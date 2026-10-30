"""Phase 5 — report cards (board-configurable) and a UDISE-style export stub.

Education ships Assessment Result + Grading Scale natively but has NO Report Card
doctype, so we compile one. The board format (CBSE / State / ICSE ...) is kept
*configurable* rather than hard-coded — pass `board` or set a default below.
The UDISE+ export is a deliberate PLACEHOLDER (shape only), per the brief.
"""

import frappe
from frappe.utils import flt

from school_suite.api import _assert_can_view_student

DEFAULT_BOARD = "CBSE"  # configurable per school (CBSE | State | ICSE | IB ...)

# Which fields a report card shows per board — left configurable, not prescriptive.
BOARD_TEMPLATES = {
    "CBSE": {"scale": "grade", "shows": ["grade", "marks"], "co_scholastic": True},
    "State": {"scale": "marks", "shows": ["marks", "percentage"], "co_scholastic": False},
    "ICSE": {"scale": "marks", "shows": ["marks", "grade"], "co_scholastic": True},
}


@frappe.whitelist()
def get_report_card(student, academic_term=None, board=None):
    """Compile a student's assessment results into a board-formatted report card."""
    _assert_can_view_student(student)
    board = board or DEFAULT_BOARD
    template = BOARD_TEMPLATES.get(board, BOARD_TEMPLATES[DEFAULT_BOARD])

    filters = {"student": student, "docstatus": 1}
    if academic_term:
        filters["academic_term"] = academic_term

    results = frappe.get_all(
        "Assessment Result", filters=filters,
        fields=["course", "assessment_group", "grade", "total_score",
                "maximum_score", "academic_term"],
        order_by="course",
    )
    subjects, total, max_total = [], 0.0, 0.0
    for r in results:
        pct = (flt(r.total_score) * 100.0 / flt(r.maximum_score)) if r.maximum_score else None
        subjects.append({"course": r.course, "assessment": r.assessment_group,
                         "marks": r.total_score, "max": r.maximum_score,
                         "percentage": round(pct, 1) if pct is not None else None,
                         "grade": r.grade, "term": r.academic_term})
        total += flt(r.total_score)
        max_total += flt(r.maximum_score)

    overall_pct = round(total * 100.0 / max_total, 1) if max_total else None
    return {
        "student": frappe.db.get_value("Student", student, "student_name"),
        "student_id": student,
        "board": board,
        "template": template,
        "academic_term": academic_term or "All",
        "subjects": subjects,
        "overall": {"marks": total, "max": max_total, "percentage": overall_pct},
        "generated_on": frappe.utils.nowdate(),
    }


@frappe.whitelist()
def udise_export(academic_year=None):
    """PLACEHOLDER UDISE+ style export (shape only — not the official schema).

    The real UDISE+ return has a fixed government format and must be mapped field
    by field with a school's DISE code. This returns the kind of aggregate data a
    school would compile, clearly marked as a placeholder for later mapping.
    """
    from school_suite.permissions import _roles, FULL_ACCESS_ROLES
    if not (_roles() & FULL_ACCESS_ROLES):
        frappe.throw("Only Principal / School Admin may export UDISE data.", frappe.PermissionError)

    students = frappe.get_all("Student", filters={"enabled": 1},
                              fields=["name", "gender", "date_of_birth"])
    by_gender = {}
    for s in students:
        by_gender[s.gender or "Unknown"] = by_gender.get(s.gender or "Unknown", 0) + 1

    return {
        "_placeholder": True,
        "_note": "Not the official UDISE+ schema. Map to the government format with "
                 "the school's DISE code before any real submission.",
        "school": {"name": frappe.defaults.get_global_default("company"),
                   "dise_code": "REPLACE_WITH_DISE_CODE",
                   "academic_year": academic_year or "2026-2027"},
        "enrolment": {"total_students": len(students), "by_gender": by_gender},
        "staff": {"total_instructors": frappe.db.count("Instructor")},
        "classes": frappe.db.count("Student Group", {"disabled": 0}),
    }
