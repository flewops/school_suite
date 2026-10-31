"""Whitelisted API for the parent portal and the unified / principal dashboards.

Education data (attendance, grades, fees, timetable, programme courses) and LMS
data (enrolments, progress, quiz scores, assignments) are joined on the User
account: `Student.user` == LMS `member`.

Every endpoint re-checks authorisation server-side; it never trusts the caller
to pass a student they are allowed to see.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, format_time

from school_suite.permissions import (
	FULL_ACCESS_ROLES,
	_allowed_students,
	_roles,
	get_guardian,
	get_student,
)
from school_suite.school_suite.doctype.school_suite_settings.school_suite_settings import get_settings


def _assert_can_view_student(student):
	user = frappe.session.user
	if _roles(user) & FULL_ACCESS_ROLES:
		return
	# Accountants bill from the desk; they don't need a child's grades or attendance.
	if student not in _allowed_students(user):
		frappe.throw(_("You are not permitted to view this student."), frappe.PermissionError)


# --------------------------------------------------------------------------- #
# Apps screen / landing
# --------------------------------------------------------------------------- #
SCHOOL_APP_ROLES = FULL_ACCESS_ROLES | {"Teacher", "Accountant", "Parent/Guardian"}


def has_app_permission():
	"""Show the School tile on the apps screen to school staff and parents."""
	return bool(_roles() & SCHOOL_APP_ROLES)


def set_guardian_default_app(doc, method=None):
	"""doc_event (Guardian.on_update): land a parent on the School app after login.

	Frappe v16 sends a portal user to their default app, and to their only app when
	there is one (Learning), before any role home page is considered; without this
	a parent lands on the course catalogue instead of /parent.
	"""
	if doc.user and not frappe.db.get_value("User", doc.user, "default_app"):
		frappe.db.set_value("User", doc.user, "default_app", "school_suite")


def _student_user(student):
	return frappe.db.get_value("Student", student, "user")


# --------------------------------------------------------------------------- #
# Parent portal
# --------------------------------------------------------------------------- #
def get_my_children_names():
	"""Student names linked to the logged-in guardian."""
	guardian = get_guardian()
	if not guardian:
		return []
	return frappe.get_all(
		"Student Guardian",
		filters={"guardian": guardian, "parenttype": "Student"},
		pluck="parent",
	)


@frappe.whitelist()
def get_my_children():
	"""Students linked to the logged-in guardian, with a light summary each."""
	out = []
	for s in get_my_children_names():
		doc = frappe.db.get_value("Student", s, ["name", "student_name", "image", "user"], as_dict=True)
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
	return {
		"present": present,
		"absent": counts.get("Absent", 0),
		"leave": counts.get("Leave", 0),
		"total": total,
		"percentage": pct,
	}


# Education v16 bills fees as Sales Invoices (Fee Schedule) carrying `student`;
# Fees is the legacy path. Both are counted. Sales Orders are not receivables
# until invoiced, so they are left out.
FEE_DOCTYPES = ("Sales Invoice", "Fees")


def get_fee_summary(student):
	# Submitted only: a draft is not yet a demand on the parent. Credit notes
	# (returns) carry negative totals and net off.
	rows = []
	for doctype in FEE_DOCTYPES:
		rows += frappe.get_all(
			doctype,
			filters={"student": student, "docstatus": 1},
			fields=["grand_total", "outstanding_amount"],
		)
	billed = sum(r.grand_total or 0 for r in rows)
	outstanding = sum(r.outstanding_amount or 0 for r in rows)
	return {
		"billed": billed,
		"outstanding": outstanding,
		"paid": billed - outstanding,
		"invoice_count": len(rows),
	}


def get_grades(student):
	return frappe.get_all(
		"Assessment Result",
		filters={"student": student, "docstatus": 1},
		fields=[
			"name",
			"course",
			"assessment_group",
			"grade",
			"total_score",
			"maximum_score",
			"academic_term",
		],
		order_by="creation desc",
	)


def get_timetable(student):
	groups = frappe.get_all("Student Group Student", filters={"student": student}, pluck="parent")
	if not groups:
		return []
	rows = frappe.get_all(
		"Course Schedule",
		filters={"student_group": ["in", groups]},
		fields=[
			"name",
			"course",
			"student_group",
			"instructor_name",
			"schedule_date",
			"from_time",
			"to_time",
			"room",
			"title",
		],
		order_by="schedule_date desc, from_time asc",
		limit=50,
	)
	# Display helpers for the portal: room name (not its ID) and HH:mm times.
	rooms = {r.room for r in rows if r.room}
	room_names = (
		dict(
			frappe.get_all(
				"Room", filters={"name": ["in", list(rooms)]}, fields=["name", "room_name"], as_list=True
			)
		)
		if rooms
		else {}
	)
	for r in rows:
		r["room_name"] = room_names.get(r.room, r.room)
		r["time_label"] = " - ".join(
			format_time(str(t), "HH:mm") for t in (r.from_time, r.to_time) if t is not None
		)
	return rows


def get_education_courses(student):
	enrollments = frappe.get_all(
		"Program Enrollment",
		filters={"student": student, "docstatus": 1},
		fields=["name", "program", "academic_year", "academic_term"],
	)
	for e in enrollments:
		e["courses"] = frappe.get_all("Program Enrollment Course", filters={"parent": e.name}, pluck="course")
	return enrollments


def get_lms_progress(student):
	"""LMS data for the student's linked user account."""
	user = _student_user(student)
	if not user:
		return {"linked_user": None, "enrollments": [], "quizzes": [], "certificates": [], "assignments": []}
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
	return {
		"linked_user": user,
		"enrollments": enrollments,
		"quizzes": quizzes,
		"certificates": certificates,
		"assignments": assignments,
	}


