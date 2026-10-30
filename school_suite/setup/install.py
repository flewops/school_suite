"""Idempotent setup run on install/migrate: roles, custom fields, property
setters and the admission workflow. These records are also exported as fixtures
(see hooks.py `fixtures`) so a fresh install reproduces them verbatim.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

# Base read access per role (row-level narrowing is done by permission_query_conditions).
# Stored as Custom DocPerm — core app permissions are never edited.
ROLE_READ_PERMS = {
    "Teacher": ["Student", "Student Group", "Student Attendance", "Assessment Result",
                "Course Schedule", "Program Enrollment", "Course Enrollment"],
    "Parent/Guardian": ["Student", "Student Attendance", "Assessment Result",
                        "Course Schedule", "Fees", "Program Enrollment"],
    "Student": ["Student", "Student Attendance", "Assessment Result", "Course Schedule",
                "Fees", "Program Enrollment", "Course Enrollment"],
    "Accountant": ["Fees", "Student", "Program Enrollment"],
}

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
            frappe.get_doc({
                "doctype": "Role",
                "role_name": role,
                "desk_access": role != "Parent/Guardian",  # guardians use the portal, not the desk
            }).insert(ignore_permissions=True)


def create_custom_field_records():
    create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)


def create_property_setters():
    # Property Setter 1: make the student e-mail mandatory so every Student can be
    # linked to a login (needed for the LMS join + portals).
    frappe.make_property_setter({
        "doctype": "Student",
        "fieldname": "student_email_id",
        "property": "reqd",
        "value": "1",
        "property_type": "Check",
    }, is_system_generated=False)

    # Property Setter 2: fix an Education v16 bug. Fees.income_account has
    # fetch_from="fee_structure.income_account", but Fee Structure no longer has
    # an income_account field, so saving any Fees doc raises
    # "Unknown column 'income_account'". Clear the broken fetch_from here (the
    # income account is set explicitly / resolved from the Item instead).
    if frappe.get_meta("Fees").get_field("income_account") and not \
            frappe.get_meta("Fee Structure").get_field("income_account"):
        frappe.make_property_setter({
            "doctype": "Fees",
            "fieldname": "income_account",
            "property": "fetch_from",
            "value": "",
            "property_type": "Small Text",
        }, is_system_generated=False)


def _ensure_workflow_masters(state_names, action_names):
    """Workflow states/actions must exist as master records before a Workflow
    can reference them."""
    for s in state_names:
        if not frappe.db.exists("Workflow State", s):
            frappe.get_doc({
                "doctype": "Workflow State", "workflow_state_name": s, "style": ""
            }).insert(ignore_permissions=True)
    for a in action_names:
        if not frappe.db.exists("Workflow Action Master", a):
            frappe.get_doc({
                "doctype": "Workflow Action Master", "workflow_action_name": a
            }).insert(ignore_permissions=True)


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
        {"state": "Draft", "action": "Apply for Approval",
         "next_state": "Pending Principal Approval", "allowed": "School Admin"},
        {"state": "Pending Principal Approval", "action": "Approve",
         "next_state": "Enrolled", "allowed": "Principal"},
        {"state": "Pending Principal Approval", "action": "Reject",
         "next_state": "Draft", "allowed": "Principal"},
    ]
    frappe.get_doc({
        "doctype": "Workflow",
        "workflow_name": "Admission Approval",
        "document_type": "Program Enrollment",
        "is_active": 1,
        "override_status": 0,
        "send_email_alert": 0,
        "workflow_state_field": "workflow_state",
        "states": states,
        "transitions": transitions,
    }).insert(ignore_permissions=True)


def grant_permissions():
    for role, doctypes in ROLE_READ_PERMS.items():
        for dt in doctypes:
            if not frappe.db.exists("DocType", dt):
                continue
            # add a permlevel-0 perm row for this role if absent, then ensure read.
            has_perm = any(
                p.role == role for p in frappe.get_all(
                    "Custom DocPerm", filters={"parent": dt, "role": role, "permlevel": 0},
                    fields=["role"],
                )
            ) or any(p.role == role and p.permlevel == 0 for p in frappe.get_meta(dt).permissions)
            if not has_perm:
                add_permission(dt, role, 0)
            update_permission_property(dt, role, 0, "read", 1, validate=False)
            update_permission_property(dt, role, 0, "select", 1, validate=False)


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
    frappe.get_doc({
        "doctype": "LMS Zoom Settings",
        "enabled": 0,
        "account_name": PLACEHOLDER_ZOOM,
        "member": "Administrator",
        "account_id": "REPLACE_WITH_ZOOM_ACCOUNT_ID",
        "client_id": "REPLACE_WITH_ZOOM_CLIENT_ID",
        "client_secret": "REPLACE_WITH_ZOOM_CLIENT_SECRET",
    }).insert(ignore_permissions=True)


def after_install():
    run()


def run():
    create_roles()
    create_custom_field_records()
    create_property_setters()
    create_admission_workflow()
    create_zoom_placeholder_settings()
    grant_permissions()
    frappe.db.commit()
