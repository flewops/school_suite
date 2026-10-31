import frappe
from frappe.utils import fmt_money

from school_suite import api


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/parent"
		raise frappe.Redirect

	context.no_cache = 1
	context.show_sidebar = False
	context.children = [api.get_student_dashboard(name) for name in api.get_my_children_names()]
	for c in context.children:
		c["fees_fmt"] = {
			k: fmt_money(c["fees"][k], currency="INR") for k in ("billed", "paid", "outstanding")
		}
	context.guardian_name = (
		frappe.db.get_value("Guardian", {"user": frappe.session.user}, "guardian_name") or frappe.session.user
	)
	return context
