# Phase 6 — Deployment Readiness

## Production image: pinned, tested, tagged per commit

**What's in it** is pinned in two files, used by CI and both scripts alike:

- `deploy/versions.env` — Frappe `v16.54.0`, Python `3.14.10`, Node `24.22.2`, and the
  frappe_docker commit whose `images/custom/Containerfile` builds the image.
- `deploy/apps.json` — each app at a **release tag**: ERPNext `v16.53.0`, HRMS
  `v16.53.0`, Education `v16.0.1`, India Compliance `v16.11.0`, LMS `v2.63.0`.
  Payments publishes no releases, so it stays on `version-16-hotfix`. bench clones
  with `git clone --branch`, which takes a branch or tag, not a commit.

To change a version, edit the pin, push to `version-16`, and let CI run the tests
against it before it reaches `main`.

**How it's built** (`.github/workflows/ci.yml`): on every push to `main` (or a `v*`
tag), the image is built **only after lint and the tests pass**, pushed to GHCR, and
smoke-tested (every app must be inside). Pushes to `version-16` and pull requests
run lint and tests only.

> The image uses frappe_docker's **custom** Containerfile with `apps.json` passed as
> a **BuildKit secret**. Earlier builds passed it as a build-arg, which the current
> Containerfile ignores, so those images held the Frappe framework only.

**Tags** on `ghcr.io/flewops/school-erp`:

| Tag | Moves? | Use |
|---|---|---|
| `v16-<commit>` (e.g. `v16-3ad0698`) | never | **deploy and roll back with this** |
| `v16` | yes, newest `main` build | quick tests only |
| `v1.2.0` (git tag) | never | named releases |

**Manual build** (same result as CI):

```bash
cd frappe_docker && git checkout <FRAPPE_DOCKER_REF from deploy/versions.env>
/path/to/school_suite/deploy/build.sh      # tags school-erp:v16 and school-erp:v16-<commit>
```

## Install, upgrade, roll back

`deploy/run_production.sh` does all three. On an existing site it takes a backup,
switches to the new image and runs `bench migrate`; it reads the database password
back from the env file instead of generating a new one.

```bash
# install or upgrade to a specific build
SITE=erp.school.in LETSENCRYPT_EMAIL=it@school.in \
  IMAGE=ghcr.io/flewops/school-erp:v16-<commit> ./deploy/run_production.sh

# roll back: run it again with the previous v16-<commit> (then restore the
# pre-upgrade backup if that release changed the schema)
```

With a registry image the default `PULL_POLICY=always` makes the server fetch the
tag again; with the old default (`missing`) a server that already had `v16` kept
running the old image after an upgrade.

## Multi-tenant plan: one site per school on a shared bench

- One **bench** (one image, one set of workers/Redis), **N sites** — `school-a.in`,
  `school-b.in`, … — each its own database and files. Add a school with
  `bench new-site <domain> --install-app erpnext,payments,education,hrms,india_compliance,lms,school_suite`.
- **Isolation:** data is per-site (separate DB); school_suite's row-level
  permissions isolate users *within* a site. Cross-site access is impossible.
- **Scaling:** vertical first; when a tenant outgrows the shared bench, move that
  site to its own bench (backup → restore on new bench). DNS: one A record per
  school pointing at the proxy; Frappe routes by host header.
- **Trade-off:** shared bench = cheap and simple, but **all sites upgrade together**
  (one app version set). A school needing a different version must move to its own
  bench.

## Backups to S3-compatible storage + restore test

- Native: `bench --site <site> backup --with-files`. Verified locally — produces a
  gzipped DB dump (+ files). Schedule daily via the bench's `backup` cron.
- Off-site: Frappe ships S3 push — set **Backup Settings** (endpoint, bucket, access
  key, secret) for any S3-compatible store (AWS S3, Wasabi, MinIO). Keys go in site
  config / env, **never in git**.
- **Restore test (run monthly — a backup you haven't restored is not a backup):**

  ```bash
  bench new-site restore-test.localhost --admin-password admin
  bench --site restore-test.localhost restore \
      /path/to/<timestamp>-database.sql.gz \
      --with-public-files <files.tar> --with-private-files <private.tar>
  bench --site restore-test.localhost migrate
  bench --site restore-test.localhost execute \
      frappe.client.get_count --kwargs '{"doctype":"Student"}'   # sanity check
  bench drop-site restore-test.localhost --force                 # clean up
  ```

## Operational notes

- Run `bench --site <site> migrate` after every image upgrade (re-applies school_suite's
  schema and settings defaults through its `after_migrate` setup automatically).
- Enable the scheduler in production (`bench --site <site> enable-scheduler`) so
  LMS live-class attendance, reminders, and backups run.
