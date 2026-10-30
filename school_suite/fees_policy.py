"""Phase 5 — Indian fee policy helpers (thin layer over native Education fees).

Native Education already provides: term-wise Fee Structure (academic_term),
Fee Schedule, per-component discount (Fee Component.discount), and sequential
receipt numbering (Fees naming series). This module adds only the *policies* that
are not native: sibling discount, scholarship/concession, and late fee.

These operate on an in-memory Fees doc *before* submit (so the native totals
recompute), or compute amounts the caller can apply. Nothing here edits core.
"""

import frappe
from frappe.utils import getdate, nowdate, date_diff, flt

# Policy knobs (could be moved to a Settings single later).
SIBLING_DISCOUNT = {1: 0, 2: 10, 3: 15}   # by birth order among enrolled siblings
SIBLING_DISCOUNT_DEFAULT = 15             # 4th child onwards
LATE_FEE_PER_DAY = 50
LATE_FEE_CAP = 1000


# --------------------------------------------------------------------------- #
# Sibling discount
# --------------------------------------------------------------------------- #
def get_siblings(student):
    """Other active students who share at least one guardian with `student`."""
    guardians = frappe.get_all(
        "Student Guardian", filters={"parent": student, "parenttype": "Student"},
        pluck="guardian",
    )
    if not guardians:
        return []
    rows = frappe.get_all(
        "Student Guardian",
        filters={"guardian": ["in", guardians], "parenttype": "Student"},
        pluck="parent",
    )
    return sorted({s for s in rows if s != student})


def sibling_rank(student):
    """1 for the eldest enrolled child, 2 for the next, etc. (by join date)."""
    family = get_siblings(student) + [student]
    dated = []
    for s in family:
        jd = frappe.db.get_value("Student", s, "joining_date") or nowdate()
        dated.append((getdate(jd), s))
    dated.sort()
    return [s for _, s in dated].index(student) + 1


def sibling_discount_percent(student):
    return SIBLING_DISCOUNT.get(sibling_rank(student), SIBLING_DISCOUNT_DEFAULT)


# --------------------------------------------------------------------------- #
# Concession / scholarship (percentage off, applied via native component field)
# --------------------------------------------------------------------------- #
def apply_concession(fee_doc, percent, reason=""):
    """Apply a percentage discount to every component of an unsaved Fees doc,
    using the native Fee Component.discount field. Returns the new total."""
    percent = flt(percent)
    for c in fee_doc.components:
        c.discount = percent
        c.total = flt(c.amount) * (100 - percent) / 100.0
    if reason:
        note = f"Concession {percent}% ({reason})"
        fee_doc.remarks = (fee_doc.get("remarks") or "")
        # 'remarks' may not exist on Fees; keep the reason in a comment instead.
    total = sum(flt(c.total) for c in fee_doc.components)
    return {"percent": percent, "reason": reason, "new_total": total}


def apply_sibling_discount(fee_doc):
    """Convenience: compute + apply the sibling discount for the fee's student."""
    pct = sibling_discount_percent(fee_doc.student)
    rank = sibling_rank(fee_doc.student)
    if pct:
        apply_concession(fee_doc, pct, reason=f"Sibling discount (child #{rank})")
    return {"rank": rank, "percent": pct}


# --------------------------------------------------------------------------- #
# Late fee
# --------------------------------------------------------------------------- #
def late_fee_amount(fee_name, as_of=None):
    """Compute (but do not post) the late fee for an overdue, unpaid fee."""
    as_of = getdate(as_of or nowdate())
    fee = frappe.db.get_value(
        "Fees", fee_name, ["due_date", "outstanding_amount"], as_dict=True
    )
    if not fee or not fee.due_date or flt(fee.outstanding_amount) <= 0:
        return {"days_overdue": 0, "late_fee": 0}
    overdue = max(0, date_diff(as_of, getdate(fee.due_date)))
    return {"days_overdue": overdue,
            "late_fee": min(overdue * LATE_FEE_PER_DAY, LATE_FEE_CAP)}
