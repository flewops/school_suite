import frappe
from frappe.utils import fmt_money

from school_suite import api
from school_suite.permissions import FULL_ACCESS_ROLES, _roles


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/principal"
		raise frappe.Redirect
	if not (_roles() & FULL_ACCESS_ROLES):
		raise frappe.PermissionError("Only Principal / School Admin may view this page.")
	context.no_cache = 1
	context.show_sidebar = False
	context.data = api.get_principal_dashboard()
	context.fee_fmt = {k: fmt_money(v, currency="INR") for k, v in context.data["fee_collection"].items()}
	return context
