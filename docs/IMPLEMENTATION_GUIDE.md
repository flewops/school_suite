# Greenfield School — Complete Implementation Guide

**ERPNext + Frappe Education + Frappe HR + Frappe Learning (LMS) + India Compliance
+ Payments + the School Suite integration app.**

This is a full manual: it explains *what* each thing is, *why* you set it up, the
*exact* clicks and fields, and *what happens next*. Read Part 0 and Part 1 first —
they give you the mental model so the rest makes sense. Then follow Parts 2
onward **in order**, because each step depends on the ones before it.

> Written for a school administrator, not a programmer. Where a step needs the
> technical team, it says so. 🟢 marks something the **School Suite** custom app
> adds on top of standard Frappe.

---

## Part 0 — What this system is and how the pieces fit

You are running **one application** made of several Frappe "apps" that share one
database on one website:

| App | What it does for the school |
|---|---|
| **ERPNext** | The accounting + business core: company, chart of accounts, invoices, payments, HR foundation. Everything financial sits here. |
| **Frappe Education** | The school information system: students, guardians, admissions, classes, subjects, attendance, exams, fees. This is where most daily school work happens. |
| **Frappe HR (hrms)** | Staff records: employees, departments, designations, leave, payroll. Teachers are HR *Employees* who are also *Instructors* in Education. |
| **Frappe Learning (LMS)** | Online learning: digital courses, lessons, quizzes, batches, live (Zoom) classes. |
| **India Compliance** | Indian tax/GST localisation: GSTIN, HSN/SAC codes on anything you sell (including fees). |
| **Payments** | Online payment gateways (Razorpay, Stripe…) so parents can pay fees online. |
| **🟢 School Suite** | *Our* app. It ties the others together and adds what none of them do alone: a parent portal that shows both school and LMS data, a principal dashboard, role-based access (a parent sees only their child; a teacher only their class), auto-enrolment of a class into an online batch, online-mode attendance, Indian fee policies (sibling discount, concession, late fee), a report-card compiler, and notifications. It also quietly fixes a real bug in Education v16's fees. |

### The mental model (learn these 8 words and everything clicks)

- **Academic Year** — a school year, e.g. *2026-2027* (1 Apr 2026 → 31 Mar 2027).
- **Academic Term** — a part of that year, e.g. *Term 1*. Fees and exams are usually per-term.
- **Program** — a *class/grade*, e.g. *Grade 1*. A Program contains the **Courses**
  (subjects) taught in that class.
- **Course** — a *subject*, e.g. *Mathematics*.
- **Student** — a child. Each Student should have an **email** so they get a login
  (needed for the portal and the LMS). 🟢 School Suite makes the email mandatory.
- **Guardian** — a parent. A Guardian is linked to one or more Students and has
  their own login to the **Parent Portal**.
- **Program Enrollment** — the record that *admits a Student into a Program* for a
  given Year/Term. This is the official "this child is in Grade 1 this year" record.
- **Student Group** — the actual *class-section that is taught and marked together*,
  e.g. *Grade 1 - A*. It holds the list of students **and** the teacher(s). Almost
  everything day-to-day (attendance, timetable, exams, online batch) attaches to a
  Student Group.

**How a student connects to online learning:** `Student → has a User login → that
same User is the "member" in the LMS`. That shared **User account** is the bridge
between Education and the LMS, and it's how 🟢 School Suite shows a parent their
child's LMS progress next to their attendance and fees.

**How a teacher connects to their class:** `Teacher's User → an HR Employee (User
ID) → an Education Instructor (linked to that Employee) → listed in a Student
Group's Instructors table`. That chain is why 🟢 School Suite can limit a teacher
to only the classes they actually teach.

### How to read the instructions

- **"Education → Academics → Academic Year"** means: click **Education** in the
  left sidebar (the workspace switcher at the top-left), then on the Education home
  page click **Academic Year** under the **Academics** heading. You can also just
  type the name in the global search (press `/` or `Ctrl/Cmd+G`).
