"""Phase 5 — report cards (board-configurable) and a UDISE-style export stub.

Education ships Assessment Result + Grading Scale natively but has NO Report Card
doctype, so we compile one. The board format (CBSE / State / ICSE ...) is kept
*configurable* rather than hard-coded — pass `board` or set a default below.
The UDISE+ export is a deliberate PLACEHOLDER (shape only), per the brief.
The Transfer Certificate compile builds on Education's native leaving fields.
"""

from collections import Counter

import frappe
from frappe import _
from frappe.utils import flt, fmt_money, getdate

from school_suite.api import _assert_can_view_student, get_attendance_summary, get_fee_summary
from school_suite.permissions import FULL_ACCESS_ROLES, _roles
from school_suite.school_suite.doctype.school_suite_settings.school_suite_settings import get_settings

# Which fields a report card shows per board — left configurable, not prescriptive.
BOARD_TEMPLATES = {
	"CBSE": {"scale": "grade", "shows": ["grade", "marks"], "co_scholastic": True},
	"State": {"scale": "marks", "shows": ["marks", "percentage"], "co_scholastic": False},
	"ICSE": {"scale": "marks", "shows": ["marks", "grade"], "co_scholastic": True},
}


@frappe.whitelist()
def get_report_card(student: str, academic_term: str | None = None, board: str | None = None):
	"""Compile a student's assessment results into a board-formatted report card."""
	_assert_can_view_student(student)
	board = board if board in BOARD_TEMPLATES else get_settings().default_board or "CBSE"
	template = BOARD_TEMPLATES.get(board, BOARD_TEMPLATES["CBSE"])

	filters = {"student": student, "docstatus": 1}
	if academic_term:
		filters["academic_term"] = academic_term

	results = frappe.get_all(
		"Assessment Result",
		filters=filters,
		fields=["course", "assessment_group", "grade", "total_score", "maximum_score", "academic_term"],
		order_by="course",
	)
	subjects, total, max_total = [], 0.0, 0.0
	for r in results:
		pct = (flt(r.total_score) * 100.0 / flt(r.maximum_score)) if r.maximum_score else None
		subjects.append(
			{
				"course": r.course,
				"assessment": r.assessment_group,
				"marks": r.total_score,
				"max": r.maximum_score,
				"percentage": round(pct, 1) if pct is not None else None,
				"grade": r.grade,
				"term": r.academic_term,
			}
		)
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
def udise_export(academic_year: str | None = None):
	"""PLACEHOLDER UDISE+ style export (shape only — not the official schema).

	The real UDISE+ return has a fixed government format and must be mapped field
	by field with a school's UDISE code. This compiles the dimensions UDISE+ asks
	for (class x gender, social category, CWSN, RTE, BPL) from the Student master,
	and lists which students are missing the identifiers UDISE+ needs.
	"""
	if not (_roles() & FULL_ACCESS_ROLES):
		frappe.throw(_("Only Principal / School Admin may export UDISE data."), frappe.PermissionError)

	academic_year = academic_year or frappe.db.get_single_value("Education Settings", "current_academic_year")
	company = frappe.defaults.get_global_default("company")
	students = frappe.get_all(
		"Student",
		filters={"enabled": 1},
		fields=[
			"name",
			"gender",
			"date_of_birth",
			"social_category",
			"is_cwsn",
			"rte_admission",
			"is_bpl",
			"pen",
			"apaar_id",
		],
	)

	enr_filters = {"docstatus": 1}
	if academic_year:
		enr_filters["academic_year"] = academic_year
	class_of = {
		e.student: e.program
		for e in frappe.get_all(
			"Program Enrollment",
			filters=enr_filters,
			fields=["student", "program"],
			order_by="enrollment_date asc, creation asc",  # latest enrolment wins
		)
	}

	by_gender, by_category, by_class = Counter(), Counter(), {}
	missing = {"pen": [], "apaar_id": [], "social_category": [], "date_of_birth": []}
	for s in students:
		gender = s.gender or "Unknown"
		by_gender[gender] += 1
		by_category[s.social_category or "Not recorded"] += 1
		by_class.setdefault(class_of.get(s.name, "Not enrolled"), Counter())[gender] += 1
		for field, names in missing.items():
			if not s.get(field):
				names.append(s.name)

	udise_code = frappe.db.get_value("Company", company, "udise_code") if company else None
	return {
		"_placeholder": True,
		"_note": "Not the official UDISE+ schema. Map to the government format with "
		"the school's UDISE code before any real submission.",
		"school": {
			"name": company,
			"udise_code": udise_code or "SET_UDISE_CODE_ON_COMPANY",
			"academic_year": academic_year,
		},
		"enrolment": {
			"total_students": len(students),
			"by_gender": dict(by_gender),
			"by_social_category": dict(by_category),
			"by_class_and_gender": {k: dict(v) for k, v in sorted(by_class.items())},
			"cwsn": sum(1 for s in students if s.is_cwsn),
			"rte_12_1_c": sum(1 for s in students if s.rte_admission),
			"bpl": sum(1 for s in students if s.is_bpl),
		},
		"staff": {"total_instructors": frappe.db.count("Instructor")},
		"classes": frappe.db.count("Student Group", {"disabled": 0}),
		"data_gaps": {field: names for field, names in missing.items() if names},
	}


