"""Pluggable notifications (SMS / WhatsApp / Email).

Sends go through Frappe's own channels when the school has configured them, so
going live is configuration, not code:
  * SMS   -> native SMS Settings (any HTTP gateway: MSG91, Gupshup, ...; DLT
            template / entity IDs go in its static parameters), or an app that
            implements Frappe's `send_sms` hook.
  * Email -> frappe.sendmail via the outgoing Email Account.
  * WhatsApp has no native channel; plug a vendor class into PROVIDERS.
Until a channel is configured its messages are only logged (dummy provider), so
a pilot makes no external calls.

    from school_suite.notify import send
    send("sms", "+919999999999", "Fees due for Arya")
    send("email", "parent@example.com", "Report card ready", subject="Report Card")
"""

import frappe
from frappe import _
from frappe.utils import formatdate, getdate, nowdate

from school_suite.school_suite.doctype.school_suite_settings.school_suite_settings import get_settings


class DummyProvider:
	channel = "generic"

	def send(self, to, message, subject=None):
		payload = {
			"channel": self.channel,
			"to": to,
			"subject": subject,
			"message": message,
			"provider": "dummy",
			"sent": True,
		}
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


class NativeSMSProvider(DummySMSProvider):
	"""Frappe SMS Settings when a gateway (or a `send_sms` hook) is configured."""

	def send(self, to, message, subject=None):
		if not (
			frappe.get_hooks("send_sms") or frappe.db.get_single_value("SMS Settings", "sms_gateway_url")
		):
			return super().send(to, message, subject)
		# The private variant skips the interactive "may this user send SMS" check: this is
		# called from server code (e.g. a background job) on the school's behalf.
		from frappe.core.doctype.sms_settings.sms_settings import _send_sms

		_send_sms([to], message, success_msg=False)
		return {"channel": self.channel, "to": to, "message": message, "provider": "sms_settings"}


class FrappeEmailProvider(DummyEmailProvider):
	"""frappe.sendmail when an outgoing Email Account exists."""

	def send(self, to, message, subject=None):
		subject = subject or _("Message from school")
		if not frappe.db.exists("Email Account", {"enable_outgoing": 1}):
			return super().send(to, message, subject)
		frappe.sendmail(recipients=[to], subject=subject, message=message)
		return {"channel": self.channel, "to": to, "subject": subject, "provider": "email_queue"}


# Channel -> provider. Replace an entry with a vendor class to add a channel.
PROVIDERS = {
	"sms": NativeSMSProvider(),
	"whatsapp": DummyWhatsAppProvider(),
	"email": FrappeEmailProvider(),
}


# Not whitelisted on purpose: with a real vendor every call costs money and goes
# out under the school's sender ID, so only server code may trigger a send.
def send(channel, to, message, subject=None):
	provider = PROVIDERS.get(channel)
	if not provider:
		frappe.throw(_("No provider configured for channel '{0}'").format(channel))
	return provider.send(to, message, subject)


def notify_guardians(student, message, channel="sms", subject=None):
	"""Send a message to all guardians of a student on the given channel."""
	guardians = frappe.get_all(
		"Student Guardian",
		filters={"parent": student, "parenttype": "Student"},
		pluck="guardian",
	)
	results = []
	for g in guardians:
		gd = frappe.db.get_value("Guardian", g, ["mobile_number", "email_address"], as_dict=True)
		to = (gd.email_address if channel == "email" else gd.mobile_number) if gd else None
		if to:
			results.append(send(channel, to, message, subject))
	return results


# --------------------------------------------------------------------------- #
# Same-day absence alert to guardians
# --------------------------------------------------------------------------- #
def on_attendance_submit(doc, method=None):
	"""doc_event: queue a guardian alert when a student is marked Absent today.
	Back-filled registers for past dates don't text parents."""
	if doc.status != "Absent" or not get_settings().absence_alert_enabled:
		return
	if getdate(doc.date) != getdate(nowdate()):
		return
	frappe.enqueue(
		"school_suite.notify.send_absence_alert",
		queue="short",
		enqueue_after_commit=True,
		attendance=doc.name,
		job_id=f"school_suite:absence_alert:{doc.name}",
		deduplicate=True,
	)


def send_absence_alert(attendance):
	a = frappe.db.get_value(
		"Student Attendance",
		attendance,
		["student", "student_name", "date", "status", "docstatus"],
		as_dict=True,
	)
	if not a or a.status != "Absent" or a.docstatus != 1:
		return []
	# Period-wise attendance creates several rows a day; alert only once.
	if frappe.db.exists(
		"Student Attendance",
		{
			"student": a.student,
			"date": a.date,
			"status": "Absent",
			"docstatus": 1,
			"name": ["!=", attendance],
			"creation": ["<", frappe.db.get_value("Student Attendance", attendance, "creation")],
		},
	):
		return []
	settings = get_settings()
	# Plain replacement, not str.format: an edited template with a stray brace must
	# not break the job.
	message = settings.absence_alert_template.replace("{student_name}", a.student_name or "").replace(
		"{date}", formatdate(a.date, "dd-MM-yyyy")
	)
	return notify_guardians(
		a.student, message, channel=settings.absence_alert_channel, subject=_("Absence alert")
	)
