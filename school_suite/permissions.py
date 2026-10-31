"""Row-level access control for School Suite.

Enforces, on top of ERPNext/Education's own DocType role permissions:
  * Parent / Guardian  -> only their own child(ren)
  * Teacher            -> only students / groups / schedules they are assigned to
  * Student            -> only their own records

Wired in hooks.py via `permission_query_conditions` (filters list views / reports)
and `has_permission` (guards access to a single document).

Design note: these functions return SQL WHERE snippets that Frappe ANDs into the
query. All interpolated values are escaped with frappe.db.escape. Staff roles
(System Manager, School Admin, Principal) are returned unrestricted here; coarse
"can this role touch this doctype at all" is handled by normal role permissions.
"""

import frappe

FULL_ACCESS_ROLES = {"System Manager", "Administrator", "School Admin", "Principal"}
# Office roles that bill every student, so they see all students, classes and
# enrolments (to raise fees) but not marks or attendance.
BILLING_ROLES = {"Accountant"}
BILLING_DOCTYPES = {"Fees", "Program Enrollment"}


# --------------------------------------------------------------------------- #
# Identity lookups: map the logged-in user to their domain record
# --------------------------------------------------------------------------- #
def _roles(user=None):
	return set(frappe.get_roles(user or frappe.session.user))


def get_guardian(user=None):
	user = user or frappe.session.user
	return frappe.db.get_value("Guardian", {"user": user}, "name")


def get_student(user=None):
	user = user or frappe.session.user
	return frappe.db.get_value("Student", {"user": user}, "name")


def get_instructor(user=None):
	"""Teacher user -> Employee (user_id) -> Instructor (employee)."""
	user = user or frappe.session.user
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		# Some deployments link an Instructor straight to a user via a custom field;
		# fall back to no instructor if that is not configured.
		return None
	return frappe.db.get_value("Instructor", {"employee": employee}, "name")


# --------------------------------------------------------------------------- #
# Reusable subquery fragments (return SQL that yields a set of Student names)
# --------------------------------------------------------------------------- #
def _students_of_guardian(guardian):
	g = frappe.db.escape(guardian)
	return f"(select parent from `tabStudent Guardian` where parenttype='Student' and guardian={g})"


def _students_of_instructor(instructor):
	i = frappe.db.escape(instructor)
	return (
		f"(select sgs.student from `tabStudent Group Student` sgs "
		f"inner join `tabStudent Group Instructor` sgi on sgs.parent=sgi.parent "
		f"where sgi.instructor={i})"
	)


def _groups_of_instructor(instructor):
	i = frappe.db.escape(instructor)
	return f"(select parent from `tabStudent Group Instructor` where instructor={i})"


def _groups_of_student(student):
	s = frappe.db.escape(student)
	return f"(select parent from `tabStudent Group Student` where student={s})"


def _no_rows():
	return "1=0"


# --------------------------------------------------------------------------- #
# permission_query_conditions handlers (one per doctype)
# --------------------------------------------------------------------------- #
def student_query(user=None):
	"""Restrict the Student list for Teacher / Parent-Guardian / Student roles.

	IMPORTANT (verified the hard way): Education's own native condition on Student
	only fires for *portal-only* users set up with the native "Guardian" role. Our
	guardians use the custom "Parent/Guardian" role, so native does NOT cover them
	— we MUST restrict them here or they would see every student. (If a school
	later standardises on the native Guardian role + portal-only users, this clause
	becomes redundant and can be dropped.)
	"""
	user = user or frappe.session.user
	roles = _roles(user)
	if roles & (FULL_ACCESS_ROLES | BILLING_ROLES):
		return ""
	clauses = []
	if "Teacher" in roles:
		instr = get_instructor(user)
		clauses.append(f"`tabStudent`.name in {_students_of_instructor(instr)}" if instr else _no_rows())
	if "Parent/Guardian" in roles:
		g = get_guardian(user)
		clauses.append(f"`tabStudent`.name in {_students_of_guardian(g)}" if g else _no_rows())
	if "Student" in roles:
		clauses.append(f"`tabStudent`.user = {frappe.db.escape(user)}")
	return "(" + " or ".join(clauses) + ")" if clauses else _no_rows()


def student_group_query(user=None):
	user = user or frappe.session.user
	roles = _roles(user)
	if roles & (FULL_ACCESS_ROLES | BILLING_ROLES):
		return ""
	clauses = []
	if "Teacher" in roles:
		if instr := get_instructor(user):
			clauses.append(f"`tabStudent Group`.name in {_groups_of_instructor(instr)}")
	if "Parent/Guardian" in roles:
		if g := get_guardian(user):
			clauses.append(
				f"`tabStudent Group`.name in "
				f"(select parent from `tabStudent Group Student` "
				f"where student in {_students_of_guardian(g)})"
			)
	if "Student" in roles:
		if s := get_student(user):
			clauses.append(f"`tabStudent Group`.name in {_groups_of_student(s)}")
	return "(" + " or ".join(clauses) + ")" if clauses else _no_rows()


def _by_student_field(doctype, user):
	"""Generic: doctype has a `student` Link; restrict to allowed students."""
	roles = _roles(user)
	if roles & FULL_ACCESS_ROLES:
		return ""
	tbl = f"`tab{doctype}`"
	clauses = []
	if "Teacher" in roles:
		if instr := get_instructor(user):
			clauses.append(f"{tbl}.student in {_students_of_instructor(instr)}")
	if "Parent/Guardian" in roles:
		if g := get_guardian(user):
			clauses.append(f"{tbl}.student in {_students_of_guardian(g)}")
	if "Student" in roles:
		if s := get_student(user):
			clauses.append(f"{tbl}.student = {frappe.db.escape(s)}")
	return "(" + " or ".join(clauses) + ")" if clauses else _no_rows()


