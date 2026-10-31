"""Indian fee policy helpers (thin layer over native Education / ERPNext billing).

Education v16 bills a class through Fee Structure -> Fee Schedule -> one Sales
Invoice (or Sales Order) per student, carrying a `student` field. The older `Fees`
doctype still exists and is supported here as the legacy path.

Native already provides term-wise Fee Structures, Fee Schedules, a per-component
discount and sequential numbering. This module adds only the policies that are not
native: sibling discount, scholarship/concession, late fee, the RTE 12(1)(c) warning
and a default education SAC on fee Items. Policy values live in School Suite
Settings. It also patches one Education v16 gap: legacy Fees ignores the
component discount when totalling.
"""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, money_in_words, nowdate

from school_suite.school_suite.doctype.school_suite_settings.school_suite_settings import get_settings

FEE_ITEM_GROUP = "Fee Component"


# --------------------------------------------------------------------------- #
# Sibling discount
# --------------------------------------------------------------------------- #
def get_siblings(student):
	"""Other enrolled students who share at least one guardian with `student`."""
	guardians = frappe.get_all(
		"Student Guardian",
		filters={"parent": student, "parenttype": "Student"},
		pluck="guardian",
	)
	if not guardians:
		return []
	rows = frappe.get_all(
		"Student Guardian",
		filters={"guardian": ["in", guardians], "parenttype": "Student"},
		pluck="parent",
	)
	others = {s for s in rows if s != student}
	if not others:
		return []
	# A sibling who has left (alumni / TC issued) no longer counts toward the discount.
	return sorted(
		frappe.get_all("Student", filters={"name": ["in", list(others)], "enabled": 1}, pluck="name")
	)


def sibling_rank(student):
	"""1 for the eldest enrolled child, 2 for the next, etc.

	Birth order (date_of_birth) when every child has one; otherwise falls back to
	enrolment order (joining_date) for the whole family so the two are never mixed.
	"""
	family = [*get_siblings(student), student]
	rows = {
		s: frappe.db.get_value("Student", s, ["date_of_birth", "joining_date"], as_dict=True) for s in family
	}
	by_dob = all(r.date_of_birth for r in rows.values())
	dated = sorted(
		(getdate((r.date_of_birth if by_dob else r.joining_date) or nowdate()), s) for s, r in rows.items()
	)
	return [s for _date, s in dated].index(student) + 1


def sibling_discount_percent(student):
	rank = sibling_rank(student)
	if rank == 1:
		return 0
	settings = get_settings()
	return flt(settings.sibling_discount_second if rank == 2 else settings.sibling_discount_third_onwards)


# --------------------------------------------------------------------------- #
# Concession / scholarship (percentage off every fee line)
# --------------------------------------------------------------------------- #
def _fee_lines(doc):
	return doc.components if doc.doctype == "Fees" else doc.items


def _has_discount(doc):
	field = "discount" if doc.doctype == "Fees" else "discount_percentage"
	return any(flt(line.get(field)) for line in _fee_lines(doc))


def apply_concession(fee_doc, percent, reason=""):
	"""Apply a percentage discount to every line of an unsaved fee bill (Sales
	Invoice / Sales Order from a Fee Schedule, or legacy Fees). The bill's own
	validate recomputes its totals. Returns the expected new total."""
	percent = flt(percent)
	if not 0 <= percent <= 100:
		frappe.throw(_("Concession must be between 0 and 100 percent, got {0}.").format(percent))
	total = 0.0
	for line in _fee_lines(fee_doc):
		if fee_doc.doctype == "Fees":
			line.discount = percent
			line.total = flt(line.amount) * (100 - percent) / 100.0
			total += line.total
			continue
		# ERPNext keeps a non-zero rate and resets the discount to match it. With a
		# zero rate it derives rate = list price - discount itself, and Stock
		# Settings' "auto insert price list rate" doesn't save the discounted rate
		# as the Item Price (it skips lines without a rate).
		list_rate = flt(line.price_list_rate) or flt(line.rate)
		line.price_list_rate = list_rate
		line.discount_percentage = percent
		line.discount_amount = 0
		line.rate = 0
		total += list_rate * (100 - percent) / 100.0 * flt(line.qty or 1)
	return {"percent": percent, "reason": reason, "new_total": total}


