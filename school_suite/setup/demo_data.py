"""Fake demo data for local testing ONLY. No real student/guardian data.

Creates a tiny school: 1 company, 1 programme, 2 guardians, 3 students,
1 teacher, 2 student groups, attendance, one LMS course with enrolments.
Run with:  bench --site school.localhost execute school_suite.setup.demo_data.run
"""

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate, today

TEST_PASSWORD = "Test@12345"  # local test credential only — never use in production
DOMAIN = "demo.school"

# student_key -> (first_name, guardian_key)
STUDENTS = {
	"arya": ("Arya", "guardian_meera"),
	"bodhi": ("Bodhi", "guardian_meera"),  # Meera has two children: Arya + Bodhi
	"chetan": ("Chetan", "guardian_ravi"),  # Ravi has one child: Chetan
}
GUARDIANS = {
	"guardian_meera": "Meera Nair",
	"guardian_ravi": "Ravi Kumar",
}
# Office staff logins, each created through its Role Profile (setup/install.py):
# key -> (full name, Role Profile)
STAFF = {
	"school_admin": ("Anita Desai", "School Admin"),
	"principal": ("Rajesh Iyer", "Principal"),
	"accountant": ("Kavya Menon", "Accountant"),
}
# Relation is printed on the Transfer Certificate (Father's / Mother's name).
GUARDIAN_RELATION = {"guardian_meera": "Mother", "guardian_ravi": "Father"}


def _email(key):
	return f"{key}@{DOMAIN}"


def _user(email, full_name, roles):
	if not frappe.db.exists("User", email):
		u = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": full_name,
				"send_welcome_email": 0,
				"new_password": TEST_PASSWORD,
			}
		)
		u.flags.ignore_permissions = True
		u.insert(ignore_permissions=True)
	u = frappe.get_doc("User", email)
	existing = {r.role for r in u.roles}
	for r in roles:
		if r not in existing:
			u.append("roles", {"role": r})
	u.save(ignore_permissions=True)
	return email


def _staff(key):
	full_name, profile = STAFF[key]
	email = _email(key)
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": full_name,
				"send_welcome_email": 0,
				"new_password": TEST_PASSWORD,
				"role_profiles": [{"role_profile": profile}],
			}
		).insert(ignore_permissions=True)
	return email


def _company():
	name = "Demo School"
	if not frappe.db.exists("Company", name):
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": name,
				"abbr": "DS",
				"default_currency": "INR",
				"country": "India",
			}
		).insert(ignore_permissions=True)
	return name


def _holiday_list(company):
	start, end = academic_year_dates()
	name = f"School Holidays {academic_year_name()}"
	if not frappe.db.exists("Holiday List", name):
		hl = frappe.get_doc(
			{
				"doctype": "Holiday List",
				"holiday_list_name": name,
				"from_date": start,
				"to_date": end,
				"weekly_off": "Sunday",
			}
		)
		hl.get_weekly_off_dates()
		hl.insert(ignore_permissions=True)
	frappe.db.set_value("Company", company, "default_holiday_list", name)
	return name


