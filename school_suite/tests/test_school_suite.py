"""Integration tests for School Suite.

Run on a test site with all required apps installed:
	bench --site <site> set-config allow_tests true
	bench --site <site> run-tests --app school_suite

Builds on the fake demo school (school_suite.setup.demo_data) plus the fee
masters from the flow test.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, nowdate

from school_suite import api, fees_policy, notify, permissions, reports
from school_suite import online_learning as ol
from school_suite.school_suite.doctype.school_suite_settings.school_suite_settings import get_settings
from school_suite.setup import demo_data, flow_test

TEACHER = "teacher_sunita@demo.school"  # teaches Class 1A (Arya, Bodhi)
GUARDIAN_MEERA = "guardian_meera@demo.school"  # Arya + Bodhi
GUARDIAN_RAVI = "guardian_ravi@demo.school"  # Chetan (Class 1B)
STUDENT_ARYA = "arya@demo.school"
SCHOOL_ADMIN = "school_admin@demo.school"
PRINCIPAL = "principal@demo.school"
ACCOUNTANT = "accountant@demo.school"


def student(first_name):
	return frappe.db.get_value("Student", {"first_name": first_name}, "name")


class TestSchoolSuite(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		# Education validates attendance against the *default* company's holiday list;
		# the demo school must be that company (the test bootstrap makes _Test Company).
		frappe.defaults.set_global_default("company", demo_data._company())
		demo_data.run()
		flow_test.prereq()  # fee category / item / structure / room
		cls.item = flow_test.ctx["item"]
		cls.income = flow_test.ctx["income"]
		cls.fee_structure = flow_test.ctx["fee_structure"]
		frappe.db.commit()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		frappe.clear_document_cache("School Suite Settings", "School Suite Settings")

	def set_setting(self, field, value):
		frappe.db.set_single_value("School Suite Settings", field, value)
		frappe.clear_document_cache("School Suite Settings", "School Suite Settings")

	# ----------------------------------------------------------------- schema
	def test_schema_and_settings_defaults(self):
		meta = frappe.get_meta("Student")
		for field in ("admission_number", "apaar_id", "pen", "social_category", "is_cwsn", "rte_admission"):
			self.assertTrue(meta.get_field(field), field)
			self.assertEqual(
				frappe.db.get_value("Custom Field", {"dt": "Student", "fieldname": field}, "module"),
				"School Suite",
			)
		self.assertTrue(frappe.get_meta("Company").get_field("udise_code"))
		settings = get_settings()
		self.assertEqual(flt(settings.late_fee_per_day), 50)
		self.assertEqual(flt(settings.low_attendance_threshold), 75)
		self.assertEqual(settings.default_fee_sac, "999220")
		gs = frappe.get_doc("Grading Scale", "CBSE 9-Point")
		self.assertEqual((gs.docstatus, len(gs.intervals)), (1, 8))

	def test_settings_validation(self):
		doc = frappe.get_doc("School Suite Settings")
		doc.sibling_discount_second = 150
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_student_email_requirement_follows_setting(self):
		doc = frappe.get_doc("School Suite Settings")
		doc.require_student_email = 0
		doc.save()
		frappe.clear_cache(doctype="Student")
		self.assertFalse(frappe.get_meta("Student").get_field("student_email_id").reqd)
		doc.require_student_email = 1
		doc.save()
		frappe.clear_cache(doctype="Student")
		self.assertTrue(frappe.get_meta("Student").get_field("student_email_id").reqd)

	# ------------------------------------------------------------ permissions
	def test_teacher_can_mark_own_class_only(self):
		self.assertTrue(frappe.has_permission("Student Attendance", "submit", user=TEACHER))
		self.assertTrue(frappe.has_permission("Assessment Result", "create", user=TEACHER))
		self.assertFalse(frappe.has_permission("Assessment Result", "submit", user=TEACHER))
		own = frappe.get_doc(
			{
				"doctype": "Student Attendance",
				"student": student("Arya"),
				"date": nowdate(),
				"status": "Present",
			}
		)
		other = frappe.get_doc(
			{
				"doctype": "Student Attendance",
				"student": student("Chetan"),
				"date": nowdate(),
				"status": "Present",
			}
		)
		self.assertTrue(frappe.has_permission("Student Attendance", "create", doc=own, user=TEACHER))
		self.assertFalse(frappe.has_permission("Student Attendance", "create", doc=other, user=TEACHER))

	def test_single_document_guards(self):
		self.assertTrue(frappe.has_permission("Student Group", "read", doc="Class 1A", user=TEACHER))
		self.assertFalse(frappe.has_permission("Student Group", "read", doc="Class 1B", user=TEACHER))
		# Parents have no role access to Student Group; check the hook's own logic.
		self.assertTrue(permissions.student_group_has_permission("Class 1B", user=GUARDIAN_RAVI))
		self.assertFalse(permissions.student_group_has_permission("Class 1A", user=GUARDIAN_RAVI))
		schedule_1a = frappe._dict(student_group="Class 1A", instructor=None)
		self.assertTrue(permissions.course_schedule_has_permission(schedule_1a, user=GUARDIAN_MEERA))
		self.assertFalse(permissions.course_schedule_has_permission(schedule_1a, user=GUARDIAN_RAVI))

	def test_staff_role_profiles_give_working_access(self):
		self.assertTrue({"School Admin", "Academics User"} <= set(frappe.get_roles(SCHOOL_ADMIN)))
		for doctype in ("Student", "Guardian", "Program Enrollment", "Student Group"):
			self.assertTrue(frappe.has_permission(doctype, "create", user=SCHOOL_ADMIN), doctype)
		self.assertTrue(frappe.has_permission("Program Enrollment", "submit", user=PRINCIPAL))
		for doctype, ptype in (
			("Fee Schedule", "create"),
			("Sales Invoice", "submit"),
			("Payment Entry", "submit"),
			("Student Group", "read"),
			("Education Settings", "read"),
		):
			self.assertTrue(frappe.has_permission(doctype, ptype, user=ACCOUNTANT), doctype)
		# the accountant bills every class but sees no marks and no child dashboard
		self.assertFalse(frappe.has_permission("Assessment Result", "read", user=ACCOUNTANT))
		frappe.set_user(ACCOUNTANT)
		self.assertEqual(sorted(frappe.get_list("Student Group", pluck="name")), ["Class 1A", "Class 1B"])
		self.assertIn("Chetan", frappe.get_list("Student", pluck="first_name"))
		self.assertRaises(frappe.PermissionError, api.get_student_dashboard, student("Arya"))

	def test_admission_workflow_with_real_staff_logins(self):
		from frappe.model.workflow import apply_workflow

		frappe.set_user(SCHOOL_ADMIN)
		pe = frappe.get_doc(
			{
				"doctype": "Program Enrollment",
				"student": student("Chetan"),
				"program": "Grade 5",
				"academic_year": demo_data.academic_year_name(),
				"enrollment_date": nowdate(),
			}
		).insert()
		pe = apply_workflow(pe, "Apply for Approval")
		self.assertEqual(pe.workflow_state, "Pending Principal Approval")
		self.assertRaises(frappe.ValidationError, apply_workflow, pe, "Approve")  # not the admin's call
		frappe.set_user(PRINCIPAL)
		pe = apply_workflow(frappe.get_doc("Program Enrollment", pe.name), "Approve")
		self.assertEqual((pe.workflow_state, pe.docstatus), ("Enrolled", 1))

	def test_list_queries_are_row_restricted(self):
		frappe.set_user(GUARDIAN_MEERA)
		self.assertEqual(
			sorted(frappe.get_list("Student", pluck="first_name")),
			["Arya", "Bodhi"],
		)
		frappe.set_user(TEACHER)
		self.assertNotIn("Chetan", frappe.get_list("Student", pluck="first_name"))

	def test_parent_cannot_view_other_child(self):
		frappe.set_user(GUARDIAN_RAVI)
		self.assertRaises(frappe.PermissionError, api.get_student_dashboard, student("Arya"))
		self.assertEqual(api.get_student_dashboard(student("Chetan"))["student_name"], "Chetan")

	def test_online_attendance_requires_staff_or_class_teacher(self):
		for user in (GUARDIAN_RAVI, STUDENT_ARYA):
			frappe.set_user(user)
			self.assertRaises(frappe.PermissionError, ol.mark_online_attendance, "Class 1A", nowdate())
		frappe.set_user("Administrator")
		self.assertRaises(
			frappe.ValidationError, ol.mark_online_attendance, "Class 1A", add_days(nowdate(), 3)
		)

	def test_school_tile_and_parent_landing(self):
		for user, expected in ((TEACHER, True), (GUARDIAN_MEERA, True), (STUDENT_ARYA, False)):
			frappe.set_user(user)
			self.assertEqual(api.has_app_permission(), expected, user)
		frappe.set_user("Administrator")
		# demo_data saves the guardian with a login, so the Guardian hook has run
		self.assertEqual(frappe.db.get_value("User", GUARDIAN_MEERA, "default_app"), "school_suite")

	def test_send_is_not_callable_over_http(self):
		self.assertNotIn(notify.send, frappe.whitelisted)

	# ----------------------------------------------------------- notifications
	def test_absence_alert_today_only_once(self):
		chetan = student("Chetan")
		guardian = frappe.db.get_value("Student Guardian", {"parent": chetan}, "guardian")
		frappe.db.set_value("Guardian", guardian, "mobile_number", "+919800000000")
		day = add_days(nowdate(), -60)
		past = frappe.get_doc(
			{
				"doctype": "Student Attendance",
				"student": chetan,
				"student_group": "Class 1B",
				"date": day,
				"status": "Absent",
			}
		)
		with patch("frappe.enqueue") as enqueue:
			past.insert(ignore_permissions=True)
			past.submit()
			enqueue.assert_not_called()  # back-filled register: no SMS
		sent = notify.send_absence_alert(past.name)
		self.assertEqual(len(sent), 1)
		self.assertEqual(sent[0]["to"], "+919800000000")
		self.assertIn("Chetan", sent[0]["message"])

	# --------------------------------------------------------------------- fees
	def make_invoice(self, first_name, rate=5000, submit=False):
		stu = frappe.get_doc("Student", student(first_name))
		if not stu.customer:
			stu.set_missing_customer_details()
			stu.reload()
		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": "Demo School",
				"customer": stu.customer,
				"student": stu.name,
				"posting_date": nowdate(),
				"due_date": add_days(nowdate(), 15),
				"items": [{"item_code": self.item, "qty": 1, "rate": rate, "income_account": self.income}],
			}
		)
		si.insert(ignore_permissions=True)
		if submit:
			si.submit()
		return si

	def test_fee_summary_counts_native_sales_invoices(self):
		before = api.get_fee_summary(student("Chetan"))["billed"]
		self.make_invoice("Chetan", 3000, submit=True)
		self.assertEqual(api.get_fee_summary(student("Chetan"))["billed"], before + 3000)

	def test_sibling_discount_applied_to_sales_invoice(self):
		self.set_setting("auto_apply_sibling_discount", 1)
		eldest = self.make_invoice("Arya")  # rank 1
		second = self.make_invoice("Bodhi")  # rank 2
		self.assertEqual(flt(eldest.grand_total), 5000)
		self.assertEqual(flt(second.items[0].discount_percentage), 10)
		self.assertEqual(flt(second.grand_total), 4500)

	def test_discounted_rate_not_saved_as_item_price(self):
		# Found in the browser walkthrough: with Stock Settings' auto-insert on, the
		# first (discounted) fee invoice saved its discounted rate as the Item Price.
		frappe.db.set_single_value("Stock Settings", "auto_insert_price_list_rate_if_missing", 1)
		frappe.db.set_single_value("Stock Settings", "update_price_list_based_on", "Rate")
		frappe.clear_document_cache("Stock Settings", "Stock Settings")
		frappe.db.delete("Item Price", {"item_code": self.item})
		self.set_setting("auto_apply_sibling_discount", 1)
		second = self.make_invoice("Bodhi")  # rank 2, created first
		self.assertEqual(flt(second.grand_total), 4500)
		self.assertFalse(frappe.db.exists("Item Price", {"item_code": self.item, "price_list_rate": 4500}))
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

	def test_no_sibling_discount_when_disabled(self):
		self.set_setting("auto_apply_sibling_discount", 0)
		self.assertEqual(flt(self.make_invoice("Bodhi").grand_total), 5000)

	def test_legacy_fees_honour_component_discount(self):
		# Education only checks the enrollment belongs to the student; a draft will do.
		enrollment = frappe.get_doc(
			{
				"doctype": "Program Enrollment",
				"student": student("Arya"),
				"program": "Grade 5",
				"academic_year": demo_data.academic_year_name(),
				"enrollment_date": nowdate(),
			}
		).insert(ignore_permissions=True)
		fee = frappe.get_doc(
			{
				"doctype": "Fees",
				"student": student("Arya"),
				"program_enrollment": enrollment.name,
				"fee_structure": self.fee_structure,
				"academic_year": demo_data.academic_year_name(),
				"program": enrollment.program,
				"company": "Demo School",
				"posting_date": nowdate(),
				"due_date": add_days(nowdate(), 30),
				"receivable_account": "Debtors - DS",
				"income_account": self.income,
				"components": [
					{"fees_category": "Tuition", "item": self.item, "amount": 5000, "discount": 20}
				],
			}
		)
		fee.insert(ignore_permissions=True)
		self.assertEqual((flt(fee.grand_total), flt(fee.outstanding_amount)), (4000, 4000))

	def test_concession_bounds(self):
		fee = frappe._dict(doctype="Fees", components=[frappe._dict(amount=1000)])
		self.assertRaises(frappe.ValidationError, fees_policy.apply_concession, fee, 150)
		self.assertEqual(fees_policy.apply_concession(fee, 25)["new_total"], 750)

	def test_rte_invoice_warns(self):
		frappe.db.set_value("Student", student("Chetan"), "rte_admission", 1)
		frappe.local.message_log = []
		self.make_invoice("Chetan")
		self.assertTrue(any("RTE" in str(m) for m in frappe.local.message_log))

	def test_fee_category_item_gets_default_sac(self):
		if not frappe.get_meta("Item").has_field("gst_hsn_code"):
			self.skipTest("India Compliance not installed")
		frappe.get_doc(
			{
				"doctype": "Fee Category",
				"category_name": "Test Transport",
				"item_defaults": [{"company": "Demo School", "income_account": self.income}],
			}
		).insert(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Item", "Test Transport", "gst_hsn_code"), "999220")

	def test_late_fee_capped(self):
		si = self.make_invoice("Chetan", 2000, submit=True)
		result = fees_policy.late_fee_amount(si.name, as_of=add_days(si.due_date, 100))
		self.assertEqual(result, {"days_overdue": 100, "late_fee": 1000})

	# ----------------------------------------------------------------- reports
	def test_principal_dashboard(self):
		data = api.get_principal_dashboard()
		self.assertIn("low_attendance", data)
		self.assertEqual(flt(data["low_attendance_threshold"]), 75)
		frappe.set_user(GUARDIAN_MEERA)
		self.assertRaises(frappe.PermissionError, api.get_principal_dashboard)

	def test_udise_export_and_transfer_certificate(self):
		udise = reports.udise_export()
		self.assertTrue(udise["_placeholder"])
		self.assertIn("by_class_and_gender", udise["enrolment"])
		tc = reports.get_transfer_certificate(student("Arya"))
		self.assertEqual(tc["mother_name"], "Meera Nair")
		self.assertTrue(tc["warnings"])  # demo data has no leaving date / TC number
		self.assertEqual(reports._date_in_words("2015-03-21"), "Twenty First March Two Thousand Fifteen")
		frappe.set_user(GUARDIAN_MEERA)
		self.assertRaises(frappe.PermissionError, reports.get_transfer_certificate, student("Arya"))

	def test_portal_pages_render(self):
		from frappe.utils import set_request
		from frappe.website.serve import get_response_content

		pages = [
			(GUARDIAN_MEERA, "parent", "Arya"),
			(GUARDIAN_MEERA, f"report-card?student={student('Arya')}", "Report Card"),
			("Administrator", "principal", "Principal Dashboard"),
			("Administrator", f"transfer-certificate?student={student('Arya')}", "Transfer Certificate"),
		]
		for user, path, expected in pages:
			frappe.set_user(user)
			route, _sep, query = path.partition("?")
			set_request(path=f"/{route}", query_string=query)
			frappe.form_dict.update(frappe.local.request.args.to_dict())
			html = get_response_content(route)
			self.assertIn(expected, html, path)
