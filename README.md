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
- **India fee policy**: sibling discount, concession/scholarship, late fee.
- **Board-configurable report card** compile + **UDISE** export placeholder.
- **Pluggable SMS/WhatsApp/email** dispatch (dummy providers for the pilot).
- A **Property Setter that fixes a real Education v16 bug** (`Fees.income_account`).

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
(report card + UDISE) · `www/parent.*`, `www/principal.*` (portals) · `setup/`
(install, demo_data, flow_test) · `fixtures/` · `deploy/` (prod image build + CI).

## Known gaps

See `docs/GAP_LIST.md`. Headlines: real Zoom/Razorpay credentials, DPDP consent
records, per-board report-card PDFs, real UDISE+ mapping, and folding `/parent`
fully into the native edu-portal. Trust/society **fund accounting is an open
question for a CA — not assumed.**

## License

MIT (see `license.txt`). Note: `lms` is **AGPL-3.0** — this app integrates with LMS
via its API/DocTypes only, to avoid pulling AGPL obligations into school_suite.
Confirm the combined-work licensing with a lawyer before hosted/commercial use.