- On any list page, the **+ Add / + New** button is top-right. A new blank form opens.
- **Save** = the button top-right, or `Ctrl+S` (Windows) / `Cmd+S` (Mac).
- Some documents are **"submittable"** — after Save you also click **Submit** to
  finalise them (Fees, Program Enrollment, Assessment Result). A *Draft* is editable;
  a *Submitted* document is locked (you must *Cancel* then *Amend* to change it).
- A **red asterisk (\*)** means the field is mandatory.
- **Link fields** (a field that points to another record, e.g. "Program") show a
  dropdown as you type; if the value doesn't exist yet, the dropdown offers
  **"Create a new …"**.

---

## Part 1 — Before you start

### 1.1 Who does what (suggested roles)

| Person | School Suite role | Typically does |
|---|---|---|
| Owner/IT | System Manager + School Admin | Full setup, user accounts, configuration |
| Principal | Principal | Approves admissions, sees the Principal dashboard |
| Office/Accounts | Accountant | Fees, invoices, payments |
| Class teachers | Teacher | Attendance, marks, their own classes only |
| Students | Student | Their own portal + LMS |
| Parents | Parent/Guardian | The Parent Portal for their own children only |

### 1.2 The order of setup (and why)

You build from the foundation up. Each layer needs the one below it:

```
Company & financial year   (money foundation)
        ↓
Academic Year → Terms       (the calendar)
        ↓
Grading scale, Courses      (what is taught & how it's marked)
        ↓
Programs (classes)          (grouping of courses)
        ↓
Staff: Employees→Instructors, Rooms
        ↓
Students + Guardians        (the people)
        ↓
Program Enrollments         (admit students into classes)
        ↓
Student Groups              (the taught class-sections)
        ↓
Fees, Attendance, Exams, LMS, Portals   (daily operation)
```

If you try to create an Academic Term before an Academic Year, or a Program
Enrollment before the Program exists, the form will block you — that's expected.

### 1.3 Log in

Open the site (**http://localhost:8000** in the pilot; your real domain in
production). Sign in as **Administrator** with your admin password. You land on the
**Desk** (the back-office). The current site already has the company **Greenfield
School** created and is otherwise empty — a clean production start.

> **Before entering real data, rename the company to your real school name.** The
> company name is baked into every account code (e.g. *Debtors - GS*), so changing
> it later is costly. Ask the technical team to set the real name now while the
> database is empty.

---

## Part 2 — The academic calendar

### 2.1 Academic Year  *(Education → Academics → Academic Year → + New)*

**What/why:** the school year everything else hangs off. Create it first.

| Field | What to enter | Example |
|---|---|---|
| Academic Year Name \* | A label for the year | `2026-2027` |
| Year Start Date \* | First day of the year | `01-04-2026` |
| Year End Date \* | Last day | `31-03-2027` |

Click the date field → a **calendar** opens → pick the month with the ‹ › arrows →
click the day (or type the date in the shown format). **Save.**
Repeat for each year you operate.

### 2.2 Academic Term  *(Education → Academics → Academic Term → + New)*

**What/why:** the parts of the year. Most schools run 2–3 terms; fees and exams are
usually organised per term. You'll reuse the term on fee structures and assessments.

| Field | Enter | Example |
|---|---|---|
| Academic Year \* | Pick the year from 2.1 | `2026-2027` |
| Term Name \* | The term's name | `Term 1` |
| Term Start Date \* / Term End Date \* | The term's span | `01-04-2026` / `30-09-2026` |

**Save.** Create `Term 2` (and `Term 3` if used) the same way.

---

## Part 3 — What is taught and how it's graded

### 3.1 Grading Scale  *(Education → Assessment → Grading Scale → + New)*

**What/why:** maps a percentage to a grade (A1, A2 …). You must create it *before*
Courses and exams, because Courses and Assessments reference it. Make one per board
scheme you use.

