# Phase 5 — Indian School Specifics

Native-first: ERPNext/Education already cover most of this. School Suite adds only
the policies that are **not** native.

## Fees

Education v16 bills a class through **Fee Structure → Fee Schedule → one Sales
Invoice (or Sales Order) per student**, with a `student` field on the invoice. The
older `Fees` doctype still exists; School Suite supports both and counts both on
`/parent`, `/principal` and the TC.

| Item | Native? | Where |
|---|---|---|
| Term-wise fee structure | ✅ Native | `Fee Structure.academic_term` |
| Fee schedules → invoices per student | ✅ Native | `Fee Schedule` → `Sales Invoice` |
| Per-component discount | ✅ Native on invoices | `Fee Component.discount` → invoice `discount_percentage` |
| Sequential numbering | ✅ Native | invoice / `Fees` naming series |
| **Sibling discount** (auto, on new fee invoices) | ❌ Custom | `fees_policy.before_fee_validate` |
| **Scholarship / concession** | ❌ Custom helper | `fees_policy.apply_concession` |
| **Late fee** (computed, not yet posted) | ❌ Custom | `fees_policy.late_fee_amount` |
| **RTE 12(1)(c) warning** | ❌ Custom | `fees_policy.warn_if_rte` |
| Legacy Fees honouring the component discount | 🩹 Fix | `fees_policy.recompute_legacy_fee_totals` |

All policy values (sibling %, late fee per day and cap, default SAC, on/off for the
auto sibling discount) are in **School Suite Settings**.

- **Sibling discount:** birth order among *enrolled* children who share a guardian
  (date of birth when every child has one, else enrolment order). With *Auto-apply*
  on, a new fee invoice (from a Fee Schedule, or whose items are all Fee Components)
  for a younger sibling gets the configured %. Invoices that already carry a
  discount, credit notes and RTE seats are skipped. Tested: 2nd child ₹5000 → ₹4500.
- **Why the discount needs care on invoices:** ERPNext keeps a line's existing rate
  and resets `discount_percentage` to 0 unless the rate already equals list price
  minus discount, so `apply_concession` sets list price, discount and rate together.
- **Legacy Fees bug:** Education v16's `Fees.calculate_total` sums the gross amount
  and ignores the component discount, so a discounted fee was billed in full.
  School Suite recomputes the totals after the native validate (tested: 20% off
  ₹5000 → ₹4000).
- **Late fee:** `late_fee_amount(invoice)` = days overdue × per-day, capped (tested:
  100 days → ₹1000 cap). Posting it to the invoice is still to build.
- **RTE 12(1)(c) seats:** saving a fee invoice for a student flagged *Admitted under
  RTE* warns, because the State reimburses those fees. It warns rather than blocks,
  since what may be billed varies by State.
- **GST:** school education up to higher secondary is GST-exempt. Mark tuition fee
  Items exempt / nil-rated; confirm transport, uniforms and books with the CA.
  Education v16 auto-creates an Item per Fee Category with no SAC, which India
  Compliance rejects, so `default_fee_item_sac` fills the default SAC (`999220`,
  primary education) on Fee Component Items that have none.

**Receipt numbering note:** the native series is already sequential per year. If a
board/trust requires a specific format (e.g. per-branch prefixes), change the
`Fees` naming series via a Property Setter in school_suite — do not edit Education.

## Student master: India / UDISE+ fields

A collapsible **India / UDISE+ Details** section on Student (custom fields, all
optional): Admission No. (General Register), APAAR ID, PEN, Social Category
(General/SC/ST/OBC), Religion, Mother Tongue, CWSN + disability type (RPwD Act), BPL,
Admitted under RTE 12(1)(c), Previous School and its TC No. Company gets **UDISE+
School Code**. Aadhaar is deliberately **not** stored; see `data_protection.md`.

## Attendance

- Teachers mark attendance (Student Attendance Tool) and enter marks (Assessment
  Result Tool) for **their own classes only**; publishing results stays with staff.
- **Absence SMS:** a guardian alert goes out once per child per day when they are
  marked Absent *today* (back-filled registers don't text parents;
  `notify.on_attendance_submit`). The text must match a TRAI **DLT-registered
  template**; edit it in School Suite Settings.
- **75% rule:** `/principal` lists students below the *Low Attendance Threshold* in
  School Suite Settings (default 75%, the CBSE board-exam bar) for the current
  academic year.

## Transfer Certificate

Education stores date of leaving, TC number and reason on Student.
`reports.get_transfer_certificate(student)` (Principal / School Admin only) compiles
the TC data: school + UDISE code, admission no., PEN/APAAR, parents, nationality,
category, DOB in figures **and words**, date of admission, last class and subjects,
attendance, fees paid/outstanding, leaving date and reason. It returns `warnings` for
missing data and leaves conduct and promotion to the office. Outstanding dues are
shown, not blocking. For Classes I–VIII the RTE Act s.5(3) requires immediate issue.
Print it from **`/transfer-certificate?student=<ID>`** (browser print / Save as PDF).

## Report cards (board-configurable)

Education ships `Assessment Result` + `Grading Scale` but **no Report Card doctype**.
`reports.get_report_card(student, academic_term, board)` compiles results into a
report card. The board format is **configurable** via `BOARD_TEMPLATES`
(CBSE / State / ICSE …) and the *Default Board* in School Suite Settings — not
hard-coded. Print from **`/report-card?student=<ID>`**. Add a board by adding
a template entry; no code change to the compile logic. A **`CBSE 9-Point`** Grading
Scale (A1 ≥91 … D ≥33, E below 33) is created on install for Classes IX–XII.

## UDISE+ export

`reports.udise_export()` returns a **placeholder** with the aggregates a school
compiles: enrolment by class × gender, by social category, CWSN / RTE / BPL counts,
staff and classes, plus `data_gaps` (students missing PEN, APAAR, category or DOB).
The UDISE code comes from the Company. It is **not** the official UDISE+
schema — it is clearly marked and must be mapped field-by-field to the government
format with the school's DISE code before any real submission.

## Notifications (SMS / WhatsApp / Email)

Frappe already has Email + Notification + SMS Settings. `notify.py` adds a thin,
provider-agnostic dispatch on top. A channel that isn't configured only logs (no
credentials, no external calls), so the pilot is safe. WhatsApp has no native
channel: put a vendor class in `notify.PROVIDERS["whatsapp"]`.
`notify.notify_guardians(student, msg, channel)` fans out to a student's guardians.
`notify.send` is server-only (not whitelisted): with a real vendor every message costs
money and goes out under the school's sender ID. SMS uses Frappe's **SMS Settings**
(or any app's `send_sms` hook) once a gateway is set, email uses the outgoing Email
Account; until then messages are only logged.

## Trust / society accounting — OPEN QUESTION for a CA (not assumed)

Many Indian schools run under a **trust or society**, which implies **fund
accounting** (restricted vs unrestricted funds, corpus, grants, 12A/80G, FCRA for
foreign donations) that ERPNext does not model out of the box. **This is flagged as
an open question for the school's Chartered Accountant — not an assumption.** Do not
configure the chart of accounts for fund accounting without CA sign-off. Options to
discuss with the CA: cost-center/dimension-based fund tracking vs a dedicated fund
accounting layer.
