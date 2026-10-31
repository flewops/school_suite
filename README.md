# School Suite

A thin **integration app** that ties ERPNext, Frappe Education, Frappe HR, Frappe
Learning (LMS), Payments and India Compliance into one school ERP + online-learning
product for Indian schools. It is the *glue and policy* layer — it does **not**
re-implement what those apps already do.

> Pilot build. Frappe/ERPNext **v16** (Python 3.14 / Node 24). Test data only.

## What is native vs. what is this app

**Native (not ours — do not edit):** ERPNext, `education`, `hrms`, `lms`,
`india_compliance`, `payments`, `frappe`. These provide students/guardians,
admissions, fees & term-wise fee structures, assessments/grading, HR, courses/
batches/quizzes, GST/HSN, payment gateways, the Email/Notification/SMS framework,
the Workflow engine, and Education's own student+guardian portal (`edu-portal`)
with its own row-level permissions.

**This app adds only the seams and policies native can't:**
- Cross-app **unified student dashboard** (Education attendance/grades/fees +
  LMS progress/quizzes) and a **Principal dashboard** — native apps don't talk.
- **Teacher → only-assigned-classes** row security (native covers guardians, not
  staff) + base read perms for the new roles.
- **LMS batch ↔ Education class mapping** with student **auto-enrolment**.
- **"Online mode" attendance** from live-class / LMS activity.
- **India fee policy** on the native v16 billing (Fee Schedule → Sales Invoice) and
  legacy Fees: auto sibling discount, concession, late fee, RTE 12(1)(c) warning.
- **India / UDISE+ student fields** (APAAR, PEN, category, CWSN, RTE …), a UDISE+
  export placeholder, and printable **report card** and **Transfer Certificate** pages.
- **Teacher attendance + marks entry** for own classes; same-day **absence SMS**.
- **SMS / email** through Frappe's own SMS Settings and Email Account (log-only until
  configured); WhatsApp pluggable.
- **School Suite Settings**: every policy value is editable by the school, not code.
- A **School** tile on the apps screen that opens each role's starting page; parents
  land on `/parent` after login.
- Fixes for real Education v16 gaps: `Fees.income_account` fetch, Fees ignoring the
  component discount, fee Items failing India Compliance's HSN/SAC check.

See `docs/` for details: **`IMPLEMENTATION_GUIDE.md`** (the full click-by-click
school setup, empty DB → go-live), `indian_specifics.md`, `online_mode.md`,
`deployment.md`, `data_protection.md`, and **`GAP_LIST.md`** (build/buy/skip +
effort estimates).

## Run it locally (Docker devcontainer)

```bash
# from a clone of https://github.com/frappe/frappe_docker
cp -R devcontainer-example .devcontainer
cp -R development/vscode-example development/.vscode
docker compose -f .devcontainer/docker-compose.yml up -d
docker exec -w /workspace/development -it devcontainer-frappe-1 bash

# inside the container (frappe/bench:latest already has Python 3.14 + Node 24):
bench init --frappe-branch version-16 --skip-redis-config-generation frappe-bench
cd frappe-bench
bench set-config -g db_host mariadb
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379
bench get-app --skip-assets erpnext --branch version-16 --resolve-deps
bench get-app --skip-assets payments --branch version-16-hotfix
bench get-app --skip-assets hrms --branch version-16
bench get-app --skip-assets education --branch version-16
bench get-app --skip-assets https://github.com/resilient-tech/india-compliance --branch version-16
bench get-app --skip-assets https://github.com/frappe/lms --branch version-16
bench get-app --skip-assets <this repo> --branch version-16

bench new-site school.localhost --db-root-password 123 --admin-password admin \
     --mariadb-user-host-login-scope=%
bench --site school.localhost install-app erpnext payments education hrms india_compliance lms school_suite
bench --site school.localhost set-config developer_mode 1
bench build && bench use school.localhost && bench start
```

Open **http://localhost:8000** (publish port 8000 from the container).
`school_suite`'s roles, custom fields, property setters and workflow are applied
automatically on install/migrate.

## Demo data & test logins (fake only)

```bash
# complete the ERPNext setup wizard first (creates company "Demo School"), then:
bench --site school.localhost execute school_suite.setup.demo_data.run
bench --site school.localhost execute school_suite.setup.flow_test.run   # full flow
```

| Login | Password | Sees |
|---|---|---|
| `Administrator` | `admin` | everything; `/principal` dashboard |
| `guardian_meera@demo.school` | `Test@12345` | `/parent` — only Arya & Bodhi |
| `guardian_ravi@demo.school` | `Test@12345` | `/parent` — only Chetan |
| `teacher_sunita@demo.school` | `Test@12345` | only Class 1A students |
| `arya@demo.school` | `Test@12345` | only herself |

## Key modules

`permissions.py` (row security) · `api.py` (dashboards) · `online_learning.py`
(batches/online attendance) · `fees_policy.py` · `notify.py` · `reports.py`
(report card, TC, UDISE) · `www/` (`/parent`, `/principal`, `/report-card`,
`/transfer-certificate`) · `school_suite/doctype/school_suite_settings` · `setup/`
(install, demo_data, flow_test) · `tests/` · `deploy/` (prod image build).

## Engineering conventions

- **Schema lives in code.** `setup/install.py` creates roles, custom fields, property
  setters, settings defaults, the workflow and grading scale on install and every
  migrate (idempotent). There are no fixtures. Custom fields and property setters
  carry `module="School Suite"`, so `bench uninstall-app school_suite` removes them.
  One-off data changes go in `patches.txt`.
- **Policy values live in School Suite Settings**, not module constants.
- **Native first.** Don't edit ERPNext / Education / LMS; extend through hooks.
- **Whitelisted methods** check permissions server-side, carry type hints, and use
  `methods=["POST"]` when they change data. User-facing strings use `_()`.
- **Style:** `pre-commit run --all-files` (ruff lint + format, tabs).
- **Tests:** `bench --site <test-site> set-config allow_tests true` then
  `bench --site <test-site> run-tests --app school_suite`. CI (`.github/workflows/ci.yml`)
  runs lint and the tests (against the pinned versions) on every push and PR, and on
  `main` builds the production image only after they pass.
- **Releases:** versions are pinned in `deploy/versions.env` and `deploy/apps.json`;
  images are tagged `v16-<commit>` (immutable) and `v16`. See `docs/deployment.md`.
- **Staff logins get a Role Profile** (School Admin, Principal, Accountant, Teacher),
  which adds the native roles that carry the permissions.

## Known gaps

See `docs/GAP_LIST.md`. Headlines: real Zoom/Razorpay credentials, DPDP consent
records, guardian login by mobile OTP, 80C fee certificate, fee reminders / late-fee
posting, transport, real UDISE+ mapping, and folding `/parent` fully into the native
edu-portal. Trust/society **fund accounting is an open
question for a CA — not assumed.**

## License

MIT (see `license.txt`). Note: `lms` is **AGPL-3.0** — this app integrates with LMS
via its API/DocTypes only, to avoid pulling AGPL obligations into school_suite.
Confirm the combined-work licensing with a lawyer before hosted/commercial use.