1. **Name:** `CBSE Scholastic` (or your board's scheme).
2. In the **Intervals** table, add one row per grade band. Each row:
   - **Threshold** = the *minimum %* for this grade (e.g. `91`)
   - **Grade Code** = `A1`
   - **Grade Point** (optional) = `10`
   Add rows down to the lowest grade with threshold `0`.

   | Threshold | Grade Code | Grade Point |
   |---|---|---|
   | 91 | A1 | 10 |
   | 81 | A2 | 9 |
   | 71 | B1 | 8 |
   | … | … | … |
   | 0 | E | 0 |
3. **Save.**

### 3.2 Courses (subjects)  *(Education → Academics → Course → + New)*

**What/why:** each subject taught anywhere in the school is a Course. Create every
subject once; you'll attach them to classes (Programs) next.

| Field | Enter | Example |
|---|---|---|
| Course Name \* | The subject | `Mathematics` |
| Department | (optional) grouping | `Primary` |
| Default Grading Scale | From 3.1 | `CBSE Scholastic` |
| Assessment Criteria (table) | The components it's marked on | `Term Exam`, `Unit Test` |
| Description / Topics | (optional) syllabus / chapters | |

**Save.** Repeat for every subject (English, Science, Hindi, EVS, …).

> **Assessment Criteria** (`Education → Assessment → Assessment Criteria`) are the
> named components marks are entered against — create `Term Exam`, `Unit Test`,
> `Project`, etc. once, then add them to Courses.

### 3.3 Programs (classes/grades)  *(Education → Academics → Program → + New)*

**What/why:** a Program is a class/grade and the set of subjects it studies.

1. **Program Name \*** = `Grade 1`; **Program Abbreviation** = `G1`.
2. In the **Courses** table, add a row per subject that Grade 1 studies
   (`Mathematics`, `English`, …) — each links to a Course from 3.2.
3. **Save.** Repeat for every class: `Grade 2`, `Grade 3`, … up to your highest.

---

## Part 4 — Staff (teachers and others)

A teacher must exist as **two linked records**: an **HR Employee** (for HR/payroll
and the login) and an **Education Instructor** (for teaching). 🟢 School Suite uses
this link to restrict each teacher to their own classes, so don't skip it.

### 4.1 Holiday List  *(HR → Leaves → Holiday List → + New)* — do this first
Employees require a holiday list.
1. Name `School Holidays 2026-2027`; **From/To** = the academic year span.
2. **Weekly Off** = `Sunday` → click **Get Weekly Off Dates** (fills every Sunday).
3. Add festival/vacation holidays as rows. **Save.**
4. Set it as the company default: **Setup → Company → Greenfield School →
   *Default Holiday List*** → save.

### 4.2 Designations & Departments  *(HR → Employee → Designation / Department)*
Create the job titles you need: `Teacher`, `Principal`, `Accountant`, `Clerk`, and
departments like `Primary`, `Secondary`, `Administration`.

### 4.3 Employees  *(HR → Employee → Employee → + New)*
One per staff member.

| Field | Enter |
|---|---|
| Employee Name \* / First Name \* | e.g. `Sunita Rao` |
| Company \* | `Greenfield School` |
| Gender, Date of Birth \* | the staff member's |
| Date of Joining \* | their start date |
| Designation / Department | from 4.2 |
| **User ID** | the login email this person will use (create the User first if needed — Part 9) |

**Save.** The **User ID** link is important: it's how the system knows which login
is which teacher.

### 4.4 Instructors  *(Education → Setup → Instructor → + New)*
For each *teaching* employee, create an Instructor:
- **Instructor Name** = the teacher's name, **Employee** = link the Employee from
  4.3, **Department** = optional. **Save.**

### 4.5 Rooms  *(Education → Setup → Room → + New)*
Create your classrooms: **Room Name** `Room 101`, **Seating Capacity** `35`. Rooms
are used on the timetable (Course Schedule).

---

## Part 5 — Students and guardians

You can add students directly (for an existing roll) or run the **Admissions**
pipeline for new intake. Direct entry is covered here; Admissions is in Part 5.4.

### 5.1 Guardians (parents)  *(Education → Student Management → Guardian → + New)*
Create the parent first so you can link the child to them.

| Field | Enter | Notes |
|---|---|---|
| Guardian Name \* | `Meera Nair` | |
| Email Address | `meera@example.com` | used for the Parent Portal login + email alerts |
| Mobile Number | `+91…` | used for SMS/WhatsApp alerts |
| **User** | the parent's login | lets them sign in to `/parent`. Create the User (Part 9) and give it the **Parent/Guardian** role. |
| Occupation / Address | optional | |

**Save.** One Guardian can have several children; one child can have several guardians.

### 5.2 Students  *(Education → Student Management → Student → + New)*

| Field | Enter | Notes |
|---|---|---|
| First / Middle / Last Name | child's name | |
| **Student Email ID** \* | `arya@example.com` | 🟢 made mandatory by School Suite — every student needs a login for the portal + LMS |
| Date of Birth, Gender | the child's | |
| Joining Date | when they joined | |
| **Guardians** (table) | add a row: pick the Guardian (5.1) + **Relation** (Mother/Father/…) | this is what powers "a parent sees only their own child" |
| **User** | the student's login (optional now) | |
| 🟢 **Online Mode** (checkbox) | tick only for students whose attendance comes from online activity (Part 7.2) | added by School Suite |

**Save.** The child is now linked to their parent(s).

### 5.3 Student Category & Batch (optional classifiers)
- **Student Category** (`…→ Student Category`): `General`, `RTE`, `Staff Ward` — used
  later for category-wise fee concessions.
- **Student Batch Name** (`…→ Student Batch Name`): section letters `A`, `B`, `C`.

### 5.4 (Alternative) Admissions pipeline
For new-intake season: create a **Student Admission** (`Education → Admissions`) for
the drive, then **Student Applicant** records for each applicant; approving an
applicant creates the Student. Use this when you want an applications funnel; for an
existing school roll, direct entry (5.1–5.2) is faster.

---

## Part 6 — Admit students into classes, then form sections

### 6.1 Program Enrollment  *(Education → Student Management → Program Enrollment → + New)*
**What/why:** the official record that a student is *in a class for a year/term*.

| Field | Enter |
|---|---|
| Student \* | the child |
| Program \* | the class, e.g. `Grade 1` |
| Academic Year \* / Academic Term | `2026-2027` / `Term 1` |
| Enrollment Date | admission date |
| Student Category / Batch | optional (from 5.3) |
| **Courses** (table) | the subjects the student takes (usually auto-filled from the Program) |

🟢 **Admission Approval workflow (School Suite):** this document now moves through
states instead of a plain Save→Submit. After Save you'll see a **workflow action
button** (top-right):
1. A **School Admin** opens it and clicks **Apply for Approval** → state becomes
   *Pending Principal Approval*.
2. The **Principal** opens it and clicks **Approve** → state becomes *Enrolled* and
   the document is submitted (locked, active).
Only an **Enrolled** enrollment counts as an active admission. (To change your mind,
the Principal can click **Reject** to send it back to Draft.)

### 6.2 Student Groups (the taught class-sections)
**What/why:** a Student Group is the actual class you teach and mark together, e.g.
*Grade 1 - A*. It carries the **student list** and the **teacher(s)**. Attendance,
timetable, exams, and online batches all attach here.

*Fast way:* **Education → Tools → Student Group Creation Tool** — choose Program +
Academic Year (+ Batch), click **Get Students**, and it pulls everyone enrolled.
Save → it creates the Student Group populated.

*Manual way:* **Education → Student Management → Student Group → + New**
| Field | Enter |
|---|---|
| Student Group Name \* | `Grade 1 - A` |
| Academic Year \* | `2026-2027` |
| **Group Based On** \* | `Batch` (then pick the Batch) — or `Course`/`Activity` |
| Program | `Grade 1` |
| Max Strength | e.g. `35` |
| **Students** (table) | add each student (or use the tool above). Keep **Active** ticked. |
| **Instructors** (table) | add the class teacher(s) — the Instructor from 4.4 |

🟢 **Enable Online (LMS) Batch** (checkbox, added by School Suite): tick this and
Save → School Suite automatically creates a matching **LMS Batch** and enrols every
active student into it (Part 8). Leave unticked for purely offline classes.

**Save.**

---

## Part 7 — Attendance

### 7.1 Daily attendance (in person)
**Education → Attendance → Student Attendance Tool** — pick the **Student Group** and
the **date**, mark each child **Present / Absent / Leave**, and **Submit**. (You can
also create a single **Student Attendance** record manually.)

### 7.2 🟢 Online-mode attendance (School Suite)
For online/pandemic periods, tick **Online Mode** on the relevant students (5.2),
then have the technical team run, per class per day:
`school_suite.online_learning.mark_online_attendance("Grade 1 - A", "2026-07-15")`.
Each student is marked **Present** if they joined the Zoom live class (when real Zoom
credentials are configured) or, failing that, if they did any LMS activity that day;
otherwise **Absent**. See `online_mode.md` for Zoom's limits (it only reports who
joined, after the class, and only matches by email). Teachers should be able to
override the result.

