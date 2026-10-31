import frappe
from frappe import _

from school_suite import reports

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/parent"
		raise frappe.Redirect
	student = frappe.form_dict.get("student")
	if not student:
		frappe.throw(_("Open this page with ?student=<Student ID>."))
	# get_report_card enforces who may see this student (parent, teacher, staff).
	context.card = reports.get_report_card(
		student, frappe.form_dict.get("academic_term"), frappe.form_dict.get("board")
	)
	context.school = reports.get_school_header()
	context.title = _("Report Card")
	context.show_sidebar = False
	return context
