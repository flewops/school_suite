# Gap List — Build / Buy / Skip (with effort estimates)

Status after the pilot build (Phases 1–6), updated 7 Nov 2026 with the two-year
demo-data test and a check of Frappe Education against what Indian schools need.
Effort is **engineering person-days** for one mid-level Frappe developer, excluding
the school's own content/config.

## 📋 What Frappe Education has, and what School Suite adds (checked 7 Nov 2026)
Against Education v16 (release v16.0.1 and the `version-16` branch) and its GitHub
branches. The sections below give the detail and the effort.

| Area | In Frappe Education v16 | School Suite today | Why it matters |
|---|---|---|---|
| Admissions | Available: Student Applicant and admission workflow | uses native (see 🐞 for the Student role) | core intake process |
| Student and guardian records | Available: Student, Guardian, Program Enrollment | adds India / UDISE+ fields | master data every module depends on |
| Fees | Available: Fee Structure and Fee Schedule, billed as ERPNext Sales Invoices | adds Indian fee policies and year-wise views | the first thing schools check |
| Attendance | Available | adds absence alerts and the below-75% list | daily operation |
| Class scheduling | Available: Course Schedule, typed in or repeated with the Course Scheduling Tool | timetable on `/parent` | daily operation |
| Assessments and grading | Available: Assessment Plan, Assessment Result, Grading Scale | adds the printable report card | the basis for report cards |
| Student web portal | Available: `/edu-portal` | students land there; invoice access closed (guide 9.4) | self-service for students |
| Online fee payment (Razorpay) | Available in v16.0.1: **Pay Now** on the portal's Fees page (some comparisons list it as `develop` only; it shipped in v16.0.1) | students can't reach it once invoices are closed; no pay button on `/parent` yet — BUILD | parents expect to pay fees online |
| Parent mobile app | Missing | `/parent` web page only — BUILD | parents judge the vendor on it; most complaints about school vendors are about the parent app (notifications, sibling accounts, slowness) |
| SMS and WhatsApp | Missing | SMS through native SMS Settings and the absence alert; WhatsApp has a plug-in point only — BUY + BUILD | fee reminders, absence alerts and circulars go out this way |
| Transport | Missing: no routes, stops, transport fees or GPS | nothing — BUILD or buy | standard in every serious school product |
| Board report cards (CBSE, state boards, HPC) | Missing: no board-specific formats | generic printable card with a CBSE / ICSE / State switch — BUILD | CBSE is moving to the Holistic Progress Card (teacher, self, peer and parent input), which is harder to support |
| UDISE+, NAAC, AISHE | Missing: no statutory education exports | UDISE+ fields and a draft export — BUILD; NAAC and AISHE — SKIP | schools file UDISE+; colleges report to NAAC and AISHE |
| Library | Unreleased: only on the unmerged `library-management` branch | nothing — SKIP | not in any release you could deploy |
| Timetable generation | Unreleased: only on unmerged `feat/timetable-generation` branches | nothing — SKIP | not in any release you could deploy |
| Hostels | Only on `develop`, which is mid-redesign | nothing — SKIP | residential schools need it; not yet stable |

