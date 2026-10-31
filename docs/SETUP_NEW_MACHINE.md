# Setting up & running on a new Mac (or any machine)

## First, understand what git has — and doesn't

What you pushed to git is the **`school_suite` app only** (the custom code,
schema setup, tests, docs). To run the whole product you must also fetch the other apps and
rebuild the bench. Nothing about the running system except `school_suite` lives in
git:

| Lives in your git repo | NOT in git — handled separately |
|---|---|
| `school_suite` app: code, hooks, schema setup in `setup/install.py` (roles, custom fields, workflow, property setters, settings), tests, `docs/`, `deploy/` | Frappe + the 6 other apps (erpnext, payments, hrms, education, india_compliance, lms) — pulled from their own repos, pinned to **version-16** |
| | The bench itself (`frappe-bench/`), Python venv, node_modules |
| | **Your database and uploaded files** — moved with a **backup/restore**, not git |
| | Site config / secrets (never commit these) |

So on a new Mac you (1) rebuild the stack, (2) install all apps incl. your
`school_suite` from its git URL, and (3) restore your data if you want the
configured database (otherwise you get a clean empty one).

Two paths below: **A** for a developer/local box (same devcontainer we used), **B**
for a real production server.

---

## Prerequisites (new Mac)

1. **Docker Desktop** — install from docker.com, open it, wait until it's running
   (`docker info` succeeds).
2. **git** — `git --version` (installs Apple Command Line Tools if missing).
3. ~15 GB free disk.

> The dev image `frappe/bench:latest` already ships **Python 3.14 + Node 24**, which
> Frappe v16 requires — you don't install those yourself.

---

## Option A — Run locally on the new Mac (devcontainer)

### A1. Get frappe_docker and start the containers
```bash
cd ~/Desktop
mkdir -p school && cd school
git clone https://github.com/frappe/frappe_docker
cd frappe_docker
cp -R devcontainer-example .devcontainer
cp -R development/vscode-example development/.vscode
```
Publish the web port so your browser can reach it — edit
`.devcontainer/docker-compose.yml` and under the **`frappe`** service add:
```yaml
    ports:
      - "8000:8000"
      - "9000:9000"
```
Then:
```bash
docker compose -f .devcontainer/docker-compose.yml up -d
```

### A2. Enter the container and build the bench
```bash
docker exec -e "TERM=xterm-256color" -w /workspace/development -it devcontainer-frappe-1 bash
```
Now **inside the container**:
```bash
bench init --frappe-branch version-16 --skip-redis-config-generation frappe-bench
cd frappe-bench
bench set-config -g db_host mariadb
bench set-config -g redis_cache   redis://redis-cache:6379
bench set-config -g redis_queue   redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379
```

### A3. Fetch all the apps (pinned to v16) — **edit the school_suite URL**
```bash
bench get-app --skip-assets erpnext          --branch version-16 --resolve-deps
bench get-app --skip-assets payments          --branch version-16-hotfix
bench get-app --skip-assets hrms              --branch version-16
bench get-app --skip-assets education          --branch version-16
bench get-app --skip-assets https://github.com/resilient-tech/india-compliance --branch version-16
bench get-app --skip-assets https://github.com/frappe/lms                        --branch version-16
bench get-app --skip-assets https://github.com/<YOUR-GIT-USER>/school_suite       --branch version-16
```
(If your `school_suite` repo is private, use an SSH URL
`git@github.com:<you>/school_suite.git` with your SSH key, or an HTTPS token.)

### A4. Create the site and install everything
```bash
bench new-site school.localhost \
  --db-root-password 123 --admin-password admin \
  --mariadb-user-host-login-scope=%
bench --site school.localhost install-app erpnext payments education hrms india_compliance lms school_suite
bench --site school.localhost set-config developer_mode 0   # production-style; use 1 for development
bench build
bench use school.localhost
bench start
```
Open **http://localhost:8000** → log in `Administrator` / `admin`. On a brand-new
site you'll be taken through the **Setup Wizard** (company, financial year) — see
`IMPLEMENTATION_GUIDE.md` Part A2.