---

## Part 8 — Online learning (LMS) and live classes

### 8.1 Build a course
Go to the **LMS** (the `/lms` site or the LMS workspace). Create an **LMS Course**,
add **Chapters → Lessons** (text, video, files), optional **Quizzes** and
**Assignments**, then **Publish** it so learners can see it.

### 8.2 🟢 Connect a class to an online batch (School Suite)
1. On the **Student Group** (6.2), tick **Enable Online (LMS) Batch** → Save. School
   Suite creates/links an **LMS Batch** named after the class and enrols every active
   student (matched by their User login).
2. Open that **LMS Batch** → in its **Courses** table add the LMS Course(s) for the
   class. Students are now enrolled in those courses automatically.
3. To re-sync after adding students, the technical team runs
   `school_suite.online_learning.sync_now("Grade 1 - A")`.

### 8.3 Live classes over Zoom
1. **The school provides** a **Zoom Server-to-Server OAuth app** (from the Zoom
   Marketplace) on a **paid Zoom plan**, and enters its *Account ID / Client ID /
   Client Secret* into **LMS Zoom Settings**, then ticks **Enabled**. (The pilot
   ships a *disabled placeholder* so nothing calls Zoom with fake keys.)
2. On an LMS Batch, create a **Live Class** — LMS creates the Zoom meeting and invites
   enrolled students. After the class, participation can feed attendance (7.2).
