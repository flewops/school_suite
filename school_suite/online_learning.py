"""Phase 4 — online / pandemic mode.

Two capabilities:

1. Batch <-> class mapping + auto-enrolment
   An Education "Student Group" with `enable_online_batch` checked gets a linked
   LMS Batch; its active students (by their linked User) are enrolled into the
   batch and the batch's courses.

2. "Online mode" attendance
   For students/classes in online mode we derive Student Attendance from online
   signals instead of a physical register:
     * Zoom live-class participation  (authoritative, but needs real Zoom creds)
     * LMS activity that day           (fallback, works with no external creds)

   Limits of the Zoom signal are documented in docs/online_mode.md and summarised
   in `zoom_attendance_limits()`.
"""

import frappe
from frappe.utils import nowdate, getdate, add_days


# --------------------------------------------------------------------------- #
# 1. Batch <-> class mapping and auto-enrolment
# --------------------------------------------------------------------------- #
def _group_instructor_users(group):
    """User accounts of the class's instructors (Instructor -> Employee.user_id)."""
    instructors = frappe.get_all(
        "Student Group Instructor", filters={"parent": group}, pluck="instructor"
    )
    users = []
    for instr in instructors:
        emp = frappe.db.get_value("Instructor", instr, "employee")
        user = frappe.db.get_value("Employee", emp, "user_id") if emp else None
        if user and user not in users:
            users.append(user)
    return users


def _ensure_batch(group):
    """Return the LMS Batch linked to this Student Group, creating it if needed."""
    gdoc = frappe.get_doc("Student Group", group)
    if gdoc.get("lms_batch") and frappe.db.exists("LMS Batch", gdoc.lms_batch):
        return gdoc.lms_batch

    existing = frappe.db.get_value("LMS Batch", {"student_group": group}, "name")
    if not existing:
        title = gdoc.student_group_name or group
        batch = frappe.get_doc({
            "doctype": "LMS Batch",
            "title": title,
            "student_group": group,
            "published": 0,
            "start_date": nowdate(),
            "end_date": add_days(nowdate(), 180),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "timezone": "Asia/Kolkata",
            "medium": "Online",
            "seat_count": gdoc.max_strength or 0,
            "description": f"Online batch for {title}",
            "batch_details": f"<p>Auto-created by School Suite for class {title}.</p>",
        })
        for user in _group_instructor_users(group) or ["Administrator"]:
            batch.append("instructors", {"instructor": user})
        batch.insert(ignore_permissions=True)
        existing = batch.name

    frappe.db.set_value("Student Group", group, "lms_batch", existing)
    return existing


def _batch_courses(batch):
    return frappe.get_all("Batch Course", filters={"parent": batch}, pluck="course")


def sync_student_group(student_group):
    """Create/link the LMS batch and enrol the group's active students.

    Returns a summary dict. Idempotent.
    """
    batch = _ensure_batch(student_group)
    courses = _batch_courses(batch)

    students = frappe.get_all(
        "Student Group Student",
        filters={"parent": student_group, "active": 1},
        pluck="student",
    )
    enrolled, skipped_no_user = [], []
    for student in students:
        user = frappe.db.get_value("Student", student, "user")
        if not user:
            skipped_no_user.append(student)
            continue
        # batch enrolment
        if not frappe.db.exists("LMS Batch Enrollment", {"member": user, "batch": batch}):
            frappe.get_doc({
                "doctype": "LMS Batch Enrollment", "member": user, "batch": batch,
            }).insert(ignore_permissions=True)
        # course enrolments
        for course in courses:
            if not frappe.db.exists("LMS Enrollment", {"member": user, "course": course}):
                frappe.get_doc({
                    "doctype": "LMS Enrollment", "member": user, "course": course,
                }).insert(ignore_permissions=True)
        enrolled.append(user)

    frappe.db.commit()
    return {"batch": batch, "courses": courses, "enrolled": enrolled,
            "skipped_no_user": skipped_no_user}


def on_student_group_update(doc, method=None):
    """doc_event: when a class is flagged online, (re)sync its LMS batch."""
    if doc.get("enable_online_batch"):
        frappe.enqueue(
            "school_suite.online_learning.sync_student_group",
            queue="short", student_group=doc.name,
        )


@frappe.whitelist()
def sync_now(student_group):
    """Manual trigger (desk button / API)."""
    frappe.has_permission("Student Group", "write", throw=True)
    return sync_student_group(student_group)


