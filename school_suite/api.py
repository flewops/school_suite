"""Whitelisted API for the parent portal and the unified / principal dashboards.

Education data (attendance, grades, fees, timetable, programme courses) and LMS
data (enrolments, progress, quiz scores, assignments) are joined on the User
account: `Student.user` == LMS `member`.

Every endpoint re-checks authorisation server-side; it never trusts the caller
to pass a student they are allowed to see.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, format_time, nowdate

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
def get_attendance_summary(student, year=None):
	# v16 forbids raw SQL aggregates in get_all field strings; count in Python.
	from collections import Counter

	filters = {"student": student, "docstatus": 1}
	if year:
		filters["date"] = ["between", [year.year_start_date, year.year_end_date]]
	statuses = frappe.get_all("Student Attendance", filters=filters, pluck="status")
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


def get_fee_summary(student, year=None):
	# Submitted only: a draft is not yet a demand on the parent. Credit notes
	# (returns) carry negative totals and net off. With a year, `arrears` is what is
	# still unpaid from earlier years, so old dues never drop out of sight.
	in_year, before_year, params = _fee_year_filters(year)
	params["student"] = student
	bills = f"from ({_FEE_BILLS}) bills where docstatus = 1 and student = %(student)s"
	rows = frappe.db.sql(
		f"select grand_total, outstanding_amount {bills} and {in_year}", params, as_dict=True
	)
	arrears = frappe.db.sql(f"select sum(outstanding_amount) {bills} and {before_year}", params)[0][0]
	billed = sum(flt(r.grand_total) for r in rows)
	outstanding = sum(flt(r.outstanding_amount) for r in rows)
	return {
		"billed": billed,
		"outstanding": outstanding,
		"paid": billed - outstanding,
		"invoice_count": len(rows),
		"arrears": flt(arrears),
	}


def get_grades(student, year=None):
	filters = {"student": student, "docstatus": 1}
	if year:
		filters["academic_year"] = year.name
	return frappe.get_all(
		"Assessment Result",
		filters=filters,
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


def get_timetable(student, year=None):
	groups = frappe.get_all("Student Group Student", filters={"student": student}, pluck="parent")
	if not groups:
		return []
	filters = {"student_group": ["in", groups]}
	if year:
		filters["schedule_date"] = ["between", [year.year_start_date, year.year_end_date]]
	rows = frappe.get_all(
		"Course Schedule",
		filters=filters,
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


def get_education_courses(student, year=None):
	filters = {"student": student, "docstatus": 1}
	if year:
		filters["academic_year"] = year.name
	enrollments = frappe.get_all(
		"Program Enrollment",
		filters=filters,
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
def get_student_dashboard(student: str, academic_year: str | None = None):
	"""Unified Education + LMS view for one student (authorisation enforced), for one
	academic year (see _resolve_academic_year). LMS progress isn't tied to a year."""
	_assert_can_view_student(student)
	base = frappe.db.get_value("Student", student, ["name", "student_name", "image", "user"], as_dict=True)
	if not base:
		frappe.throw(_("Student not found"), frappe.DoesNotExistError)
	year = _resolve_academic_year(academic_year)
	base.update(
		{
			"academic_year": year.name if year else None,
			"attendance": get_attendance_summary(student, year),
			"fees": get_fee_summary(student, year),
			"grades": get_grades(student, year),
			"timetable": get_timetable(student, year),
			"education_courses": get_education_courses(student, year),
			"lms": get_lms_progress(student),
		}
	)
	return base


# --------------------------------------------------------------------------- #
# Principal dashboard
# --------------------------------------------------------------------------- #
def _resolve_academic_year(academic_year=None):
	"""The academic year a dashboard reports on: the one asked for, else Education
	Settings' current year, else the year that contains today. None when no year is
	set up, in which case the dashboard covers all history."""
	fields = ["name", "year_start_date", "year_end_date"]
	for name in (academic_year, frappe.db.get_single_value("Education Settings", "current_academic_year")):
		year = name and frappe.db.get_value("Academic Year", name, fields, as_dict=True)
		if year and year.year_start_date and year.year_end_date:
			return year
	today = nowdate()
	return frappe.db.get_value(
		"Academic Year",
		{"year_start_date": ["<=", today], "year_end_date": [">=", today]},
		fields,
		as_dict=True,
		order_by="year_start_date desc",
	)


def _year_date_condition(year):
	"""SQL date filter on Student Attendance for `year` (see _resolve_academic_year).
	Empty string when there is no year, i.e. all history."""
	if not year:
		return ""
	start, end = frappe.db.escape(str(year.year_start_date)), frappe.db.escape(str(year.year_end_date))
	return f" and sa.date between {start} and {end}"