Full details and limits: `online_mode.md`.

---

## Part 9 — Logins, roles and access (School Suite)

### 9.1 The six roles (already installed)
`School Admin, Accountant, Teacher, Student, Parent/Guardian, Principal` exist out of
the box. You assign them to each person's login.

### 9.2 Create a login and assign a role  *(Settings → Users → User → + New)*
1. **Email** = the person's login, **First Name**, Save (an invite/temp password is
   set depending on your email config).
2. On the User, open the **Roles** section and tick the right role(s):
   - Parent → **Parent/Guardian** (their home becomes the `/parent` portal)
   - Teacher → **Teacher** (plus make sure their Employee→Instructor link exists, 4.3–4.4)
   - Student → **Student**
   - Office → **School Admin** / **Accountant**; head → **Principal**
3. Link the login back to the person: set this email as the **User** on the Guardian
   (5.1) or Student (5.2), or as **User ID** on the Employee (4.3).

### 9.3 What the access rules do (automatic — just verify)
🟢 School Suite enforces, on top of standard permissions:
- a **parent** sees only their own children,
- a **teacher** sees only students in their assigned Student Groups,
- a **student** sees only themselves,
- **Principal / School Admin** see everything.
To verify: log in as a parent and open the Student list — you should see only their
child. (These rules were tested and confirmed during the build.)

---

## Part 10 — Fees (term-wise, with Indian policies)

### 10.1 Fee Category  *(Education → Fee Management → Fee Category → + New)*
**What/why:** a type of fee (`Tuition`, `Transport`, `Exam`). In Education v16 each
Fee Category is backed by an ERPNext **Item**, and India Compliance requires an
**HSN/SAC** code on it.
1. **Category Name** = `Tuition`. In **Item Defaults** add a row: **Company** =
   Greenfield School, **Income Account** = e.g. `Sales - GS`. **Save** — this creates
   a linked Item named `Tuition`.
2. Open that **Item** (search `Tuition`) and set **HSN/SAC** to a valid 6/8-digit
   code (education services ≈ `999293`). Save.