def _academic():
	ay = academic_year_name()
	start, end = academic_year_dates()
	if not frappe.db.exists("Academic Year", ay):
		frappe.get_doc(
			{
				"doctype": "Academic Year",
				"academic_year_name": ay,
				"year_start_date": start,
				"year_end_date": end,
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("Course", "Mathematics"):
		frappe.get_doc({"doctype": "Course", "course_name": "Mathematics"}).insert(ignore_permissions=True)
	prog = "Grade 5"
	if not frappe.db.exists("Program", prog):
		p = frappe.get_doc({"doctype": "Program", "program_name": prog})
		p.append("courses", {"course": "Mathematics"})
		p.insert(ignore_permissions=True)
	return ay, prog, "Mathematics"


def _guardian(key):
	name_val = GUARDIANS[key]
	email = _user(_email(key), name_val, ["Parent/Guardian"])
	existing = frappe.db.get_value("Guardian", {"user": email}, "name")
	if existing:
		return existing
	g = frappe.get_doc(
		{
			"doctype": "Guardian",
			"guardian_name": name_val,
			"email_address": email,
			"user": email,
		}
	)
	g.insert(ignore_permissions=True)
	return g.name


def _student(key, ay, prog):
	first, gkey = STUDENTS[key]
	guardian = _guardian(gkey)
	email = _user(_email(key), first, ["Student"])
	existing = frappe.db.get_value("Student", {"user": email}, "name")
	if existing:
		return existing
	s = frappe.get_doc(
		{
			"doctype": "Student",
			"first_name": first,
			"student_email_id": email,
			"user": email,
			"joining_date": academic_year_dates()[0],
		}
	)
	s.append("guardians", {"guardian": guardian, "relation": GUARDIAN_RELATION[gkey]})
	s.insert(ignore_permissions=True)
	return s.name


def _teacher(company):
	email = _user(_email("teacher_sunita"), "Sunita Rao", ["Teacher", "Instructor"])
	emp = frappe.db.get_value("Employee", {"user_id": email}, "name")
	if not emp:
		e = frappe.get_doc(
			{
				"doctype": "Employee",
				"employee_name": "Sunita Rao",
				"first_name": "Sunita",
				"company": company,
				"gender": "Female",
				"date_of_birth": "1988-06-01",
				"date_of_joining": academic_year_dates()[0],
				"status": "Active",
				"user_id": email,
			}
		)
		e.insert(ignore_permissions=True)
		emp = e.name
	instr = frappe.db.get_value("Instructor", {"employee": emp}, "name")
	if not instr:
		i = frappe.get_doc(
			{
				"doctype": "Instructor",
				"instructor_name": "Sunita Rao",
				"employee": emp,
			}
		)
		i.insert(ignore_permissions=True)
		instr = i.name
	return instr


def _group(name, ay, prog, students, instructor=None):
	existing = frappe.db.get_value("Student Group", {"student_group_name": name}, "name")
	if existing:
		return existing
	g = frappe.get_doc(
		{
			"doctype": "Student Group",
			"student_group_name": name,
			"group_based_on": "Activity",
			"program": prog,
			"academic_year": ay,
		}
	)
	for s in students:
		g.append("students", {"student": s, "active": 1})
	if instructor:
		g.append("instructors", {"instructor": instructor})
	g.insert(ignore_permissions=True)
	return g.name


def _attendance(student, group, status, day_offset):
	exists = frappe.db.exists(
		"Student Attendance", {"student": student, "date": add_days(nowdate(), -day_offset)}
	)
	if exists:
		return
	a = frappe.get_doc(
		{
			"doctype": "Student Attendance",
			"student": student,
			"student_group": group,
			"date": add_days(nowdate(), -day_offset),
			"status": status,
		}
	)
	a.insert(ignore_permissions=True)
	a.submit()


def _lms(students):
	course = "Fractions Basics"
	if not frappe.db.exists("LMS Course", {"title": course}):
		c = frappe.get_doc(
			{
				"doctype": "LMS Course",
				"title": course,
				"short_introduction": "Intro to fractions",
				"description": "Demo course",
				"published": 1,
				"status": "Approved",
				# mandatory in LMS v2.63.0 (the pinned release), checked before LMS's
				# own validate would default it to the owner
				"instructors": [{"instructor": _email("teacher_sunita")}],
			}
		)
		c.insert(ignore_permissions=True)
	course_name = frappe.db.get_value("LMS Course", {"title": course}, "name")
	progress_map = {0: 40, 1: 75, 2: 100}
	for idx, s in enumerate(students):
		user = frappe.db.get_value("Student", s, "user")
		if user and not frappe.db.exists("LMS Enrollment", {"member": user, "course": course_name}):
			frappe.get_doc(
				{
					"doctype": "LMS Enrollment",
					"member": user,
					"course": course_name,
					"progress": progress_map.get(idx, 50),
				}
			).insert(ignore_permissions=True)
	return course_name


def academic_year_dates(on=None):
	"""Indian academic year (1 April - 31 March) containing `on` (default today)."""
	d = getdate(on or today())
	start_year = d.year if d.month >= 4 else d.year - 1
	return f"{start_year}-04-01", f"{start_year + 1}-03-31"


def academic_year_name(on=None):
	start = int(academic_year_dates(on)[0][:4])
	return f"{start}-{start + 1}"


def assert_dev_site():
	"""Demo data creates logins with a known password; never on a live site."""
	if not (frappe.conf.developer_mode or frappe.flags.in_test):
		frappe.throw(_("Demo data and the flow test run only on a developer-mode site."))


def run():
	assert_dev_site()
	company = _company()
	_holiday_list(company)
	ay, prog, _course = _academic()
	students = {k: _student(k, ay, prog) for k in STUDENTS}
	teacher = _teacher(company)
	staff = {key: _staff(key) for key in STAFF}

	# Group 1A: Arya + Bodhi, taught by Sunita.  Group 1B: Chetan, no teacher.
	g1 = _group("Class 1A", ay, prog, [students["arya"], students["bodhi"]], teacher)
	g2 = _group("Class 1B", ay, prog, [students["chetan"]])

	_attendance(students["arya"], g1, "Present", 1)
	_attendance(students["arya"], g1, "Absent", 2)
	_attendance(students["bodhi"], g1, "Present", 1)
	_attendance(students["chetan"], g2, "Present", 1)

	lms_course = _lms([students["arya"], students["bodhi"], students["chetan"]])

	frappe.db.commit()
	return {
		"students": students,
		"teacher": teacher,
		"groups": {"Class 1A": g1, "Class 1B": g2},
		"lms_course": lms_course,
		"logins": {
			"parent_meera": _email("guardian_meera"),
			"parent_ravi": _email("guardian_ravi"),
			"teacher": _email("teacher_sunita"),
			"student_arya": _email("arya"),
			**staff,
			"password": TEST_PASSWORD,
		},
	}
