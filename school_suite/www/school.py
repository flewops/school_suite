import frappe

from school_suite.permissions import FULL_ACCESS_ROLES, _roles

no_cache = 1


def get_context(context):
	"""Route behind the School tile: send each role to where its work starts."""
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/school"
		raise frappe.Redirect
	roles = _roles()
	if roles & FULL_ACCESS_ROLES:
		target = "/principal"
	elif "Teacher" in roles:
		target = "/app/student-attendance-tool"
	elif "Accountant" in roles:
		target = "/app/fee-schedule"
	elif "Parent/Guardian" in roles:
		target = "/parent"
	else:
		target = "/me"
	frappe.local.flags.redirect_location = target
	raise frappe.Redirect
