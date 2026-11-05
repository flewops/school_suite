from urllib.parse import quote

import frappe
from frappe import _
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
	context.data = api.get_principal_dashboard(frappe.form_dict.get("academic_year"))
	context.academic_years = frappe.get_all("Academic Year", order_by="year_start_date desc", pluck="name")
	context.money = lambda amount: fmt_money(amount, currency="INR")
	context.fee_reports = _fee_reports()
	return context


def _fee_reports():
	"""Native reports for drilling into the fee figures, those this user may open."""
	reports = (
		(_("Per-student balances"), "Student Fee Collection"),
		(_("Class-wise, by date"), "Program Wise Fee Collection"),
		(_("Overdue by age"), "Accounts Receivable"),
	)
	return [
		(label, f"/desk/query-report/{quote(name)}")
		for label, name in reports
		if frappe.db.exists("Report", name) and frappe.get_doc("Report", name).is_permitted()
	]