3. Repeat for `Transport`, `Exam`, etc.

### 10.2 Fee Structure (one per class × term)  *(…→ Fee Structure → + New)*
**What/why:** the template of what a class pays in a term. Making it *per Academic
Term* is what gives you **term-wise fees**.

| Field | Enter |
|---|---|
| Program \* | `Grade 1` |
| Academic Year \* / **Academic Term** | `2026-2027` / `Term 1` |
| Company \* | Greenfield School |
| Receivable Account | `Debtors - GS` |
| **Components** (table) | one row per Fee Category: Category + its Item + **Amount** |

**Save → Submit.** Repeat per class and per term.

### 10.3 Raise and collect a fee  *(…→ Fees → + New)*
| Field | Enter |
|---|---|
| Student \* | the child |
| Program Enrollment | their enrollment (6.1) |
| Fee Structure | the one from 10.2 (components auto-fill) |
| Posting Date / Due Date | today / the deadline |

**Save → Submit.** The receipt number is sequential (`EDU-FEE-2026-#####`). The
balance shows as **Outstanding Amount** until paid.

### 10.4 🟢 Indian fee policies (School Suite) — applied *before* submitting a fee
The technical team can call these from a button/script or the console:
- **Sibling discount:** `fees_policy.apply_sibling_discount(fee)` — automatically
  gives a % off based on birth order among siblings who share a guardian (e.g. 2nd
  child 10%, 3rd 15%). Verified: a 3rd child's ₹5000 fee becomes ₹4250.
- **Scholarship/concession:** `fees_policy.apply_concession(fee, percent, reason)`.
- **Late fee:** `fees_policy.late_fee_amount(fee_name)` computes the overdue charge
  (per-day, capped).

### 10.5 Online payment (Razorpay)
**The school provides** its own Razorpay keys. Enter the **`rzp_test_`** (test) or
live key/secret in **Razorpay Settings**, create a **Payment Gateway Account**
(gateway *Razorpay* → company *Greenfield School* → a bank account), then raise a
**Payment Request** on a fee to generate a hosted checkout link parents can pay.
Details: `online_mode.md`.

---

## Part 11 — Exams, results and report cards

### 11.1 Assessment Plan  *(Education → Assessment → Assessment Plan → + New)*
A scheduled exam for a class: pick **Student Group**, **Course**, **Assessment
Group/Criteria**, **Maximum Score**, date/time. **Save → Submit.**

### 11.2 Assessment Result  *(Education → Assessment → Assessment Result)*
Enter marks against the plan; the **Grade** auto-computes from the Course's Grading
Scale (3.1). **Submit.** (Use the Assessment Result Tool to enter a whole group at
once.)

### 11.3 🟢 Report card (School Suite, board-configurable)
School Suite compiles report cards from Assessment Results via
`reports.get_report_card(student, academic_term, board)`. The board format
(**CBSE / State / ICSE**) is configurable — the technical team sets `DEFAULT_BOARD`
or passes a `board`. For printable PDFs per board, create a **Print Format** (listed
in `GAP_LIST.md`).

---

## Part 12 — India compliance & UDISE

- **GST:** `India Compliance → GST Settings` — set the school's GSTIN and defaults if
  registered. HSN/SAC codes ship with the app; put them on fee Items (10.1).
- **UDISE+:** 🟢 `reports.udise_export()` returns a **placeholder** aggregate
  (enrolment by gender, staff, classes). It is **not** the official UDISE+ format —
  the technical team must map it to the government schema with your DISE code before
  any real submission.

---

## Part 13 — Notifications (email / SMS / WhatsApp)

- **Email:** `Settings → Email Account` — add the school's outgoing SMTP. Then build
  alerts in `Settings → Notification` (native), e.g. "Fee due in 3 days", "Report
  card published".
- 🟢 **SMS / WhatsApp (School Suite):** a pluggable sender ships with **dummy
  providers** (they only log, no credentials) for the pilot. To go live, the
  technical team replaces the provider for a channel with a real vendor (MSG91,
  Gupshup, Twilio, Meta WhatsApp) and uses
  `notify.send(channel, to, message)` or `notify.notify_guardians(student, msg, channel)`.