def apply_sibling_discount(fee_doc):
	"""Compute + apply the sibling discount for the bill's student."""
	rank = sibling_rank(fee_doc.student)
	pct = sibling_discount_percent(fee_doc.student)
	if pct:
		apply_concession(fee_doc, pct, reason=_("Sibling discount (child #{0})").format(rank))
	return {"rank": rank, "percent": pct}


def _is_fee_bill(doc):
	if doc.doctype == "Fees":
		return True
	if doc.get("is_return") or not doc.get("student"):
		return False
	if doc.get("fee_schedule"):
		return True
	return bool(doc.items) and all(
		frappe.get_cached_value("Item", line.item_code, "item_group") == FEE_ITEM_GROUP for line in doc.items
	)


def before_fee_validate(doc, method=None):
	"""doc_event (Sales Invoice / Fees before_validate): auto-apply the sibling
	discount to a new fee bill, if enabled in School Suite Settings. Bills that
	already carry a discount (Fee Structure or a manual concession) and RTE seats
	are left alone."""
	if not doc.is_new() or not get_settings().auto_apply_sibling_discount or not _is_fee_bill(doc):
		return
	if _has_discount(doc) or frappe.db.get_value("Student", doc.student, "rte_admission"):
		return
	result = apply_sibling_discount(doc)
	if result["percent"]:
		frappe.msgprint(
			_("Sibling discount of {0}% applied (child #{1}).").format(result["percent"], result["rank"]),
			alert=True,
		)


def recompute_legacy_fee_totals(doc, method=None):
	"""doc_event (Fees.validate): Education v16's Fees.calculate_total sums the
	gross component amount and ignores the component discount, so a discounted
	fee is billed in full. Recompute after the native validate."""
	if doc.docstatus == 2:
		return
	for c in doc.components:
		c.total = flt(c.amount) * (100 - flt(c.discount)) / 100.0
	doc.grand_total = sum(flt(c.total) for c in doc.components)
	doc.outstanding_amount = doc.grand_total
	doc.grand_total_in_words = money_in_words(doc.grand_total, doc.get("currency"))


# --------------------------------------------------------------------------- #
# Fee Items: default GST SAC
# --------------------------------------------------------------------------- #
def default_fee_item_sac(doc, method=None):
	"""doc_event (Item.before_validate): Education v16 auto-creates an Item for
	every Fee Category without an HSN/SAC, which India Compliance rejects, so
	saving a Fee Category fails on a fresh site. Fill the default education SAC;
	change it on the Item where a fee is not tuition (e.g. transport)."""
	if (
		doc.item_group == FEE_ITEM_GROUP
		and doc.meta.has_field("gst_hsn_code")
		and not doc.get("gst_hsn_code")
	):
		doc.gst_hsn_code = get_settings().default_fee_sac


# --------------------------------------------------------------------------- #
# RTE 12(1)(c) seats
# --------------------------------------------------------------------------- #
def warn_if_rte(doc, method=None):
	"""doc_event (Sales Invoice / Fees validate): a child on an RTE 12(1)(c) seat
	must not be charged; the State reimburses the school. Warn, don't block: what
	(if anything) may be billed for such a seat varies by State."""
	student = doc.get("student")
	if not student or flt(doc.grand_total) <= 0:
		return
	if frappe.db.get_value("Student", student, "rte_admission"):
		frappe.msgprint(
			_(
				"{0} is admitted under RTE 12(1)(c). Fees for this seat are reimbursed by the "
				"State and should not be charged to the parent."
			).format(doc.get("student_name") or student),
			title=_("RTE student"),
			indicator="orange",
		)


# --------------------------------------------------------------------------- #
# Late fee
# --------------------------------------------------------------------------- #
def late_fee_amount(fee_name, as_of=None, doctype=None):
	"""Compute (but do not post) the late fee for an overdue, unpaid fee bill
	(a Sales Invoice, or a legacy Fees record; detected from the name)."""
	doctype = doctype or ("Fees" if frappe.db.exists("Fees", fee_name) else "Sales Invoice")
	as_of = getdate(as_of or nowdate())
	fee = frappe.db.get_value(doctype, fee_name, ["due_date", "outstanding_amount"], as_dict=True)
	if not fee or not fee.due_date or flt(fee.outstanding_amount) <= 0:
		return {"days_overdue": 0, "late_fee": 0}
	settings = get_settings()
	overdue = max(0, date_diff(as_of, getdate(fee.due_date)))
	return {
		"days_overdue": overdue,
		"late_fee": min(overdue * flt(settings.late_fee_per_day), flt(settings.late_fee_cap)),
	}