Sources: [Education docs](https://docs.frappe.io/education) ·
[repository](https://github.com/frappe/education) ([branches](https://github.com/frappe/education/branches),
[commits on develop](https://github.com/frappe/education/commits/develop),
[tags](https://github.com/frappe/education/tags)) ·
[NCERT PARAKH on the Holistic Progress Card](https://parakh.ncert.gov.in/blog/more-report-card-idea-behind-holistic-progress-cards) ·
[parent-app reviews of a school ERP (Capterra)](https://capterra.com/p/163105/Teachmint/)

## ✅ Done and verified in the pilot
| Capability | Notes |
|---|---|
| v16 stack on one site (ERPNext + Education + HRMS + LMS + India Compliance + Payments) | all `version-16`, Python 3.14 / Node 24 |
| Row-level security (teacher→class; guardian→child via native) | verified by impersonation |
| Unified Education + LMS student dashboard + Principal dashboard | the real cross-app value |
| Parent portal (`/parent`) incl. LMS progress | augments native edu-portal |
| LMS batch ↔ class mapping + auto-enrol | verified |
| "Online mode" attendance (LMS activity; Zoom path documented) | verified (activity path) |
| Fees on the native v16 flow (Fee Schedule → Sales Invoice) counted on portals, dashboards, TC | integration tests |
| Sibling discount (auto, on new fee invoices) / concession / late-fee calculation | tests: ₹5000 → ₹4500 for a 2nd child; late fee capped |
| Fix: legacy Fees ignored the component discount when totalling | tests: 20% → ₹4000 |
| **School Suite Settings**: every policy value editable by the school | replaces code constants |
| Board-configurable report card compile + UDISE placeholder | verified |
| SMS via native SMS Settings, email via Email Account; log-only until configured | WhatsApp still pluggable |
| Teacher attendance marking + marks entry (native tools, own classes only) | verified by impersonation |
| Same-day absence SMS to guardians (once per child per day) | verified (dummy provider) |
| India / UDISE+ student fields (APAAR, PEN, category, CWSN, RTE, BPL, admission no.) + UDISE code on Company | custom fields |
| UDISE+ export with class × gender, category, CWSN/RTE/BPL + data-gap list | still a placeholder schema |
| Printable Transfer Certificate (`/transfer-certificate`) and report card (`/report-card`) | browser print / Save as PDF |
| Below-75% attendance list on `/principal`; CBSE 9-Point grading scale seed | verified |
| RTE 12(1)(c) fee warning | warns, doesn't block |
| Admission→fee→timetable→quiz→report full flow | 10/10 steps verified |
| Schema in code (no fixtures), module-tagged for clean uninstall; upgrade from the fixtures version tested | `setup/install.py` |
| 27 integration tests + CI (pre-commit lint, server tests) | `bench run-tests --app school_suite` |
| Hosting on Frappe Cloud: one site per school, release flow `version-16` → PR → `main` → deploy, backup + migrate on update | `docs/deployment.md` |
| CI tests against pinned app versions; bump a pin before deploying that app's update on Frappe Cloud | `.github/workflows/ci.yml` |
| Staff Role Profiles (School Admin, Principal, Accountant, Teacher, Parent) | tested with real logins |
| Backup/restore, data-protection and deployment docs | files shipped |
| Academic-year views: `/principal`, `/parent` and the report card show one year at a time; unpaid fees from earlier years shown separately | tests + two years of demo data on the local site |
| Student access to invoices closed (Implementation guide 9.4) | tested with real logins; a manual step on each site |

## 🐞 Found in testing (6–7 Nov 2026)
Two academic years of demo data on the local site covered promotion, a repeated
class, a mid-year join, a student who left with a TC, stream and section changes,
an RTE seat, a concession, a credit note, a bounced cheque, an advance and old-style
`Fees` bills. "Native" means the fault is in Frappe or Education, so the fix is a
setting, a guide step, an upstream PR or a small School Suite rule — never an override.

| Problem | Where | How we know | Fix (native first) | Est. (days) |
|---|---|---|---|---|
| **A student created by School Admin gets no `Student` role**, so they can't use the portal | Native: roles on User are permission level 1; School Admin only has level 0 | tested on a copy of the local site | a small School Suite rule that adds the role when the Student is saved (needs approval); until then a System Manager adds it by hand | 0.5 |
| **One Fee Schedule bills a student twice** if they have two enrollments in the same year (stream change) | Native: Fee Schedule's `get_students` joins on student and year | tested on a copy: 2 bills from one schedule | a School Suite check that refuses a second bill for the same student and Fee Schedule; report upstream | 0.5–1 |
| **A repeating student's Grades page shows last year's marks**, and the class picker lists the program twice with no year | Native student portal (filters by program, not year) | seen on screen as a repeating student | upstream fix; meanwhile parents use `/parent` and the report card, which are by year | upstream |
| The native portal still lists a student's old section | Native (`get_student_groups` ignores *active*) | API call as the student | upstream fix | upstream |
| `/parent` timetable shows the old section, and classes after a student left | School Suite (`get_timetable` ignores *active*) | page read through a parent login | count only active class memberships | 0.5 |
| `/principal` *Fees by class* puts a stream-changer's fees under the old class | School Suite (the oldest enrollment of the year wins) | page read through the principal login | use the latest enrollment of the year | 0.5 |
| A credit note shows as "-₹500 overdue", lowers the overdue total, and disappears from the parent's next-year view | School Suite (credits netted with dues; earlier-year figure shown only when above zero) | pages read through principal and parent logins | show credits on their own line | 0.5–1 |
| An advance payment (paid against no bill) isn't shown to the parent | School Suite (`/parent` counts bills only) | page read through a parent login | show unallocated advances | 0.5 |
| A student who left keeps their login, and `/parent` doesn't mark the child as left | Native (disabling a Student doesn't disable the User) + School Suite page | logged in as the student who left | guide step: disable the User when issuing the TC; label left children on `/parent` | 0.5 |
| The *Per-student balances* report (Student Fee Collection) leaves out old-style `Fees` bills; Accounts Receivable shows them only with Party Type = Student | Native reports | ran both reports | guide note; new schools bill through Fee Schedule (Sales Invoice) | doc only |
| The Accountant can't open Student Fee Collection | Native report roles | refused through the accountant login | add the role in *Role Permission for Page and Report* | config |
| The first fee bill creates a site-wide Item Price for the fee item (e.g. Tuition Fee ₹19,000) | Native: Stock Settings → *Auto insert Price List rate if missing* | seen while seeding | decide per site; the bill amount still comes from the Fee Schedule | config |
| The monthly attendance report crashes | Native (trailing space in the Student link) | reproduced; fix sent as frappe/education PR #532, still open | wait for the merge | upstream |
| Approved leave counts against the 75% attendance rule | Policy | 116 present of 186 days, 5 of them on medical leave | the school decides; adjust the calculation if needed | 0.5 |
| A report card for one term finds nothing unless the class's Student Group has that term | Native data model | tested; documented in the Implementation guide 11.3 | set the term on term-wise groups, or use the year view | doc only |

## 🔨 BUILD (remaining gaps, worth doing in-house)
| Gap | Why build | Est. (days) |
|---|---|---|
| Real Zoom S2S integration wired end-to-end (create class, pull attendance, match by email) | only the plumbing is done; needs real creds + email-match tuning + teacher override UI | 3–5 |
| Razorpay test→live fee collection (Payment Gateway Account, Payment Request on fee invoices, reconciliation) | Education v16.0.1 already has a Razorpay **Pay Now** on the student portal's Fees page, but students can't reach it once invoice access is closed (guide 9.4). Needs a pay button on `/parent`, real keys, reconciliation, and a review of Education's `billing.py`: it imports a helper from an ERPNext test file and appears to trust the invoice number the browser sends (read in code, not tested) | 2–4 |
| Consent Record doctype + capture flow (DPDP children's data) | legal requirement; not native | 3–4 |
| Retention/purge job + export audit surfacing | legal requirement | 2–3 |
| Real UDISE+ field mapping to the government schema | placeholder only; format is fixed & external | 4–6 |
| Fold parent portal fully into native edu-portal (remove overlap) | reduce duplication flagged in review | 2–3 |
| Board-exact layouts (CBSE / state formats, co-scholastic block) for the printable report card and TC | generic print pages exist; boards prescribe exact formats | 2–3 |
| **Section 80C tuition-fee certificate** for parents' income-tax claim | every parent asks each year; needs a "tuition" flag on Fee Category + paid-in-FY sum from Payment Entries | 1–2 |
| **Guardian login by mobile number + SMS OTP** | many parents have no email. Frappe supports mobile login; needs a user-creation flow. (Mandatory student email can now be switched off in Settings.) | 2–3 |
| **Fee-due reminders + late-fee posting** (scheduler) | `late_fee_amount` computes but nothing posts or reminds; ERPNext Dunning may cover posting; needs DLT templates | 1–2 |
| **RTE reimbursement claim tracking** (per-child per-year claim to the State) | private unaided schools claim this yearly | 2–3 |
| **Transport**: routes, stops, bus fee by stop, vehicle staff; live GPS tracking | very common in Indian schools; nothing native, and no upstream branch for it | 4–6 (or buy; GPS: buy) |
| **Circulars and bulk messages** to parents (one class, a year group, the whole school) | only the absence alert sends today; schools send circulars by SMS/WhatsApp | 1–2 |
| **Parent mobile app** (installable, push notifications) | parents judge school vendors on the app; `/parent` works in a phone browser but isn't an app | not estimated (or buy) |
| **Co-scholastic grades + NEP 2020 Holistic Progress Card** | CBSE template expects co-scholastic data; no source today | 3–5 |
| **Portal translations** (Hindi / regional) | strings are wrapped in `_()`; needs the translation files | translation only |
| **Restrict sensitive student fields** (religion, caste, disability, BPL) to staff via permlevel | DPDP minimisation | 0.5–1 |

## 💳 BUY / integrate (don't build)
| Gap | Buy instead of build |
|---|---|
| SMS / WhatsApp delivery | a provider (MSG91, Gupshup, Twilio, Meta WhatsApp Cloud) — plug into `notify.PROVIDERS` |
| Payment gateway | Razorpay (already the chosen rail) — just credentials + account |
| Video classes | Zoom (paid plan for reporting API) or Google Meet |
| Managed hosting (India region), backups with offsite copies | **Frappe Cloud** (chosen) |

## ⏭️ SKIP (for the pilot; revisit later)
| Gap | Why skip now |
|---|---|
| Trust/society **fund accounting** | **open question for the CA** — do not assume a model |
| Separate sites + SSO topology | single site is simpler; only split if AGPL/upgrade cadence forces it |
| Native-dashboard rebuild of `/principal` | the custom page works; migrate to Number Cards only if desired |
| Multi-board report cards beyond CBSE/State | add boards when a school actually needs them |
| Hostel, library, automatic timetable generation | hostel and library matter only to boarding / larger schools. Upstream Education has all three unreleased: hostel only on `develop` (mid-redesign), library and timetable generation on unmerged branches. Build or integrate when a school asks |
| CBSE board registration (LOC) export | Classes IX–XII only; format changes yearly |
| NAAC / AISHE exports | colleges only, not schools |

## ⚠️ Upstream risk (Frappe Education)
Checked on GitHub for the 90 days to 7 Nov 2026:

| Signal | Value | Why it matters |
|---|---|---|
| Recent commits on `develop` from one developer | 85% (of 33) | the app depends on one person |
| Issues opened / closed | 21 / **0** | nothing reported recently has been fixed |
| Pull requests merged | 13 | low activity next to ERPNext core |
| Education v16.0.0 after ERPNext v16.0.0 | about 10 weeks (25 Mar vs 12 Jan 2026) | the app lags core releases |
| `develop` reworks core records | the Student Group and Instructor doctypes are gone; Faculty replaces Instructor | anything built on it now may need reworking |

So:
- Don't wait on upstream for fixes. Work around native bugs with settings, guide
  steps or small School Suite rules, and still send the fix upstream (PR #532 is
  still open).
- Don't build on `develop` or feature branches.
- CI pins Education **v16.0.1**, but **v16.1.0** is out and the local bench runs the
  newer `version-16` branch. Before each update, test against exactly what the
  Frappe Cloud bench deploys.

## Rough total for a production-hardened v1
**~35–50 engineering days** across the BUILD items and the fixes found in testing,
not counting a parent mobile app, plus the school's own content setup (programmes,
courses, fee structures, staff, report-card layouts) and the legal review. The pilot
itself (what's done) is the foundation those build on.
