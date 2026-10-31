# Phase 6 — Deployment Readiness

## Pinned production image

`deploy/apps.json` pins every app to its v16 branch (verified in the pilot).
`deploy/build.sh` builds a single image from frappe_docker's layered Containerfile;
`.github/workflows/build-image.yml` does the same in CI and pushes to GHCR.

```bash
cd frappe_docker                       # the official repo (has the Containerfile)
APPS_JSON=/path/to/school_suite/deploy/apps.json \
  IMAGE_TAG=school-erp:v16 ./build.sh  # (copy build.sh here, or call by full path)
```

Pins: `FRAPPE_BRANCH=version-16`, `PYTHON_VERSION=3.14.10`, `NODE_VERSION=24.22.2`
(v16 requires Python 3.14+/Node 24+ — see the Phase 1 report).

> **school_suite must be reachable by the builder.** Push it to the git URL in
> `apps.json`, or inject it as a private repo with a build secret. Until then the
> build fetches the six public apps; add school_suite as the last layer.

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