---

## Part 14 — The portals and dashboards (the payoff)

- **Parent Portal — `/parent`:** a signed-in parent sees, **per child**, attendance %,
  fee dues & receipts, grades, timetable, and **online-course progress** — Education
  and LMS data combined on one page. 🟢 School Suite; shows only their own children.
- **Principal Dashboard — `/principal`:** class-wise attendance, fee collection, and
  online-course completion. 🟢 School Suite; Principal / School Admin only.
- **Student / Guardian portal (native):** `edu-portal`.

---

## Part 15 — Daily operation (quick reference once set up)

| Task | Where |
|---|---|
| Take attendance | Education → Attendance → Student Attendance Tool |
| Raise a term's fees | Education → Fee Management → Fees (from the Fee Structure) |
| Record a payment | the Fee / Payment Entry / Razorpay checkout |
| Enter exam marks | Education → Assessment → Assessment Result |
| Publish a report card | run the report-card compile for the student/term |
| Add a new admission | Program Enrollment → Apply for Approval → Principal approves |
| Message parents | Notification (email) / `notify.*` (SMS/WhatsApp) |
| Check the school at a glance | `/principal` |

---

## Part 16 — Go-live checklist

- [ ] Real school name set on the Company (before real data).
- [ ] Academic Year + Terms created.
- [ ] Grading Scale, all Courses, all Programs (with their courses).
- [ ] Staff: Holiday List set as company default, Employees created, Instructors linked.
- [ ] Rooms created.
- [ ] Students + Guardians entered and linked; emails on every student.
- [ ] Program Enrollments created and **approved** (Enrolled).
- [ ] Student Groups formed with students + class teacher.
- [ ] Fee Categories (with HSN on Items), Fee Structures per class × term.
- [ ] Logins created; each person has the correct School Suite role; a parent and a
      teacher login spot-checked for correct access.
- [ ] Email account configured; SMS/WhatsApp vendor wired in (if used).
- [ ] Razorpay keys + Payment Gateway Account (if collecting online).
- [ ] Zoom S2S app configured (if running live classes).
- [ ] Backups scheduled to S3 **and a restore test done** (`deployment.md`).
- [ ] Data-protection checklist reviewed by legal (`data_protection.md`).
- [ ] `developer_mode` off in production.

---

## Part 17 — Troubleshooting & FAQ

- **"Could not find … / field is mandatory on a link":** you're creating something
  before its prerequisite exists. Create the prerequisite first (e.g. Academic Year
  before Academic Term; Program before Program Enrollment).
- **A parent/teacher sees nothing, or sees everyone:** check (a) the User has the
  right role, and (b) the link is set — Guardian.User / Student.User / Employee.User
  ID / the Instructor is in the Student Group's Instructors table.
- **A student has no LMS progress on the parent portal:** the Student has no **User**,
  or that user isn't enrolled in the LMS batch. Set the Student's email/User and
  re-sync the group (8.2).
- **Fees won't save ("Unknown column income_account"):** already fixed — School Suite
  ships a property setter that clears Education v16's broken field reference. If you
  see it, run `bench --site <site> migrate` so the fix is applied.
- **HSN/SAC error on a fee Item:** set a valid 6- or 8-digit HSN/SAC on the Item
  (10.1).
- **Can't open the site:** the server may be stopped, or another project grabbed the
  port. Restart: `docker start devcontainer-mariadb-1 devcontainer-redis-cache-1
  devcontainer-redis-queue-1 devcontainer-frappe-1` then
  `docker exec -d devcontainer-frappe-1 bash -lc 'cd /workspace/development/frappe-bench && bench start'`.

**Companion docs:** `indian_specifics.md` (fees/report cards/UDISE/notifications),
`online_mode.md` (LMS batches, online attendance, Zoom & Razorpay setup +
limits), `deployment.md` (production image, multi-tenant, backups/restore),
`data_protection.md` (children's-data checklist), `GAP_LIST.md` (what's done vs. the
remaining build/buy/skip work with effort estimates).
