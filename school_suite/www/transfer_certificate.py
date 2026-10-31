import frappe
from frappe import _

from school_suite import reports

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/principal"
		raise frappe.Redirect
	student = frappe.form_dict.get("student")
	if not student:
		frappe.throw(_("Open this page with ?student=<Student ID>."))
	# get_transfer_certificate allows Principal / School Admin only.
	context.tc = reports.get_transfer_certificate(student)
	context.school = reports.get_school_header()
	context.title = _("Transfer Certificate")
	context.show_sidebar = False
	return context
