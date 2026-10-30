"""Phase 5 — pluggable notifications (SMS / WhatsApp / Email).

Frappe already has an Email + Notification + SMS Settings framework natively.
This module adds a thin, provider-agnostic dispatch so a school can plug in any
SMS/WhatsApp vendor later. For the pilot, DUMMY providers only *log* the message
(no external calls, no credentials). Swap the class in PROVIDERS for a real one.

    from school_suite.notify import send
    send("sms", "+919999999999", "Fees due for Arya")
    send("whatsapp", "+919999999999", "Class at 9am")
    send("email", "parent@example.com", "Report card ready", subject="Report Card")
"""

import frappe


class DummyProvider:
    channel = "generic"

    def send(self, to, message, subject=None):
        payload = {"channel": self.channel, "to": to, "subject": subject,
                   "message": message, "provider": "dummy", "sent": True}
        # Log so it is observable without any external service or credential.
        frappe.logger("school_suite.notify").info(payload)
        # Keep an in-request trail for tests/verification.
        frappe.flags.setdefault("school_suite_sent", []).append(payload)
        return payload


class DummySMSProvider(DummyProvider):
    channel = "sms"


class DummyWhatsAppProvider(DummyProvider):
    channel = "whatsapp"


class DummyEmailProvider(DummyProvider):
    channel = "email"

    def send(self, to, message, subject=None):
        # A real deployment would use frappe.sendmail; dummy just logs.
        return super().send(to, message, subject or "(no subject)")


# Channel -> provider. Point these at real vendor classes to go live.
PROVIDERS = {
    "sms": DummySMSProvider(),
    "whatsapp": DummyWhatsAppProvider(),
    "email": DummyEmailProvider(),
}


@frappe.whitelist()
def send(channel, to, message, subject=None):
    provider = PROVIDERS.get(channel)
    if not provider:
        frappe.throw(f"No provider configured for channel '{channel}'")
    return provider.send(to, message, subject)


def notify_guardians(student, message, channel="sms", subject=None):
    """Send a message to all guardians of a student on the given channel."""
    guardians = frappe.get_all(
        "Student Guardian", filters={"parent": student, "parenttype": "Student"},
        pluck="guardian",
    )
    results = []
    for g in guardians:
        gd = frappe.db.get_value("Guardian", g, ["mobile_number", "email_address"], as_dict=True)
        to = (gd.email_address if channel == "email" else gd.mobile_number) if gd else None
        if to:
            results.append(send(channel, to, message, subject))
    return results
