import frappe
from school_suite import api
from school_suite.permissions import _roles, FULL_ACCESS_ROLES


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/principal"
        raise frappe.Redirect
    if not (_roles() & FULL_ACCESS_ROLES):
        raise frappe.PermissionError("Only Principal / School Admin may view this page.")
    context.no_cache = 1
    context.show_sidebar = False
    context.data = api.get_principal_dashboard()
    return context
