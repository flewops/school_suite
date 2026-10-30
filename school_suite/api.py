"""Whitelisted API for the parent portal and the unified / principal dashboards.

Education data (attendance, grades, fees, timetable, programme courses) and LMS
data (enrolments, progress, quiz scores, assignments) are joined on the User
account: `Student.user` == LMS `member`.

Every endpoint re-checks authorisation server-side; it never trusts the caller
to pass a student they are allowed to see.
"""

import frappe
from frappe import _

from school_suite.permissions import (
    _allowed_students,
    get_guardian,
    get_student,
    _roles,
    FULL_ACCESS_ROLES,
)


def _assert_can_view_student(student):
    user = frappe.session.user
    if _roles(user) & FULL_ACCESS_ROLES:
        return
    if "Accountant" in _roles(user):
        return
    if student not in _allowed_students(user):
        frappe.throw(_("You are not permitted to view this student."), frappe.PermissionError)


def _student_user(student):
    return frappe.db.get_value("Student", student, "user")


# --------------------------------------------------------------------------- #
# Parent portal
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def get_my_children():
    """Students linked to the logged-in guardian, with a light summary each."""
    guardian = get_guardian()
    if not guardian:
        return []
    student_names = frappe.get_all(
        "Student Guardian",
        filters={"guardian": guardian, "parenttype": "Student"},
        pluck="parent",
    )
    out = []
    for s in student_names:
        doc = frappe.db.get_value(
            "Student", s, ["name", "student_name", "image", "user"], as_dict=True
        )
        if doc:
            doc["attendance"] = get_attendance_summary(s)
            doc["fees"] = get_fee_summary(s)
            out.append(doc)
    return out


# --------------------------------------------------------------------------- #
# Per-student building blocks
# --------------------------------------------------------------------------- #
def get_attendance_summary(student):
    # v16 forbids raw SQL aggregates in get_all field strings; count in Python.
    from collections import Counter
    statuses = frappe.get_all(
        "Student Attendance",
        filters={"student": student, "docstatus": 1},
        pluck="status",
    )
    counts = Counter(statuses)
    present = counts.get("Present", 0)
    total = len(statuses)
    pct = round(present * 100.0 / total, 1) if total else None
    return {"present": present, "absent": counts.get("Absent", 0),
            "leave": counts.get("Leave", 0), "total": total, "percentage": pct}


def get_fee_summary(student):
    rows = frappe.get_all(
        "Fees",
        filters={"student": student, "docstatus": ["<", 2]},
        fields=["grand_total", "outstanding_amount"],
    )
    billed = sum(r.grand_total or 0 for r in rows)
    outstanding = sum(r.outstanding_amount or 0 for r in rows)
    return {"billed": billed, "outstanding": outstanding, "paid": billed - outstanding,
            "invoice_count": len(rows)}


def get_grades(student):
    return frappe.get_all(
        "Assessment Result",
        filters={"student": student, "docstatus": 1},
        fields=["name", "course", "assessment_group", "grade",
                "total_score", "maximum_score", "academic_term"],
        order_by="creation desc",
    )


def get_timetable(student):
    groups = frappe.get_all(
        "Student Group Student", filters={"student": student}, pluck="parent"
    )
    if not groups:
        return []
    return frappe.get_all(
        "Course Schedule",
        filters={"student_group": ["in", groups]},
        fields=["name", "course", "student_group", "instructor_name",
                "schedule_date", "from_time", "to_time", "room", "title"],
        order_by="schedule_date desc, from_time asc",
        limit=50,
    )


def get_education_courses(student):
    enrollments = frappe.get_all(
        "Program Enrollment",
        filters={"student": student, "docstatus": 1},
        fields=["name", "program", "academic_year", "academic_term"],
    )
    for e in enrollments:
        e["courses"] = frappe.get_all(
            "Program Enrollment Course", filters={"parent": e.name}, pluck="course"
        )
    return enrollments


def get_lms_progress(student):
    """LMS data for the student's linked user account."""
    user = _student_user(student)
    if not user:
        return {"linked_user": None, "enrollments": [], "quizzes": [],
                "certificates": [], "assignments": []}
    enrollments = frappe.get_all(
        "LMS Enrollment",
        filters={"member": user},
        fields=["course", "progress", "current_lesson", "enrollment_from_batch"],
    )
    for e in enrollments:
        e["course_title"] = frappe.db.get_value("LMS Course", e.course, "title")
    quizzes = frappe.get_all(
        "LMS Quiz Submission",
        filters={"member": user},
        fields=["quiz_title", "course", "score", "score_out_of", "percentage"],
        order_by="creation desc",
    )
    certificates = frappe.get_all(
        "LMS Certificate",
        filters={"member": user},
        fields=["course_title", "issue_date", "expiry_date"],
    )
    assignments = frappe.get_all(
        "LMS Assignment Submission",
        filters={"member": user},
        fields=["assignment_title", "course", "status"],
        order_by="creation desc",
    )
    return {"linked_user": user, "enrollments": enrollments, "quizzes": quizzes,
            "certificates": certificates, "assignments": assignments}


@frappe.whitelist()
def get_student_dashboard(student):
    """Unified Education + LMS view for one student (authorisation enforced)."""
    _assert_can_view_student(student)
    base = frappe.db.get_value(
        "Student", student, ["name", "student_name", "image", "user"], as_dict=True
    )
    if not base:
        frappe.throw(_("Student not found"))
    base.update({
        "attendance": get_attendance_summary(student),
        "fees": get_fee_summary(student),
        "grades": get_grades(student),
        "timetable": get_timetable(student),
        "education_courses": get_education_courses(student),
        "lms": get_lms_progress(student),
    })
    return base


# --------------------------------------------------------------------------- #
# Principal dashboard
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def get_principal_dashboard(academic_year=None):
    if not (_roles() & FULL_ACCESS_ROLES):
        frappe.throw(_("Only Principal / School Admin may view this."), frappe.PermissionError)

    # Class-wise attendance (grouped by student group)
    att = frappe.db.sql(
        """
        select sa.student_group as `group`,
               sum(sa.status='Present') as present,
               count(sa.name) as total
        from `tabStudent Attendance` sa
        where sa.docstatus=1 and sa.student_group is not null
        group by sa.student_group
        """,
        as_dict=True,
    )
    for a in att:
        a["percentage"] = round((a["present"] or 0) * 100.0 / a["total"], 1) if a["total"] else None

    # Fee collection
    fee = frappe.db.sql(
        """
        select ifnull(sum(grand_total),0) as billed,
               ifnull(sum(grand_total-outstanding_amount),0) as collected,
               ifnull(sum(outstanding_amount),0) as outstanding
        from `tabFees` where docstatus < 2
        """,
        as_dict=True,
    )[0]

    # Course completion (LMS) — avg progress per course
    completion = frappe.db.sql(
        """
        select e.course, c.title as course_title,
               count(e.name) as learners,
               round(avg(e.progress),1) as avg_progress
        from `tabLMS Enrollment` e
        left join `tabLMS Course` c on c.name=e.course
        group by e.course
        order by learners desc
        """,
        as_dict=True,
    )

    totals = {
        "students": frappe.db.count("Student", {"enabled": 1}),
        "guardians": frappe.db.count("Guardian"),
        "student_groups": frappe.db.count("Student Group", {"disabled": 0}),
        "lms_courses": frappe.db.count("LMS Course"),
    }
    return {"totals": totals, "attendance_by_group": att,
            "fee_collection": fee, "course_completion": completion}
