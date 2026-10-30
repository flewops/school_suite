import frappe
from school_suite import api


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/parent"
        raise frappe.Redirect

    context.no_cache = 1
    context.show_sidebar = False
    children = api.get_my_children()
    context.children = [api.get_student_dashboard(c["name"]) for c in children]
    context.guardian_name = frappe.db.get_value(
        "Guardian", {"user": frappe.session.user}, "guardian_name"
    ) or frappe.session.user
    return context