# Every fee bill (submitted or draft) with the date that places it in an academic
# year: the start of the year it was raised for (its Fee Schedule's year, or the
# legacy Fees' own), else its posting date (a one-off invoice). So fees posted in
# March for the year starting in April count in that new year.
# Education v16 bills fees as Sales Invoices (Fee Schedule) carrying `student`;
# Fees is the legacy path. Both are counted. Sales Orders are not receivables
# until invoiced, so they are left out.
_FEE_BILLS = """
	select si.student, si.docstatus, si.grand_total, si.outstanding_amount, si.due_date,
	       coalesce(ay.year_start_date, si.posting_date) as year_date, fs.program
	from `tabSales Invoice` si
	left join `tabFee Schedule` fs on fs.name = si.fee_schedule
	left join `tabAcademic Year` ay on ay.name = fs.academic_year
	where si.docstatus < 2 and ifnull(si.student, '') != ''
	union all
	select f.student, f.docstatus, f.grand_total, f.outstanding_amount, f.due_date,
	       coalesce(ay.year_start_date, f.posting_date), f.program
	from `tabFees` f
	left join `tabAcademic Year` ay on ay.name = f.academic_year
	where f.docstatus < 2
"""


def _fee_year_filters(year):
	"""SQL conditions on _FEE_BILLS for the bills raised for `year` and for earlier
	years, and their params. Without a year every bill counts and none is earlier."""
	if not year:
		return "1=1", "1=0", {}
	return (
		"year_date between %(start)s and %(end)s",
		"year_date < %(start)s",
		{"start": year.year_start_date, "end": year.year_end_date},
	)


def _fee_collection(year):
	"""Fee figures for `year`: billed, collected and outstanding (split into overdue
	and not yet due) for the bills raised for that year, by class too; unpaid bills of
	earlier years as arrears; and the number of draft bills, which are not counted
	because they are not yet a demand on the parent."""
	in_year, before_year, params = _fee_year_filters(year)
	params["today"] = nowdate()

	rows = frappe.db.sql(
		f"""
		select student, program, sum(grand_total) as billed, sum(outstanding_amount) as outstanding,
		       sum(case when due_date < %(today)s then outstanding_amount else 0 end) as overdue
		from ({_FEE_BILLS}) bills
		where docstatus = 1 and {in_year}
		group by student, program
		""",
		params,
		as_dict=True,
	)
	arrears = frappe.db.sql(
		f"""
		select student, sum(outstanding_amount) as outstanding
		from ({_FEE_BILLS}) bills
		where docstatus = 1 and {before_year}
		group by student
		having sum(outstanding_amount) > 0
		""",
		params,
		as_dict=True,
	)
	drafts = frappe.db.sql(
		f"select count(*) from ({_FEE_BILLS}) bills where docstatus = 0 and {in_year}", params
	)[0][0]

	# A student's class is their enrollment for the year; failing that, the class
	# the bill was raised for.
	enrolled = {}
	if year:
		for pe in frappe.get_all(
			"Program Enrollment",
			filters={"academic_year": year.name, "docstatus": 1},
			fields=["student", "program", "student_batch_name"],
		):
			enrolled[pe.student] = " · ".join(filter(None, (pe.program, pe.student_batch_name)))
	amounts = ("billed", "outstanding", "overdue")
	by_class = {}
	for row in rows:
		label = enrolled.get(row.student) or row.program or _("Not enrolled")
		group = by_class.setdefault(label, dict.fromkeys(amounts, 0.0))
		for key in amounts:
			group[key] += flt(row[key])

	def summarise(figures):
		billed, outstanding, overdue = (flt(figures[key], 2) for key in amounts)
		collected = flt(billed - outstanding, 2)
		return {
			"billed": billed,
			"collected": collected,
			"outstanding": outstanding,
			"overdue": overdue,
			"not_yet_due": flt(outstanding - overdue, 2),
			"collection_pct": round(collected * 100.0 / billed, 1) if billed else None,
		}

	return {
		**summarise({key: sum(flt(row[key]) for row in rows) for key in amounts}),
		"by_class": [{"class": label, **summarise(by_class[label])} for label in sorted(by_class)],
		"arrears": {
			"outstanding": flt(sum(flt(a.outstanding) for a in arrears), 2),
			"students": len(arrears),
		},
		"draft_bills": cint(drafts),
	}


@frappe.whitelist()
def get_principal_dashboard(academic_year: str | None = None):
	if not (_roles() & FULL_ACCESS_ROLES):
		frappe.throw(_("Only Principal / School Admin may view this."), frappe.PermissionError)

	year = _resolve_academic_year(academic_year)
	year_cond = _year_date_condition(year)
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

	fee = _fee_collection(year)

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
		"academic_year": year.name if year else None,
		"totals": totals,
		"attendance_by_group": att,
		"low_attendance": low_attendance,
		"low_attendance_threshold": int(threshold) if threshold == int(threshold) else threshold,
		"fee_collection": fee,
		"course_completion": completion,
	}
