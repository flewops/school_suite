#!/usr/bin/env bash
#
# run_production.sh — bring up, or upgrade, the School Suite stack in PRODUCTION.
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
#   IMAGE=ghcr.io/flewops/school-erp:v16-<commit>
#                          prebuilt image (else it BUILDS locally). Prefer the
#                          v16-<commit> tag: it never moves, so you can roll back.
#   DB_PASSWORD=...        MariaDB root password (first run: generated; later runs:
#                          read back from the env file, since MariaDB keeps the first)
#   ADMIN_PASSWORD=...     Administrator password for a NEW site (generated if unset)
#   PROJECT=school_prod    docker compose project name
#   WORKDIR=~/school-erp   where frappe_docker is cloned
#   PULL_POLICY=always     always (default for a registry IMAGE, so a re-pushed tag
#                          is picked up) | missing | never (local build)
#
# First install and upgrades use the same command. On an existing site it backs up,
# switches to the new image and runs `bench migrate`.
#
# Example:
#   SITE=erp.greenfield.edu LETSENCRYPT_EMAIL=admin@greenfield.edu \
#     IMAGE=ghcr.io/flewops/school-erp:v16-3ad0698 ./run_production.sh
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # the deploy/ folder
# shellcheck source=versions.env
source "$SELF_DIR/versions.env"
APPS_JSON="$SELF_DIR/apps.json"
PROJECT="${PROJECT:-school_prod}"
WORKDIR="${WORKDIR:-$HOME/school-erp}"

log(){ printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# --------------------------------------------------------------------------- checks
command -v docker >/dev/null || die "Docker not installed."
docker info >/dev/null 2>&1  || die "Docker daemon not running."
: "${SITE:?Set SITE=your.domain}"
: "${LETSENCRYPT_EMAIL:?Set LETSENCRYPT_EMAIL=you@mail.com}"

# --------------------------------------------------------------------------- frappe_docker
mkdir -p "$WORKDIR"; cd "$WORKDIR"
if [ ! -d frappe_docker ]; then
  log "Cloning frappe_docker at $FRAPPE_DOCKER_REF"
  git init -q frappe_docker
  git -C frappe_docker fetch -q --depth 1 https://github.com/frappe/frappe_docker "$FRAPPE_DOCKER_REF"
  git -C frappe_docker checkout -q FETCH_HEAD
elif [ "$(git -C frappe_docker rev-parse HEAD)" != "$FRAPPE_DOCKER_REF" ]; then
  log "WARNING: frappe_docker is not at the pinned FRAPPE_DOCKER_REF ($FRAPPE_DOCKER_REF)"
fi
cd frappe_docker; FD="$PWD"
ENV_FILE="$FD/$PROJECT.env"

# MariaDB keeps the root password it was first initialised with: on later runs
# reuse the one in the env file instead of generating a new (wrong) one.
if [ -z "${DB_PASSWORD:-}" ] && [ -f "$ENV_FILE" ]; then
  DB_PASSWORD="$(sed -n 's/^DB_PASSWORD=//p' "$ENV_FILE")"
fi
DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -hex 16)}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(openssl rand -hex 12)}"

# --------------------------------------------------------------------------- image
if [ -z "${IMAGE:-}" ]; then
  IMAGE="school-erp:v16-$(git -C "$SELF_DIR" rev-parse --short HEAD)"
  log "No IMAGE given — building $IMAGE from apps.json (this takes a while)"
  # custom Containerfile + apps.json as a BuildKit secret: see deploy/build.sh
  DOCKER_BUILDKIT=1 docker build \
    --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
    --build-arg=FRAPPE_BRANCH="$FRAPPE_BRANCH" \
    --build-arg=PYTHON_VERSION="$PYTHON_VERSION" \
    --build-arg=NODE_VERSION="$NODE_VERSION" \
    --secret=id=apps_json,src="$APPS_JSON" \
    --tag "$IMAGE" \
    --file images/custom/Containerfile .
  PULL_POLICY="${PULL_POLICY:-never}"
fi
PULL_POLICY="${PULL_POLICY:-always}"
case "$IMAGE" in *:*) : ;; *) die "IMAGE must include a tag, e.g. name:v16-<commit>";; esac
CUSTOM_IMAGE="${IMAGE%:*}"; CUSTOM_TAG="${IMAGE##*:}"
log "Using image $CUSTOM_IMAGE:$CUSTOM_TAG (pull_policy=$PULL_POLICY)"

# --------------------------------------------------------------------------- env file
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
NEW_SITE=0
if "${COMPOSE[@]}" exec -T backend bash -lc "test -d sites/$SITE"; then
  # Upgrade: the new image may carry schema changes and patches, so migrate
  # (after a backup) before the site is used.
  log "Site $SITE exists — backing up, then migrating to the new image"
  "${COMPOSE[@]}" exec -T backend bench --site "$SITE" backup --with-files
  "${COMPOSE[@]}" exec -T backend bench --site "$SITE" migrate
else
  NEW_SITE=1
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
      Login:     $([ "$NEW_SITE" = 1 ] && echo "Administrator / $ADMIN_PASSWORD" || echo "unchanged (existing site)")
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