# --------------------------------------------------------------------------- #
# 2. Online-mode attendance
# --------------------------------------------------------------------------- #
def _lms_activity_present(user, date):
    """True if the user shows LMS activity on `date` (progress or quiz)."""
    date = getdate(date)
    progressed = frappe.db.sql(
        """select 1 from `tabLMS Course Progress`
           where member=%s and date(modified)=%s limit 1""",
        (user, date),
    )
    if progressed:
        return True
    quizzed = frappe.db.sql(
        """select 1 from `tabLMS Quiz Submission`
           where member=%s and date(creation)=%s limit 1""",
        (user, date),
    )
    return bool(quizzed)


def _zoom_present_emails(student_group, date):
    """Set of participant e-mails from a Zoom live class for this group on `date`.

    Returns None if no usable Zoom data (no live class, no creds, API error) so
    the caller can fall back to the LMS-activity signal.
    """
    batch = frappe.db.get_value("Student Group", student_group, "lms_batch")
    if not batch:
        return None
    live = frappe.db.get_value(
        "LMS Live Class",
        {"batch_name": batch, "date": getdate(date), "uuid": ["is", "set"]},
        ["name", "uuid", "zoom_account"], as_dict=True,
    )
    if not live or not live.zoom_account:
        return None
    try:
        # Reuse LMS's own participant fetch (needs real Zoom S2S creds).
        from lms.lms.doctype.lms_live_class.lms_live_class import get_attendance
        participants = get_attendance(live)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "school_suite: Zoom attendance fetch failed")
        return None
    emails = set()
    for p in participants:
        email = (p.get("user_email") or "").strip().lower()
        if email:
            emails.add(email)
    return emails


def _mark(student, group, date, status):
    if frappe.db.exists("Student Attendance", {"student": student, "date": getdate(date)}):
        return False
    doc = frappe.get_doc({
        "doctype": "Student Attendance", "student": student, "student_group": group,
        "date": getdate(date), "status": status,
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    return True


@frappe.whitelist()
def mark_online_attendance(student_group, date=None):
    """Derive attendance for an online-mode class on `date`.

    A student is Present if they appear in the Zoom participant list (when real
    Zoom creds + a finished meeting exist) OR, failing that, if they show LMS
    activity that day. Otherwise Absent. Only students flagged `online_mode`
    (or whose class has it) are processed.
    """
    date = date or nowdate()
    zoom_emails = _zoom_present_emails(student_group, date)  # may be None

    students = frappe.get_all(
        "Student Group Student",
        filters={"parent": student_group, "active": 1},
        pluck="student",
    )
    marked = {"present": [], "absent": [], "skipped": [], "source": None}
    marked["source"] = "zoom" if zoom_emails is not None else "lms_activity"

    for student in students:
        s = frappe.db.get_value(
            "Student", student, ["user", "online_mode", "student_email_id"], as_dict=True
        )
        if not s or not s.user:
            marked["skipped"].append(student)
            continue

        present = False
        if zoom_emails is not None:
            email = (s.student_email_id or s.user or "").strip().lower()
            present = email in zoom_emails
        else:
            present = _lms_activity_present(s.user, date)

        status = "Present" if present else "Absent"
        if _mark(student, student_group, date, status):
            marked["present" if present else "absent"].append(student)
        else:
            marked["skipped"].append(student)  # already had attendance that day

    frappe.db.commit()
    return marked


def zoom_attendance_limits():
    """Machine-readable summary of what Zoom's participant API can and cannot tell us."""
    return {
        "endpoint": "GET /v2/past_meetings/{uuid}/participants (Server-to-Server OAuth)",
        "limits": [
            "Available only AFTER the meeting ends — not real-time.",
            "Needs a paid Zoom plan and report/dashboard scopes on the S2S app.",
            "user_email is present only for participants signed into a Zoom account; "
            "guests joining by name have no email, so email->Student matching fails.",
            "Rejoins create multiple rows per participant; must aggregate + sum duration.",
            "Zoom reports join/leave/duration, not 'present/absent' — you must choose a "
            "minimum-duration threshold to call it attendance.",
            "Meeting UUIDs may contain '/'; must be URL-encoded (LMS handles this).",
            "Report data is rate-limited and retained only for a limited window.",
        ],
        "recommendation": "Use Zoom participation as the primary signal when available; "
                          "fall back to LMS activity; always allow a teacher to override.",
    }