def student_attendance_query(user=None):
	return _by_student_field("Student Attendance", user or frappe.session.user)


def assessment_result_query(user=None):
	return _by_student_field("Assessment Result", user or frappe.session.user)


def program_enrollment_query(user=None):
	user = user or frappe.session.user
	if _roles(user) & BILLING_ROLES:
		return ""
	return _by_student_field("Program Enrollment", user)


def course_enrollment_query(user=None):
	return _by_student_field("Course Enrollment", user or frappe.session.user)


def fees_query(user=None):
	user = user or frappe.session.user
	roles = _roles(user)
	if roles & FULL_ACCESS_ROLES or "Accountant" in roles:
		return ""
	# Parents and students see only their own fees; teachers see none.
	clauses = []
	if "Parent/Guardian" in roles:
		if g := get_guardian(user):
			clauses.append(f"`tabFees`.student in {_students_of_guardian(g)}")
	if "Student" in roles:
		if s := get_student(user):
			clauses.append(f"`tabFees`.student = {frappe.db.escape(s)}")
	return "(" + " or ".join(clauses) + ")" if clauses else _no_rows()


def course_schedule_query(user=None):
	user = user or frappe.session.user
	roles = _roles(user)
	if roles & FULL_ACCESS_ROLES:
		return ""
	clauses = []
	if "Teacher" in roles:
		if instr := get_instructor(user):
			clauses.append(f"`tabCourse Schedule`.instructor = {frappe.db.escape(instr)}")
			clauses.append(f"`tabCourse Schedule`.student_group in {_groups_of_instructor(instr)}")
	if "Parent/Guardian" in roles:
		if g := get_guardian(user):
			clauses.append(
				f"`tabCourse Schedule`.student_group in "
				f"(select parent from `tabStudent Group Student` "
				f"where student in {_students_of_guardian(g)})"
			)
	if "Student" in roles:
		if s := get_student(user):
			clauses.append(f"`tabCourse Schedule`.student_group in {_groups_of_student(s)}")
	return "(" + " or ".join(clauses) + ")" if clauses else _no_rows()


# --------------------------------------------------------------------------- #
# has_permission handlers (single-document access)
# --------------------------------------------------------------------------- #
def _allowed_students(user):
	"""Set of Student names this user may see (small sets only: parent/student)."""
	roles = _roles(user)
	allowed = set()
	if "Parent/Guardian" in roles and (g := get_guardian(user)):
		allowed |= set(
			frappe.get_all(
				"Student Guardian",
				filters={"guardian": g, "parenttype": "Student"},
				pluck="parent",
			)
		)
	if "Student" in roles and (s := get_student(user)):
		allowed.add(s)
	if "Teacher" in roles and (instr := get_instructor(user)):
		groups = frappe.get_all("Student Group Instructor", filters={"instructor": instr}, pluck="parent")
		if groups:
			allowed |= set(
				frappe.get_all(
					"Student Group Student",
					filters={"parent": ["in", groups]},
					pluck="student",
				)
			)
	return allowed


def _allowed_groups(user):
	"""Set of Student Group names this user may see (mirrors student_group_query)."""
	roles = _roles(user)
	allowed = set()
	if "Teacher" in roles and (instr := get_instructor(user)):
		allowed |= set(
			frappe.get_all("Student Group Instructor", filters={"instructor": instr}, pluck="parent")
		)
	students = set()
	if "Parent/Guardian" in roles and (g := get_guardian(user)):
		students |= set(
			frappe.get_all(
				"Student Guardian",
				filters={"guardian": g, "parenttype": "Student"},
				pluck="parent",
			)
		)
	if "Student" in roles and (s := get_student(user)):
		students.add(s)
	if students:
		allowed |= set(
			frappe.get_all(
				"Student Group Student",
				filters={"student": ["in", list(students)]},
				pluck="parent",
			)
		)
	return allowed


def student_group_has_permission(doc, ptype=None, user=None):
	"""Single-document guard for Student Group (list filtering alone does not stop
	a teacher opening another class's roster by URL)."""
	user = user or frappe.session.user
	if _roles(user) & (FULL_ACCESS_ROLES | BILLING_ROLES):
		return True
	name = doc if isinstance(doc, str) else doc.name
	return name in _allowed_groups(user)


def course_schedule_has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	roles = _roles(user)
	if roles & FULL_ACCESS_ROLES:
		return True
	if "Teacher" in roles and (instr := get_instructor(user)) and doc.get("instructor") == instr:
		return True
	return doc.get("student_group") in _allowed_groups(user)


def student_has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if _roles(user) & (FULL_ACCESS_ROLES | BILLING_ROLES):
		return True
	name = doc if isinstance(doc, str) else doc.name
	return name in _allowed_students(user)


def student_record_has_permission(doc, ptype=None, user=None):
	"""For doctypes carrying a `student` field."""
	user = user or frappe.session.user
	roles = _roles(user)
	if roles & FULL_ACCESS_ROLES:
		return True
	if roles & BILLING_ROLES and getattr(doc, "doctype", None) in BILLING_DOCTYPES:
		return True
	student = getattr(doc, "student", None)
	if student is None:
		return True  # not our concern
	return student in _allowed_students(user)