def get_school_header():
	"""Name, logo and UDISE code for printed certificates."""
	company = frappe.defaults.get_global_default("company")
	return {
		"name": company,
		"udise_code": frappe.db.get_value("Company", company, "udise_code") if company else None,
		"logo": frappe.db.get_single_value("Education Settings", "school_college_logo"),
	}


# --------------------------------------------------------------------------- #
# Transfer Certificate (School Leaving Certificate)
# --------------------------------------------------------------------------- #
def _date_in_words(d):
	"""2015-03-15 -> 'Fifteenth March Two Thousand Fifteen' (as TCs require)."""
	from num2words import num2words

	d = getdate(d)
	year = num2words(d.year).replace("-", " ").replace(" and ", " ")
	return f"{num2words(d.day, to='ordinal').replace('-', ' ')} {d.strftime('%B')} {year}".title()


@frappe.whitelist()
def get_transfer_certificate(student: str):
	"""Compile the data for a Transfer Certificate.

	Native Education already stores date_of_leaving, leaving_certificate_number and
	reason_for_leaving on Student; this joins them with the admission record, the
	last class studied, attendance and dues. `warnings` lists what the office must
	complete before printing; `manual_fields` are judgement calls the software does
	not make (conduct, promotion).
	"""
	if not (_roles() & FULL_ACCESS_ROLES):
		frappe.throw(
			_("Only Principal / School Admin may issue a Transfer Certificate."), frappe.PermissionError
		)

	s = frappe.get_doc("Student", student)
	parents = {}
	for g in s.guardians:
		parents.setdefault(g.relation or "Others", g.guardian_name)

	last = frappe.get_all(
		"Program Enrollment",
		filters={"student": student, "docstatus": 1},
		fields=["name", "program", "academic_year", "enrollment_date"],
		order_by="enrollment_date desc, creation desc",
		limit=1,
	)
	last = last[0] if last else None
	subjects = (
		frappe.get_all("Program Enrollment Course", filters={"parent": last.name}, pluck="course_name")
		if last
		else []
	)

	company = frappe.defaults.get_global_default("company")
	fees = get_fee_summary(student)

	warnings = []
	for field, label in [
		("date_of_leaving", _("Date of leaving")),
		("leaving_certificate_number", _("TC number")),
		("date_of_birth", _("Date of birth")),
		("admission_number", _("Admission number")),
	]:
		if not s.get(field):
			warnings.append(_("{0} is not set on the Student record.").format(label))
	if not last:
		warnings.append(_("No submitted Program Enrollment, so the last class is unknown."))
	if flt(fees["outstanding"]) > 0:
		warnings.append(
			_(
				"Fees outstanding: {0}. For Classes I-VIII the RTE Act s.5(3) requires the TC "
				"to be issued immediately; do not withhold it over dues without legal advice."
			).format(fmt_money(fees["outstanding"], currency="INR"))
		)

	return {
		"school": {
			"name": company,
			"udise_code": frappe.db.get_value("Company", company, "udise_code") if company else None,
		},
		"tc_number": s.leaving_certificate_number,
		"admission_number": s.get("admission_number"),
		"pen": s.get("pen"),
		"apaar_id": s.get("apaar_id"),
		"student_name": s.student_name,
		"father_name": parents.get("Father"),
		"mother_name": parents.get("Mother"),
		"guardian_name": parents.get("Others"),
		"nationality": s.nationality,
		"social_category": s.get("social_category"),
		"date_of_birth": s.date_of_birth,
		"date_of_birth_in_words": _date_in_words(s.date_of_birth) if s.date_of_birth else None,
		"date_of_admission": s.joining_date,
		"class_last_studied": last.program if last else None,
		"academic_year": last.academic_year if last else None,
		"subjects_studied": subjects,
		"attendance": get_attendance_summary(student),
		"fees_paid": fees["paid"],
		"fees_outstanding": fees["outstanding"],
		"date_of_leaving": s.date_of_leaving,
		"reason_for_leaving": s.reason_for_leaving,
		"manual_fields": [
			_("Whether qualified for promotion to a higher class"),
			_("General conduct"),
			_("Any fee concession availed"),
			_("Games / extra-curricular activities"),
			_("Remarks"),
		],
		"warnings": warnings,
		"issued_on": frappe.utils.nowdate(),
	}
