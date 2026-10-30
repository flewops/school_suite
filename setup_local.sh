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

# stop a `bench start` left over from an earlier run: its watcher holds ~1.5 GB the
# asset build needs, and it would keep port 8000 from the server we start at the end
BENCH_PROCS='honcho start|frappe.utils.bench_helper|socketio.js|esbuild|yarn run watch'
stop_bench(){
  docker exec "$C" pkill -f "$BENCH_PROCS" 2>/dev/null || true
  sleep 3
  docker exec "$C" pkill -9 -f "$BENCH_PROCS" 2>/dev/null || true
}

# ----------------------------------------------------------------------------- 0. checks
command -v docker >/dev/null || die "Docker is not installed. Install Docker Desktop."
docker info >/dev/null 2>&1  || die "Docker daemon not running. Open Docker Desktop and wait until it's ready."
command -v git >/dev/null    || die "git is not installed."
[ -n "$SCHOOL_SUITE_URL" ]   || die "Could not determine school_suite git URL. Run: ./setup_local.sh <git_url>"
# the Vite builds of lms/hrms/education get OOM-killed (exit 137) below ~7 GB
DOCKER_MEM_MB=$(( $(docker info --format '{{.MemTotal}}') / 1024 / 1024 ))
[ "$DOCKER_MEM_MB" -ge 7000 ] || die "Docker has only ${DOCKER_MEM_MB} MB of memory; the asset build needs ~8 GB.
  Docker Desktop -> Settings -> Resources -> Memory: set 8 GB or more, Apply & Restart, then re-run."
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

# an app counts as fetched only once bench registered it in apps.txt; a half-done
# clone from an interrupted run is fetched again (--overwrite)
get(){
  local name=$1; shift
  grep -qx "$name" sites/apps.txt 2>/dev/null && return 0
  echo "==> get-app $name"
  bench get-app --skip-assets --overwrite "$@"
}
get erpnext          erpnext  --branch version-16 --resolve-deps
get payments         payments --branch version-16-hotfix
get hrms             hrms     --branch version-16
get education        education --branch version-16
get india_compliance https://github.com/resilient-tech/india-compliance --branch version-16
get lms              https://github.com/frappe/lms --branch version-16
get school_suite     "$SCHOOL_SUITE_URL" --branch "$SS_BRANCH"

# The site folder lives on the bind mount but the database lives in the MariaDB
# volume, so they can get out of sync (e.g. volume reset). Check the DB itself.
site_db_exists(){
  local db out
  db=$(sed -n 's/.*"db_name": *"\([^"]*\)".*/\1/p' "sites/$SITE/site_config.json" 2>/dev/null)
  [ -n "$db" ] || return 1
  out=$(mariadb -h mariadb -uroot -p"$DB_ROOT_PW" -N -e "SHOW DATABASES LIKE '$db'") \
    || { echo "ERROR: cannot query MariaDB as root" >&2; exit 1; }
  [ -n "$out" ]
}

if ! site_db_exists; then
  if [ -d "sites/$SITE" ]; then
    echo "==> sites/$SITE exists but its database is missing (MariaDB volume reset?) - recreating site"
  else
    echo "==> creating site $SITE"
  fi
  bench new-site "$SITE" --force --db-root-password "$DB_ROOT_PW" --admin-password "$ADMIN_PW" \
       --mariadb-user-host-login-scope=%
fi
# install-app skips apps already installed, so this also finishes an interrupted install
bench --site "$SITE" install-app erpnext payments education hrms india_compliance lms school_suite
bench --site "$SITE" set-config developer_mode 1
bench use "$SITE"

# Build one app at a time: a single `bench build` runs every app's Vite build while
# frappe's bundler is still in memory, and gets OOM-killed (exit 137) on an 8 GB VM.
# Skipped on re-runs when no app's commit changed since the last complete build.
BUILD_STAMP=sites/.setup_build_ok
build_id=$(for a in $(cat sites/apps.txt); do echo "$a $(git -C "apps/$a" rev-parse HEAD)"; done | sha1sum | cut -d' ' -f1)
if [ -f sites/assets/assets.json ] && [ "$(cat "$BUILD_STAMP" 2>/dev/null)" = "$build_id" ]; then
  echo "==> assets already built for these app versions - skipping build"
else
  rm -f "$BUILD_STAMP"
  for app in $(cat sites/apps.txt); do
    echo "==> building assets: $app (first time is slow)"
    bench build --app "$app" || { echo "==> build of $app failed - retrying once"; bench build --app "$app"; }
  done
  echo "$build_id" > "$BUILD_STAMP"
fi
echo "BOOTSTRAP_OK"
INNER

stop_bench
log "Building bench + installing apps inside the container (several minutes the first time)..."
docker exec \
  -e FRAPPE_BRANCH="$FRAPPE_BRANCH" -e SS_BRANCH="$SS_BRANCH" \
  -e SCHOOL_SUITE_URL="$SCHOOL_SUITE_URL" -e SITE="$SITE" \
  -e DB_ROOT_PW="$DB_ROOT_PW" -e ADMIN_PW="$ADMIN_PW" \
  -w /workspace/development "$C" bash /workspace/development/_bootstrap_bench.sh

# ----------------------------------------------------------------------------- 4. start the server
log "Starting the web server"
docker exec -d "$C" bash -lc 'cd /workspace/development/frappe-bench && bench start > /tmp/bench.log 2>&1'
# /login only renders when the DB connection and the site work, and it links the built CSS
code=000
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 http://localhost:8000/login 2>/dev/null || true)
  [ "$code" = "200" ] && break
  sleep 2
done
server_failed(){
  docker exec "$C" tail -40 /tmp/bench.log >&2 || true
  die "$1  Full log: docker exec $C cat /tmp/bench.log"
}
[ "$code" = "200" ] || server_failed "Server did not come up (last HTTP status for /login: $code)."
css=$(curl -s --max-time 10 http://localhost:8000/login | grep -o '/assets/[^"]*\.css' | head -1 || true)
[ -n "$css" ] && [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://localhost:8000$css")" = "200" ] \
  || server_failed "Login page loads but its stylesheet (${css:-none found}) does not - assets are not built."

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
