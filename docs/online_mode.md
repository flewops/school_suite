# Phase 4 — Online / Pandemic Mode

How School Suite ties Education classes to LMS batches, runs online classes, and
derives attendance from online activity. **What the school must provide is called
out explicitly.**

## 1. Batch ↔ class mapping and auto-enrolment

- Tick **Enable Online (LMS) Batch** on a *Student Group* (Education class/section).
  On save, `school_suite.online_learning.on_student_group_update` enqueues a sync.
- The sync (`sync_student_group`) creates/links an **LMS Batch** (reverse-linked via
  the `student_group` custom field), then enrols every *active* student into the
  batch and into each of the batch's courses — matched by the student's linked
  **User** account (`Student.user`).
- Students with no linked User are reported in `skipped_no_user` (they cannot access
  the LMS until a User is created and linked).
- Manual trigger: `school_suite.online_learning.sync_now(student_group)` (whitelisted).

**School must provide:** an LMS Course per subject you want online, added to the
batch's *Courses* table. (Mapping an Education *Course* to an *LMS Course* is a
content decision; the demo attaches "Fractions Basics".)

## 2. Live classes (Zoom)

LMS has native Zoom support. Our setup ships a **disabled** `LMS Zoom Settings`
row with obvious placeholder credentials so no call is ever made with fake keys.

**School must provide — a Zoom Server-to-Server OAuth app:**
1. In the Zoom Marketplace, create a **Server-to-Server OAuth** app.
2. Copy its **Account ID**, **Client ID**, **Client Secret** into `LMS Zoom Settings`
   and set **Enabled**. Replace the `PLACEHOLDER - School Zoom` row.
3. Grant the app scopes for meetings and reports (`meeting:write`, `meeting:read`,
   and a report/dashboard read scope for attendance).
4. Requires a **paid Zoom plan** (reporting APIs are not on free plans).

With real creds, creating an **LMS Live Class** on the batch calls
`POST /v2/users/me/meetings` and stores the join URL; LMS invites the enrolled
learners. (With the placeholder disabled, live-class creation is intentionally
not exercised.)

## 3. "Online mode" attendance

Custom field **Student.online_mode** marks a student as learning online.
`mark_online_attendance(student_group, date)` derives Student Attendance from two
signals, in priority order:

1. **Zoom participation (authoritative).** If a finished live class for the mapped
   batch exists on that date *and* real Zoom creds are set, we read
   `GET /v2/past_meetings/{uuid}/participants` (via LMS's own `get_attendance`) and
   mark Present anyone whose participant e-mail matches a student's e-mail/User.
2. **LMS activity (fallback, works with no external creds).** Otherwise, Present if
   the student's User shows LMS activity that day — an `LMS Course Progress` update
   or an `LMS Quiz Submission`.

Everyone else that day is marked **Absent**. The function reports which `source`
it used. Already-recorded days are skipped (never double-marked).

### Limits of the Zoom attendance signal (read before relying on it)

`zoom_attendance_limits()` returns this machine-readable; in prose:

- **Post-hoc only.** `past_meetings/participants` is available *after* the meeting
  ends — not real-time. Attendance can only be computed once class is over.
- **Paid plan + scopes.** Needs a paid Zoom account and report/dashboard scopes on
  the S2S app; otherwise the call 4xxs.
- **Email matching is unreliable.** `user_email` is populated only for participants
  signed into a Zoom account whose email is visible. Guests who join by name only
  have **no email**, so email→Student matching silently misses them. Name matching
  is fuzzy and not implemented.
- **Rejoins split rows.** A participant who drops and rejoins appears as multiple
  rows; you must de-duplicate and sum durations.
- **Zoom has no "present/absent".** It reports join/leave/duration. You must choose
  a minimum-duration threshold to call it "present" — a policy decision, not data.
- **UUID encoding / recurrence.** Meeting UUIDs may contain `/` and must be
  URL-encoded (LMS handles this); recurring meetings have a UUID per occurrence.
- **Rate limits & retention.** Report APIs are rate-limited and retain participant
  data only for a limited window.

**Recommendation:** use Zoom participation as the primary signal when available,
fall back to LMS activity, and **always let a teacher override** the derived marks.

## 4. Fee payment (Razorpay, TEST mode)

- The Education **Fees** doc books a receivable against the student's Customer.
  (Note: a v16 Education bug — `Fees.income_account` fetched a dropped
  `Fee Structure.income_account` field — is fixed by a Property Setter shipped in
  `school_suite` fixtures.)
- Setup ships a **Razorpay Settings** row with placeholder keys; saving it creates
  the "Razorpay" Payment Gateway record.

**School must provide — to take a real test payment:**
1. Enter the school's own **`rzp_test_` key and secret** in *Razorpay Settings*.
2. Create a **Payment Gateway Account** linking the *Razorpay* gateway to *Demo
   School* and a bank account.
3. A fee's Payment Request can then generate a hosted Razorpay checkout URL. Without
   real test keys, the balance is tracked but no checkout link can be generated.

## Verified end-to-end flow

`bench --site school.localhost execute school_suite.setup.flow_test.run` runs, for a
new student "Diya": admission (Draft→Enrolled via the Admission Approval workflow) →
fee (₹5000 outstanding) → Razorpay gateway configured → timetable → quiz →
online-mode attendance (Present from quiz activity) → unified report. All 10 steps
pass locally; the only parts needing the school's own credentials are the real Zoom
meeting and the real Razorpay charge, as documented above.