@frappe.whitelist()
def get_student_dashboard(student: str):
	"""Unified Education + LMS view for one student (authorisation enforced)."""
	_assert_can_view_student(student)
	base = frappe.db.get_value("Student", student, ["name", "student_name", "image", "user"], as_dict=True)
	if not base:
		frappe.throw(_("Student not found"), frappe.DoesNotExistError)
	base.update(
		{
			"attendance": get_attendance_summary(student),
			"fees": get_fee_summary(student),
			"grades": get_grades(student),
			"timetable": get_timetable(student),
			"education_courses": get_education_courses(student),
			"lms": get_lms_progress(student),
		}
	)
	return base


# --------------------------------------------------------------------------- #
# Principal dashboard
# --------------------------------------------------------------------------- #
def _year_date_condition(academic_year):
	"""SQL date filter for the academic year (defaults to Education Settings' current
	year). Empty string when no year is configured, i.e. all history."""
	academic_year = academic_year or frappe.db.get_single_value("Education Settings", "current_academic_year")
	if not academic_year:
		return ""
	start, end = frappe.db.get_value(
		"Academic Year", academic_year, ["year_start_date", "year_end_date"]
	) or (None, None)
	if not (start and end):
		return ""
	return f" and sa.date between {frappe.db.escape(str(start))} and {frappe.db.escape(str(end))}"


@frappe.whitelist()
def get_principal_dashboard(academic_year: str | None = None):
	if not (_roles() & FULL_ACCESS_ROLES):
		frappe.throw(_("Only Principal / School Admin may view this."), frappe.PermissionError)

	year_cond = _year_date_condition(academic_year)
	threshold = flt(get_settings().low_attendance_threshold)

	# Class-wise attendance (grouped by student group)
	att = frappe.db.sql(
		f"""
        select sa.student_group as `group`,
               sum(sa.status='Present') as present,
               count(sa.name) as total
        from `tabStudent Attendance` sa
        where sa.docstatus=1 and sa.student_group is not null {year_cond}
        group by sa.student_group
        """,
		as_dict=True,
	)
	for a in att:
		# SQL sum() comes back as a decimal; these are day counts.
		a["present"] = cint(a["present"])
		a["percentage"] = round(a["present"] * 100.0 / a["total"], 1) if a["total"] else None

	# Students below the board-exam attendance bar
	low_attendance = frappe.db.sql(
		f"""
        select sa.student, max(sa.student_name) as student_name,
               sum(sa.status='Present') as present, count(sa.name) as total,
               round(sum(sa.status='Present') * 100.0 / count(sa.name), 1) as percentage
        from `tabStudent Attendance` sa
        where sa.docstatus=1 {year_cond}
        group by sa.student
        having sum(sa.status='Present') * 100.0 < %s * count(sa.name)
        order by percentage asc
        limit 100
        """,
		(threshold,),
		as_dict=True,
	)
	for row in low_attendance:
		row["present"] = cint(row["present"])

	# Fee collection (all years, so arrears stay visible; submitted fee bills only)
	fee = {"billed": 0.0, "collected": 0.0, "outstanding": 0.0}
	for doctype in FEE_DOCTYPES:
		table = f"`tab{doctype}`"
		student_cond = "and ifnull(student, '') != ''" if doctype == "Sales Invoice" else ""
		row = frappe.db.sql(
			f"""
            select ifnull(sum(grand_total),0) as billed,
                   ifnull(sum(grand_total-outstanding_amount),0) as collected,
                   ifnull(sum(outstanding_amount),0) as outstanding
            from {table} where docstatus = 1 {student_cond}
            """,
			as_dict=True,
		)[0]
		for key in fee:
			fee[key] += flt(row[key])

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
	return {
		"totals": totals,
		"attendance_by_group": att,
		"low_attendance": low_attendance,
		"low_attendance_threshold": int(threshold) if threshold == int(threshold) else threshold,
		"fee_collection": fee,
		"course_completion": completion,
	}
