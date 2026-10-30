#!/usr/bin/env bash
#
# setup_local.sh — one-shot local setup for the Greenfield School ERP + LMS stack.
#
# Usage (from a clone of your school_suite repo):
#     ./setup_local.sh                      # uses this repo's git origin as school_suite
#     ./setup_local.sh <school_suite_git_url>
#   env overrides: WORKDIR, SCHOOL_SUITE_BRANCH, SITE, ADMIN_PW
#
# What it does: clones frappe_docker, starts the dev containers (published on
# :8000), builds a Frappe v16 bench, installs all 7 apps (incl. YOUR school_suite),
# creates the site, and starts the server. Safe to re-run (it skips finished steps).
#
# Requirements: Docker Desktop running, git. (Python/Node come inside the image.)
set -euo pipefail

# ----------------------------------------------------------------------------- config
WORKDIR="${WORKDIR:-$HOME/school-erp}"          # where frappe_docker is cloned
PROJECT="school"                                # docker compose project -> containers school-*
SITE="${SITE:-school.localhost}"
FRAPPE_BRANCH="version-16"
SS_BRANCH="${SCHOOL_SUITE_BRANCH:-version-16}"   # your school_suite branch
DB_ROOT_PW="123"
ADMIN_PW="${ADMIN_PW:-admin}"
C="${PROJECT}-frappe-1"                          # frappe container name

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHOOL_SUITE_URL="${1:-${SCHOOL_SUITE_URL:-$(git -C "$SELF_DIR" config --get remote.origin.url 2>/dev/null || true)}}"

log(){ printf "\n\033[1;32m==> %s\033[0m\n" "$*"; }
die(){ printf "\n\033[1;31mERROR: %s\033[0m\n" "$*" >&2; exit 1; }

# ----------------------------------------------------------------------------- 0. checks
command -v docker >/dev/null || die "Docker is not installed. Install Docker Desktop."
docker info >/dev/null 2>&1  || die "Docker daemon not running. Open Docker Desktop and wait until it's ready."
command -v git >/dev/null    || die "git is not installed."
[ -n "$SCHOOL_SUITE_URL" ]   || die "Could not determine school_suite git URL. Run: ./setup_local.sh <git_url>"
log "school_suite = $SCHOOL_SUITE_URL  (branch $SS_BRANCH)"

# ----------------------------------------------------------------------------- 1. frappe_docker
mkdir -p "$WORKDIR"; cd "$WORKDIR"
if [ ! -d frappe_docker ]; then
  log "Cloning frappe_docker"
  git clone --depth 1 https://github.com/frappe/frappe_docker
fi
cd frappe_docker
FD="$PWD"
[ -d .devcontainer ]        || cp -R devcontainer-example .devcontainer
[ -d development/.vscode ]  || cp -R development/vscode-example development/.vscode

# publish ports via an override file (no editing of the stock compose)
cat > .devcontainer/ports.override.yml <<'YML'
services:
  frappe:
    ports:
      - "8000:8000"
      - "9000:9000"
YML

# ----------------------------------------------------------------------------- 2. containers
log "Starting containers (compose project: $PROJECT)"
docker compose -p "$PROJECT" \
  -f .devcontainer/docker-compose.yml \
  -f .devcontainer/ports.override.yml up -d

log "Waiting for the frappe container and MariaDB..."
for i in $(seq 1 60); do docker exec "$C" true 2>/dev/null && break; sleep 2; done
docker exec "$C" true 2>/dev/null || die "Container $C did not come up."
docker exec "$C" bash -lc 'for i in $(seq 1 60); do (echo > /dev/tcp/mariadb/3306) 2>/dev/null && exit 0; sleep 2; done; exit 1' \
  || die "MariaDB did not become reachable."

# ----------------------------------------------------------------------------- 3. bench + apps + site
# write the in-container steps to the shared volume (/workspace/development)
cat > "$FD/development/_bootstrap_bench.sh" <<'INNER'
#!/bin/bash
set -euo pipefail
cd /workspace/development

if [ ! -d frappe-bench ]; then
  echo "==> bench init (frappe $FRAPPE_BRANCH)"
  bench init --frappe-branch "$FRAPPE_BRANCH" --skip-redis-config-generation frappe-bench
fi
cd frappe-bench
bench set-config -g db_host mariadb
bench set-config -g redis_cache    redis://redis-cache:6379
bench set-config -g redis_queue    redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379

get(){ echo "==> get-app $*"; bench get-app --skip-assets "$@"; }
[ -d apps/erpnext ]          || get erpnext  --branch version-16 --resolve-deps
[ -d apps/payments ]         || get payments --branch version-16-hotfix
[ -d apps/hrms ]             || get hrms     --branch version-16
[ -d apps/education ]        || get education --branch version-16
[ -d apps/india_compliance ] || get https://github.com/resilient-tech/india-compliance --branch version-16
[ -d apps/lms ]              || get https://github.com/frappe/lms --branch version-16
[ -d apps/school_suite ]     || get "$SCHOOL_SUITE_URL" --branch "$SS_BRANCH"

if [ ! -d "sites/$SITE" ]; then
  echo "==> creating site $SITE"
  bench new-site "$SITE" --db-root-password "$DB_ROOT_PW" --admin-password "$ADMIN_PW" \
       --mariadb-user-host-login-scope=%
  bench --site "$SITE" install-app erpnext payments education hrms india_compliance lms school_suite
fi
bench --site "$SITE" set-config developer_mode 1
echo "==> building assets (first time is slow)"
bench build
bench use "$SITE"
echo "BOOTSTRAP_OK"
INNER

log "Building bench + installing apps inside the container (several minutes the first time)..."
docker exec \
  -e FRAPPE_BRANCH="$FRAPPE_BRANCH" -e SS_BRANCH="$SS_BRANCH" \
  -e SCHOOL_SUITE_URL="$SCHOOL_SUITE_URL" -e SITE="$SITE" \
  -e DB_ROOT_PW="$DB_ROOT_PW" -e ADMIN_PW="$ADMIN_PW" \
  -w /workspace/development "$C" bash /workspace/development/_bootstrap_bench.sh

# ----------------------------------------------------------------------------- 4. start the server
log "Starting the web server"
docker exec -d "$C" bash -lc 'cd /workspace/development/frappe-bench && bench start > /tmp/bench.log 2>&1'
for i in $(seq 1 90); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 http://localhost:8000/api/method/ping 2>/dev/null)" = "200" ] && break
  sleep 2
done

# ----------------------------------------------------------------------------- done
printf '\n\033[1;32m============================================================\033[0m\n'
cat <<DONE
  ✅  Ready.  Open:  http://localhost:8000
      Login:  Administrator  /  $ADMIN_PW
      (a fresh site starts with the Setup Wizard — see docs/IMPLEMENTATION_GUIDE.md)

  Restart later (after a reboot):
      docker start ${PROJECT}-mariadb-1 ${PROJECT}-redis-cache-1 ${PROJECT}-redis-queue-1 ${PROJECT}-frappe-1
      docker exec -d ${PROJECT}-frappe-1 bash -lc 'cd /workspace/development/frappe-bench && bench start'

  Stop everything:
      docker compose -p ${PROJECT} -f "$FD/.devcontainer/docker-compose.yml" -f "$FD/.devcontainer/ports.override.yml" stop
DONE
printf '\033[1;32m============================================================\033[0m\n'
