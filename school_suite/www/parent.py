import frappe
from frappe.utils import fmt_money

from school_suite import api


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/parent"
		raise frappe.Redirect

	context.no_cache = 1
	context.show_sidebar = False
	names = api.get_my_children_names()
	context.children = [
		api.get_student_dashboard(name, frappe.form_dict.get("academic_year")) for name in names
	]
	for c in context.children:
		c["fees_fmt"] = {
			k: fmt_money(c["fees"][k], currency="INR") for k in ("billed", "paid", "outstanding", "arrears")
		}
	context.academic_year = context.children[0].academic_year if context.children else None
	context.academic_years = _academic_years(names, context.academic_year)
	context.guardian_name = (
		frappe.db.get_value("Guardian", {"user": frappe.session.user}, "guardian_name") or frappe.session.user
	)
	return context


def _academic_years(students, current):
	"""The years a parent can look at, newest first: those their children were
	enrolled in, and the one on show."""
	years = set(
		frappe.get_all(
			"Program Enrollment",
			filters={"student": ["in", students], "docstatus": 1},
			pluck="academic_year",
		)
	)
	years.add(current)
	return frappe.get_all(
		"Academic Year",
		filters={"name": ["in", [year for year in years if year]]},
		order_by="year_start_date desc",
		pluck="name",
	)
