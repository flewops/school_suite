# Phase 6 — Deployment on Frappe Cloud

School Suite is hosted on **Frappe Cloud**. Frappe Cloud builds the bench from the apps'
git repositories, runs the servers, takes backups and applies updates, so this repo
ships no production image or server scripts. What it does ship is the CI that tests
`school_suite` against pinned app versions before anything reaches `main`.

## One-time setup

1. **Bench Group** (a private one: custom apps from GitHub can't go on a shared bench).
   Frappe **Version 16**, an **India region** (data stays in India; see
   `data_protection.md`).
2. **Apps → Add App**, from the Marketplace: **ERPNext**, **Payments**, **Education**,
   **Learning (LMS)**, and for schools that need them **HRMS** and **India Compliance**.
3. **Apps → Add App → GitHub**: `flewops/school_suite`, branch **`main`**. If the repo is
   private, first install the Frappe Cloud GitHub app on the `flewops` account so Frappe
   Cloud can read it.
4. **Deploy** the bench group.

## Add a school (one site per school)

1. **New Site** on the bench group, e.g. `greenfield.frappe.cloud`, then add the
   school's own domain under **Site → Domains** (Frappe Cloud provisions TLS).
2. **Install apps** on that site. Required: ERPNext, Education, LMS (Payments comes
   with LMS) and School Suite. Optional per school: **HRMS** (staff payroll and leave)
   and **India Compliance** (GST e-invoicing). School Suite is tested both with and
   without the optional two.
3. Open the site and follow `IMPLEMENTATION_GUIDE.md` from the Setup Wizard.

School Suite's roles, custom fields, workflow and settings defaults are applied on
install and again on every migrate; nothing is configured by hand on Frappe Cloud.

## Releasing School Suite changes

1. Work on `version-16`; CI runs lint and the tests on every push.
2. Open a pull request `version-16` → `main`; merge when CI is green.
3. Frappe Cloud shows an update for the bench group (it tracks `main`). **Deploy** it.
4. Frappe Cloud moves each site to the new deploy: it backs the site up and runs
   `bench migrate`, which re-applies School Suite's setup through `after_migrate`.
5. Spot-check one site: log in as a parent (`/parent`), the principal (`/principal`)
   and the accountant (a fee invoice).

**Roll back:** revert the commit on `main` and deploy again. If the bad release changed
the schema, also restore the site from its pre-update backup (**Site → Backups**).

## Updating ERPNext, Education, LMS and the other apps

Frappe Cloud offers upstream updates on the bench group too. Test them first:

1. Bump that app's pin in `.github/workflows/ci.yml` to the release Frappe Cloud is
   offering, push to `version-16` and let CI pass.
2. Merge to `main`, then deploy the update on Frappe Cloud.

Payments publishes no releases, so CI tests its `version-16-hotfix` branch.

## Many schools on one bench group

- **Isolation:** each site has its own database and files; School Suite's row-level
  permissions separate users *within* a site. One school can't see another's data.
- **Trade-off:** all sites on a bench group **update together**. A school that needs
  different app versions (or its own server) gets its own bench group.
- **Scaling:** move to a bigger plan first; a school that outgrows the shared bench
  group moves to its own.

## Backups and restore test

- Frappe Cloud takes **automated backups, with offsite copies**. Check the schedule
  and retention on your plan under **Site → Backups**.
- **Restore test (monthly; a backup you haven't restored is not a backup):** download
  the latest database, public and private files from **Site → Backups**, then restore
  them on a local dev bench:

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

  The same backup files restore into a new Frappe Cloud site (**New Site → restore from
  backup**) when a school has to be moved.

## Operational notes

- The scheduler is on by default on Frappe Cloud; School Suite's absence alerts and
  LMS live-class attendance depend on it.
- `developer_mode` stays off. Demo data and the flow test refuse to run without it,
  so they can't touch a school's site.
- SMS, email, Razorpay and Zoom credentials are entered per site in the desk (SMS
  Settings, Email Account, Razorpay Settings, LMS Zoom Settings), never in git.