> `school_suite`'s roles, custom fields, workflow and property-setter fixes apply
> automatically on install/migrate — no manual step.

### A5. (Optional) Bring your data from the old Mac
A fresh site is empty. To copy your **configured database + files**:
```bash
# ON THE OLD MAC (inside its container, in the bench):
bench --site school.localhost backup --with-files
#   -> creates 3 files under sites/school.localhost/private/backups/ :
#      <ts>-database.sql.gz , <ts>-files.tar , <ts>-private-files.tar
# copy those 3 files to the new Mac (AirDrop / scp / USB), e.g. into
#   frappe_docker/development/   (which is /workspace/development inside the container)
```
```bash
# ON THE NEW MAC (inside the container, in the bench), after A4 created the site:
bench --site school.localhost restore /workspace/development/<ts>-database.sql.gz \
  --with-public-files  /workspace/development/<ts>-files.tar \
  --with-private-files /workspace/development/<ts>-private-files.tar \
  --db-root-password 123
bench --site school.localhost migrate
```
Your students, fees, config etc. are now on the new Mac.

### A6. Starting/stopping later
`bench start` runs the server (keep the terminal open, or run detached). After a
reboot the containers don't auto-start the server — restart with:
```bash
docker start devcontainer-mariadb-1 devcontainer-redis-cache-1 devcontainer-redis-queue-1 devcontainer-frappe-1
docker exec -d devcontainer-frappe-1 bash -lc 'cd /workspace/development/frappe-bench && bench start'
```

---

## Option B — Real production server (not a laptop)

For an actual server, don't run the devcontainer — build the **pinned production
image** instead (it bakes in all apps + `school_suite`). This repo ships the files:

- `deploy/apps.json` — all apps pinned to v16. **Edit the last line** to your
  `school_suite` git URL.
- `deploy/build.sh` — builds the image from frappe_docker's layered Containerfile.
- `.github/workflows/build-image.yml` — the same build in CI, pushing to GHCR.

```bash
git clone https://github.com/frappe/frappe_docker && cd frappe_docker
APPS_JSON=/path/to/school_suite/deploy/apps.json IMAGE_TAG=school-erp:v16 \
  /path/to/school_suite/deploy/build.sh
```
Then run it with frappe_docker's production compose (`compose.yaml` + overrides:
Traefik for TLS, a managed MariaDB/Redis, your domain). Create the site and install
apps as in A4, then restore your backup (A5). Full notes, multi-tenant (one site per
school) and S3 backups/restore: **`deployment.md`**.

---

## Common issues

- **`docker compose ... up` fails to bind port 8000** — another project (or an old
  stack) holds it. Stop that one, or change the published port to e.g. `8080:8000`.
- **`get-app` of school_suite asks for a password / fails** — the repo is private;
  use an SSH URL + key, or a personal-access-token HTTPS URL.
- **Version mismatch errors on install** — make sure *every* app is `version-16`
  (payments uses `version-16-hotfix`); don't mix branches.
- **Site loads but assets look broken** — run `bench build` then hard-refresh.
- **`bench build` dies with `Killed` / exit code 137** — out of memory. Give Docker
  Desktop at least 8 GB (Settings → Resources → Memory), stop any running
  `bench start` (its watcher holds ~1.5 GB), and build one app at a time
  (`bench build --app <app>`). `setup_local.sh` does all of this for you.
- **Browser shows `AttributeError: is_ajax`** — that hides the real error, which
  is in the bench log: usually `Access denied for user '_xxxx'`. The site folder
  (on your Mac's disk) survived but the MariaDB volume was reset, so the site's
  database is gone. Re-run `setup_local.sh`; it detects this and recreates the site.
- **After restore, something's off** — always run `bench --site <site> migrate`
  after a restore so the schema and `school_suite`'s setup reconcile.
```
