# Copyright (c) 2026, School Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class SchoolSuiteSettings(Document):
	def validate(self):
		for field in (
			"sibling_discount_second",
			"sibling_discount_third_onwards",
			"low_attendance_threshold",
		):
			if not 0 <= flt(self.get(field)) <= 100:
				frappe.throw(_("{0} must be between 0 and 100.").format(self.meta.get_label(field)))
		if flt(self.late_fee_per_day) < 0 or flt(self.late_fee_cap) < 0:
			frappe.throw(_("Late fee amounts cannot be negative."))

	def on_update(self):
		from school_suite.setup.install import apply_student_email_requirement

		apply_student_email_requirement(self.require_student_email)


def get_settings():
	"""Cached School Suite Settings (cache is cleared on save)."""
	return frappe.get_cached_doc("School Suite Settings")


def ensure_defaults():
	"""Persist DocType defaults for unset fields. Run on every install/migrate.

	A Single shows its defaults only while nothing at all is stored for it: once
	any one value is written (a save, or db.set_single_value from a script), the
	rest load as empty. Likewise a field added in a later release starts empty.
	So the defaults are always written to the database.
	"""
	doc = frappe.get_doc("School Suite Settings")
	changed = not frappe.db.get_singles_dict(doc.doctype)
	for df in doc.meta.fields:
		if df.default is not None and doc.get(df.fieldname) in (None, ""):
			doc.set(df.fieldname, df.default)
			changed = True
	if changed:
		doc.flags.ignore_permissions = True
		doc.save()
