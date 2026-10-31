"""Idempotent setup run on install and every migrate: roles, custom fields,
property setters, settings defaults, the admission workflow, a grading scale and
role permissions.

This module is the single source of truth for that schema (there are no
fixtures to keep in sync). Custom fields and property setters carry
module="School Suite", so `bench uninstall-app school_suite` removes them.
Roles, the workflow and the grading scale are created only when missing: once
installed they belong to the school, and a migrate must not undo its edits.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from school_suite.school_suite.doctype.school_suite_settings.school_suite_settings import (
	ensure_defaults,
	get_settings,
)

MODULE = "School Suite"

# Base read access per role (row-level narrowing is done by permission_query_conditions).
# Stored as Custom DocPerm — core app permissions are never edited.
ROLE_READ_PERMS = {
	"Teacher": [
		"Student",
		"Student Group",
		"Student Attendance",
		"Assessment Result",
		"Course Schedule",
		"Program Enrollment",
		"Course Enrollment",
	],
	"Parent/Guardian": [
		"Student",
		"Student Attendance",
		"Assessment Result",
		"Course Schedule",
		"Fees",
		"Program Enrollment",
	],
	"Student": [
		"Student",
		"Student Attendance",
		"Assessment Result",
		"Course Schedule",
		"Fees",
		"Program Enrollment",
		"Course Enrollment",
	],
	"Accountant": ["Fees", "Student", "Program Enrollment"],
}

# Rights on top of read. Row-level hooks still limit a teacher to their own classes.
# Teachers mark daily attendance and enter marks; publishing results (submit) stays
# with School Admin / Principal.
ROLE_WRITE_PERMS = {
	"Teacher": {
		"Student Attendance": ["create", "write", "submit"],
		"Student Attendance Tool": ["create", "write"],
		"Assessment Result": ["create", "write"],
		"Assessment Result Tool": ["create", "write"],
		"Assessment Plan": [],
		"Assessment Criteria": [],
		"Grading Scale": [],
	},
	"School Admin": {"School Suite Settings": ["create", "write"]},
	"Principal": {"School Suite Settings": []},
}

CBSE_GRADING_SCALE = "CBSE 9-Point"
# (grade, minimum %, description) — CBSE scheme for Classes IX-XII; 33% is the pass mark.
CBSE_GRADES = [
	("A1", 91, "91-100"),
	("A2", 81, "81-90"),
	("B1", 71, "71-80"),
	("B2", 61, "61-70"),
	("C1", 51, "51-60"),
	("C2", 41, "41-50"),
	("D", 33, "33-40"),
	("E", 0, "32 and below (needs improvement)"),
]

# Roles required by the brief. (Education already ships "Student"/"Instructor";
# we create our named roles idempotently and leave existing ones untouched.)
ROLES = [
	"School Admin",
	"Accountant",
	"Teacher",
	"Student",
	"Parent/Guardian",
	"Principal",
]

CUSTOM_FIELDS = {
	# Per-student "online mode" toggle: attendance may be derived from
	# live-class / LMS activity rather than a physical register.
	"Student": [
		{
			"fieldname": "online_mode",
			"label": "Online Mode (attendance from live class / LMS)",
			"fieldtype": "Check",
			"insert_after": "enabled",
			"description": "When set, attendance may be derived from LMS / live-class activity.",
		},
		# Indian student-master data needed for UDISE+, RTE, scholarships and the
		# Transfer Certificate. All optional; collect only what the school needs.
		{
			"fieldname": "india_section",
			"label": "India / UDISE+ Details",
			"fieldtype": "Section Break",
			"collapsible": 1,
			"insert_after": "student_applicant",
		},
		{
			"fieldname": "admission_number",
			"label": "Admission No. (General Register)",
			"fieldtype": "Data",
			"in_standard_filter": 1,
			"search_index": 1,
			"no_copy": 1,
			"insert_after": "india_section",
		},
		{
			"fieldname": "apaar_id",
			"label": "APAAR ID",
			"fieldtype": "Data",
			"no_copy": 1,
			"insert_after": "admission_number",
			"description": "12-digit Automated Permanent Academic Account Registry ID.",
		},
		{
			"fieldname": "pen",
			"label": "PEN (UDISE+)",
			"fieldtype": "Data",
			"no_copy": 1,
			"insert_after": "apaar_id",
			"description": "Permanent Education Number allotted by UDISE+.",
		},
		{
			"fieldname": "social_category",
			"label": "Social Category",
			"fieldtype": "Select",
			"options": "\nGeneral\nSC\nST\nOBC",
			"insert_after": "pen",
		},
		{
			"fieldname": "religion",
			"label": "Religion",
			"fieldtype": "Select",
			"options": "\nHindu\nMuslim\nChristian\nSikh\nBuddhist\nParsi\nJain\nOther",
			"insert_after": "social_category",
		},
		{
			"fieldname": "mother_tongue",
			"label": "Mother Tongue",
			"fieldtype": "Data",
			"insert_after": "religion",
		},
		{
			"fieldname": "india_column",
			"fieldtype": "Column Break",
			"insert_after": "mother_tongue",
		},
		{
			"fieldname": "is_cwsn",
			"label": "Child With Special Needs (CWSN)",
			"fieldtype": "Check",
			"insert_after": "india_column",
		},
		{
			"fieldname": "disability_type",
			"label": "Disability Type (RPwD Act)",
			"fieldtype": "Data",
			"depends_on": "is_cwsn",
			"insert_after": "is_cwsn",
		},
		{
			"fieldname": "is_bpl",
			"label": "BPL Family",
			"fieldtype": "Check",
			"insert_after": "disability_type",
		},
		{
			"fieldname": "rte_admission",
			"label": "Admitted under RTE 12(1)(c)",
			"fieldtype": "Check",
			"insert_after": "is_bpl",
			"description": "EWS/DG quota seat: fees are reimbursed by the State, not charged to the parent.",
		},
		{
			"fieldname": "previous_school",
			"label": "Previous School",
			"fieldtype": "Data",
			"insert_after": "rte_admission",
		},
		{
			"fieldname": "previous_tc_number",
			"label": "Previous School TC No.",
			"fieldtype": "Data",
			"insert_after": "previous_school",
		},
	],
	"Company": [
		{
			"fieldname": "udise_code",
			"label": "UDISE+ School Code",
			"fieldtype": "Data",
			"insert_after": "date_of_establishment",
			"description": "11-digit code; used on the UDISE+ export and Transfer Certificates.",
		}
	],
	# Map an Education class/section to an LMS batch and auto-enrol its students.
	"Student Group": [
		{
			"fieldname": "enable_online_batch",
			"label": "Enable Online (LMS) Batch",
			"fieldtype": "Check",
			"insert_after": "instructors",
			"description": "Create/sync an LMS Batch for this class and auto-enrol its students.",
		},
		{
			"fieldname": "lms_batch",
			"label": "LMS Batch",
			"fieldtype": "Link",
			"options": "LMS Batch",
			"read_only": 1,
			"insert_after": "enable_online_batch",
		},
	],
	# Reverse link on the LMS batch back to the Education class.
	"LMS Batch": [
		{
			"fieldname": "student_group",
			"label": "Education Student Group",
			"fieldtype": "Link",
			"options": "Student Group",
			"read_only": 1,
			"insert_after": "title",
		}
	],
}


def create_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc(
				{
					"doctype": "Role",
					"role_name": role,
					"desk_access": role != "Parent/Guardian",  # guardians use the portal, not the desk
				}
			).insert(ignore_permissions=True)


def set_guardian_landing():
	"""Existing guardian logins land on the School app (api.set_guardian_default_app
	covers guardians saved from now on)."""
	from school_suite.api import set_guardian_default_app

	for guardian in frappe.get_all("Guardian", filters={"user": ["is", "set"]}, fields=["user"]):
		set_guardian_default_app(guardian)


def create_custom_field_records():
	fields = {dt: [{**df, "module": MODULE} for df in dfs] for dt, dfs in CUSTOM_FIELDS.items()}
	create_custom_fields(fields, ignore_validate=True)


def apply_student_email_requirement(required):
	"""Student email is mandatory by default so every Student can be linked to a
	login (needed for the LMS join + portals). Schools whose youngest children
	have no email switch it off in School Suite Settings."""
	frappe.make_property_setter(
		{
			"doctype": "Student",
			"fieldname": "student_email_id",
			"property": "reqd",
			"value": "1" if required else "0",
			"property_type": "Check",
		},
		is_system_generated=False,
		module=MODULE,
	)


def create_property_setters():
	# Fix an Education v16 bug. Fees.income_account has
	# fetch_from="fee_structure.income_account", but Fee Structure no longer has
	# an income_account field, so saving any Fees doc raises
	# "Unknown column 'income_account'". Clear the broken fetch_from here (the
	# income account is set explicitly / resolved from the Item instead).
	if frappe.get_meta("Fees").get_field("income_account") and not frappe.get_meta("Fee Structure").get_field(
		"income_account"
	):
		frappe.make_property_setter(
			{
				"doctype": "Fees",
				"fieldname": "income_account",
				"property": "fetch_from",
				"value": "",
				"property_type": "Small Text",
			},
			is_system_generated=False,
			module=MODULE,
		)


def _ensure_workflow_masters(state_names, action_names):
	"""Workflow states/actions must exist as master records before a Workflow
	can reference them."""
	for s in state_names:
		if not frappe.db.exists("Workflow State", s):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": s, "style": ""}).insert(
				ignore_permissions=True
			)
	for a in action_names:
		if not frappe.db.exists("Workflow Action Master", a):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": a}).insert(
				ignore_permissions=True
			)


def create_admission_workflow():
	"""Admission approval workflow on Program Enrollment:
	Draft -> Pending Principal Approval -> Enrolled."""
	if frappe.db.exists("Workflow", "Admission Approval"):
		return

	_ensure_workflow_masters(
		state_names=["Draft", "Pending Principal Approval", "Enrolled"],
		action_names=["Apply for Approval", "Approve", "Reject"],
	)

	# Ensure the Education roles we transition with exist; already handled by create_roles.
	states = [
		{"state": "Draft", "doc_status": "0", "allow_edit": "School Admin"},
		{"state": "Pending Principal Approval", "doc_status": "0", "allow_edit": "Principal"},
		{"state": "Enrolled", "doc_status": "1", "allow_edit": "Principal"},
	]
	transitions = [
		{
			"state": "Draft",
			"action": "Apply for Approval",
			"next_state": "Pending Principal Approval",
			"allowed": "School Admin",
		},
		{
			"state": "Pending Principal Approval",
			"action": "Approve",
			"next_state": "Enrolled",
			"allowed": "Principal",
		},
		{
			"state": "Pending Principal Approval",
			"action": "Reject",
			"next_state": "Draft",
			"allowed": "Principal",
		},
	]
	frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": "Admission Approval",
			"document_type": "Program Enrollment",
			"is_active": 1,
			"override_status": 0,
			"send_email_alert": 0,
			"workflow_state_field": "workflow_state",
			"states": states,
			"transitions": transitions,
		}
	).insert(ignore_permissions=True)


def _grant(dt, role, rights):
	if not frappe.db.exists("DocType", dt):
		return
	# add a permlevel-0 perm row for this role if absent, then ensure each right.
	has_perm = any(
		p.role == role
		for p in frappe.get_all(
			"Custom DocPerm",
			filters={"parent": dt, "role": role, "permlevel": 0},
			fields=["role"],
		)
	) or any(p.role == role and p.permlevel == 0 for p in frappe.get_meta(dt).permissions)
	if not has_perm:
		add_permission(dt, role, 0)
	for right in ["read", "select", *rights]:
		update_permission_property(dt, role, 0, right, 1, validate=False)


def grant_permissions():
	for role, doctypes in ROLE_READ_PERMS.items():
		for dt in doctypes:
			_grant(dt, role, [])
	for role, perms in ROLE_WRITE_PERMS.items():
		for dt, rights in perms.items():
			_grant(dt, role, rights)


def create_grading_scales():
	"""Seed the CBSE 9-point scale so report cards grade out of the box. Schools on
	another board add their own Grading Scale; nothing forces this one."""
	if not frappe.db.exists("DocType", "Grading Scale") or frappe.db.exists(
		"Grading Scale", CBSE_GRADING_SCALE
	):
		return
	gs = frappe.get_doc(
		{
			"doctype": "Grading Scale",
			"grading_scale_name": CBSE_GRADING_SCALE,
			"description": "CBSE 9-point grading, Classes IX-XII. Pass mark 33%.",
		}
	)
	for code, threshold, desc in CBSE_GRADES:
		gs.append("intervals", {"grade_code": code, "threshold": threshold, "grade_description": desc})
	gs.insert(ignore_permissions=True)
	gs.submit()


PLACEHOLDER_ZOOM = "PLACEHOLDER - School Zoom (replace before use)"


def create_zoom_placeholder_settings():
	"""Create a DISABLED LMS Zoom Settings row with obvious placeholder creds.

	The school must replace these with a real Zoom Server-to-Server OAuth app
	(account_id / client_id / client_secret) and enable it. Left disabled so no
	live Zoom API call is ever made with fake creds.
	"""
	if not frappe.db.exists("DocType", "LMS Zoom Settings"):
		return
	if frappe.db.exists("LMS Zoom Settings", {"account_name": PLACEHOLDER_ZOOM}):
		return
	frappe.get_doc(
		{
			"doctype": "LMS Zoom Settings",
			"enabled": 0,
			"account_name": PLACEHOLDER_ZOOM,
			"member": "Administrator",
			"account_id": "REPLACE_WITH_ZOOM_ACCOUNT_ID",
			"client_id": "REPLACE_WITH_ZOOM_CLIENT_ID",
			"client_secret": "REPLACE_WITH_ZOOM_CLIENT_SECRET",
		}
	).insert(ignore_permissions=True)


def after_install():
	run()


def run():
	create_roles()
	create_custom_field_records()
	ensure_defaults()
	create_property_setters()
	apply_student_email_requirement(get_settings().require_student_email)
	create_admission_workflow()
	create_zoom_placeholder_settings()
	create_grading_scales()
	grant_permissions()
	set_guardian_landing()
	frappe.db.commit()
