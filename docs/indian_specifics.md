# Phase 5 — Indian School Specifics

Native-first: ERPNext/Education already cover most of this. School Suite adds only
the policies that are **not** native.

## Fees

| Item | Native? | Where |
|---|---|---|
| Term-wise fee structure | ✅ Native | `Fee Structure.academic_term` |
| Fee schedules / assessment | ✅ Native | `Fee Schedule`, `Fees` |
| Per-component discount | ✅ Native | `Fee Component.discount` |
| Sequential receipt numbering | ✅ Native | `Fees` naming series `EDU-FEE-.YYYY.-` |
| **Sibling discount** | ❌ Custom | `fees_policy.apply_sibling_discount` |
| **Scholarship / concession** | ❌ Custom | `fees_policy.apply_concession` |
| **Late fee** | ❌ Custom | `fees_policy.late_fee_amount` |

Policy knobs live at the top of `fees_policy.py` (sibling discount by birth order,
late-fee per-day and cap). Verified: a 3rd child gets 15% (₹5000→₹4250); an
overdue fee accrues ₹50/day capped at ₹1000.

**Receipt numbering note:** the native series is already sequential per year. If a
board/trust requires a specific format (e.g. per-branch prefixes), change the
`Fees` naming series via a Property Setter in school_suite — do not edit Education.

## Report cards (board-configurable)

Education ships `Assessment Result` + `Grading Scale` but **no Report Card doctype**.
`reports.get_report_card(student, academic_term, board)` compiles results into a
report card. The board format is **configurable** via `BOARD_TEMPLATES`
(CBSE / State / ICSE …) and `DEFAULT_BOARD` — not hard-coded. Add a board by adding
a template entry; no code change to the compile logic.

## UDISE+ export

`reports.udise_export()` returns a **placeholder** with the aggregates a school
compiles (enrolment by gender, staff, classes). It is **not** the official UDISE+
schema — it is clearly marked and must be mapped field-by-field to the government
format with the school's DISE code before any real submission.

## Notifications (SMS / WhatsApp / Email)

Frappe already has Email + Notification + SMS Settings. `notify.py` adds a thin,
provider-agnostic dispatch so any vendor can be plugged in later. For the pilot the
providers are **dummy (log-only)** — no credentials, no external calls. To go live,
replace the class in `notify.PROVIDERS[channel]` with a real vendor client.
`notify.notify_guardians(student, msg, channel)` fans out to a student's guardians.

## Trust / society accounting — OPEN QUESTION for a CA (not assumed)

Many Indian schools run under a **trust or society**, which implies **fund
accounting** (restricted vs unrestricted funds, corpus, grants, 12A/80G, FCRA for
foreign donations) that ERPNext does not model out of the box. **This is flagged as
an open question for the school's Chartered Accountant — not an assumption.** Do not
configure the chart of accounts for fund accounting without CA sign-off. Options to
discuss with the CA: cost-center/dimension-based fund tracking vs a dedicated fund
accounting layer.
