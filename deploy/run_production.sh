#!/usr/bin/env bash
#
# run_production.sh — bring up the Greenfield School stack in PRODUCTION.
#
# Run this ON THE SERVER (a Linux host with a public IP and your domain's DNS
# A-record pointing at it) — NOT on a laptop. It uses frappe_docker's production
# compose: Traefik (automatic HTTPS via Let's Encrypt) + MariaDB + Redis +
# gunicorn web + background workers + scheduler.
#
# REQUIRED env vars:
#   SITE=school.example.com         your domain (becomes the Frappe site name)
#   LETSENCRYPT_EMAIL=you@mail.com  email for the TLS certificate
# OPTIONAL env vars:
#   IMAGE=ghcr.io/flewops/school-erp:v16   prebuilt image (else it BUILDS locally)
#   DB_PASSWORD=...        MariaDB root password      (generated if unset)
#   ADMIN_PASSWORD=...     site Administrator password (generated if unset)
#   PROJECT=school_prod    docker compose project name
#   WORKDIR=~/school-erp   where frappe_docker is cloned
#   PULL_POLICY=missing    always | never | missing
#
# Example:
#   SITE=erp.greenfield.edu LETSENCRYPT_EMAIL=admin@greenfield.edu ./run_production.sh
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # the deploy/ folder
APPS_JSON="$SELF_DIR/apps.json"
PROJECT="${PROJECT:-school_prod}"
WORKDIR="${WORKDIR:-$HOME/school-erp}"
PULL_POLICY="${PULL_POLICY:-missing}"
FRAPPE_BRANCH="version-16"
PY_VER="3.14.10"; NODE_VER="24.22.2"

log(){ printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# --------------------------------------------------------------------------- checks
command -v docker >/dev/null || die "Docker not installed."
docker info >/dev/null 2>&1  || die "Docker daemon not running."
: "${SITE:?Set SITE=your.domain}"
: "${LETSENCRYPT_EMAIL:?Set LETSENCRYPT_EMAIL=you@mail.com}"
DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -hex 16)}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(openssl rand -hex 12)}"

# --------------------------------------------------------------------------- frappe_docker
mkdir -p "$WORKDIR"; cd "$WORKDIR"
[ -d frappe_docker ] || { log "Cloning frappe_docker"; git clone --depth 1 https://github.com/frappe/frappe_docker; }
cd frappe_docker; FD="$PWD"

# --------------------------------------------------------------------------- image
if [ -z "${IMAGE:-}" ]; then
  IMAGE="school-erp:v16"
  log "No IMAGE given — building $IMAGE from apps.json (this takes a while)"
  APPS_JSON_BASE64="$(base64 < "$APPS_JSON" | tr -d '\n')"
  docker build \
    --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
    --build-arg=FRAPPE_BRANCH="$FRAPPE_BRANCH" \
    --build-arg=PYTHON_VERSION="$PY_VER" \
    --build-arg=NODE_VERSION="$NODE_VER" \
    --build-arg=APPS_JSON_BASE64="$APPS_JSON_BASE64" \
    --tag "$IMAGE" \
    --file images/layered/Containerfile .
  PULL_POLICY="never"
fi
case "$IMAGE" in *:*) : ;; *) die "IMAGE must include a tag, e.g. name:v16";; esac
CUSTOM_IMAGE="${IMAGE%:*}"; CUSTOM_TAG="${IMAGE##*:}"
log "Using image $CUSTOM_IMAGE:$CUSTOM_TAG (pull_policy=$PULL_POLICY)"

# --------------------------------------------------------------------------- env file
ENV_FILE="$FD/$PROJECT.env"
{
  echo "CUSTOM_IMAGE=$CUSTOM_IMAGE"
  echo "CUSTOM_TAG=$CUSTOM_TAG"
  echo "PULL_POLICY=$PULL_POLICY"
  echo "DB_PASSWORD=$DB_PASSWORD"
  echo "LETSENCRYPT_EMAIL=$LETSENCRYPT_EMAIL"
  printf 'SITES_RULE=Host(\x60%s\x60)\n' "$SITE"     # Traefik routing rule, backticks literal
  echo "FRAPPE_SITE_NAME_HEADER=$SITE"
} > "$ENV_FILE"
chmod 600 "$ENV_FILE"
log "Wrote $ENV_FILE (contains secrets — keep it safe, do NOT commit)"

# --------------------------------------------------------------------------- bring up
COMPOSE=( docker compose -p "$PROJECT" --env-file "$ENV_FILE"
          -f compose.yaml
          -f overrides/compose.mariadb.yaml
          -f overrides/compose.redis.yaml
          -f overrides/compose.https.yaml )
log "Starting the production stack"
"${COMPOSE[@]}" up -d

log "Waiting for the backend to be ready..."
for i in $(seq 1 60); do
  "${COMPOSE[@]}" exec -T backend bash -lc 'ls sites/apps.txt >/dev/null 2>&1' && break
  sleep 3
done

# --------------------------------------------------------------------------- create site
if "${COMPOSE[@]}" exec -T backend bash -lc "test -d sites/$SITE"; then
  log "Site $SITE already exists — skipping creation"
else
  log "Creating site $SITE and installing all apps"
  "${COMPOSE[@]}" exec -T backend bench new-site "$SITE" \
    --mariadb-user-host-login-scope=% \
    --db-root-password "$DB_PASSWORD" \
    --admin-password "$ADMIN_PASSWORD" \
    --install-app erpnext --install-app payments --install-app education \
    --install-app hrms --install-app india_compliance --install-app lms \
    --install-app school_suite
  "${COMPOSE[@]}" exec -T backend bench --site "$SITE" scheduler enable
fi

# --------------------------------------------------------------------------- done
printf '\n\033[1;32m============================================================\033[0m\n'
cat <<DONE
  ✅  Production stack is up.

      Site:      https://$SITE          (TLS provisions automatically via Let's Encrypt;
                 give it a minute on first run, and ensure DNS points here + ports 80/443 open)
      Login:     Administrator / $ADMIN_PASSWORD
      DB root:   $DB_PASSWORD
      Env file:  $ENV_FILE   (secrets — keep safe, never commit)

  Manage:
      ${COMPOSE[*]} ps
      ${COMPOSE[*]} logs -f backend
      ${COMPOSE[*]} down          # stop (keeps volumes/data)

  Backups: add  -f overrides/compose.backup-cron.yaml  for scheduled backups,
  and push them off-site to S3 (see docs/deployment.md). ALWAYS test a restore.
DONE
printf '\033[1;32m============================================================\033[0m\n'
