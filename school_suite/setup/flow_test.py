import json

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, nowdate

from school_suite import api
from school_suite import online_learning as ol
from school_suite.setup.demo_data import academic_year_name, assert_dev_site

flow, ctx = {}, {}


def step(name, fn):
	try:
		flow[name] = {"ok": True, "detail": fn()}
	except Exception as e:
		flow[name] = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:280]}"}


# -- prerequisites: fee category, room, income acct, fee structure, razorpay placeholder
def prereq():
	if not frappe.db.exists("Room", {"room_name": "Room 101"}):
		frappe.get_doc(
			{"doctype": "Room", "room_name": "Room 101", "room_number": "101", "seating_capacity": 30}
		).insert(ignore_permissions=True)
	ctx["room"] = frappe.db.get_value("Room", {"room_name": "Room 101"}, "name")
	inc = frappe.get_all(
		"Account", {"company": "Demo School", "root_type": "Income", "is_group": 0}, pluck="name"
	)
	ctx["income"] = inc[0] if inc else None
	ctx["receivable"] = "Debtors - DS"

	# India Compliance makes HSN/SAC mandatory on sales items; pick a valid SAC
	# (9992 = education services) from the loaded GST HSN Code list.
	_hsn = frappe.db.sql(
		"""select hsn_code from `tabGST HSN Code`
           where length(hsn_code) in (6,8) and hsn_code like '9992%'
           order by length(hsn_code) limit 1"""
	)
	if not _hsn:
		_hsn = frappe.db.sql("select hsn_code from `tabGST HSN Code` where length(hsn_code) in (6,8) limit 1")
	ctx["hsn"] = _hsn[0][0] if _hsn else None

	# Education v16 maps every Fee Category to an ERPNext Item (created on insert).
	if not frappe.db.exists("Item Group", "Fee Component"):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": "Fee Component",
				"parent_item_group": "All Item Groups",
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("Fee Category", "Tuition"):
		fc = frappe.get_doc({"doctype": "Fee Category", "category_name": "Tuition"})
		fc.append("item_defaults", {"company": "Demo School", "income_account": ctx["income"]})
		fc.insert(ignore_permissions=True)
	# self-heal: Education expects an Item named after the category; create if missing.
	if not frappe.db.exists("Item", "Tuition"):
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "Tuition",
				"item_name": "Tuition",
				"item_group": "Fee Component",
				"is_sales_item": 1,
				"is_service_item": 1,
				"is_stock_item": 0,
				"gst_hsn_code": ctx["hsn"],
			}
		)
		item.append("item_defaults", {"company": "Demo School", "income_account": ctx["income"]})
		item.insert(ignore_permissions=True)
		frappe.db.set_value("Fee Category", "Tuition", "item", "Tuition")
	ctx["item"] = "Tuition"

	if not frappe.db.get_value("Fee Structure", {"program": "Grade 5"}, "name"):
		fs = frappe.get_doc(
			{
				"doctype": "Fee Structure",
				"program": "Grade 5",
				"academic_year": academic_year_name(),
				"company": "Demo School",
				"receivable_account": ctx["receivable"],
			}
		)
		fs.append("components", {"fees_category": "Tuition", "item": ctx["item"], "amount": 5000})
		fs.insert(ignore_permissions=True)
		fs.submit()
	ctx["fee_structure"] = frappe.db.get_value("Fee Structure", {"program": "Grade 5"}, "name")
	# Razorpay TEST placeholder — fake keys, must be replaced with real rzp_test_ keys.
	# Never overwrite keys a school has already entered.
	try:
		rs = frappe.get_single("Razorpay Settings")
		if rs.api_key:
			ctx["razorpay"] = "keys already set; left untouched"
			return ctx
		rs.api_key = "rzp_test_PLACEHOLDER"
		rs.api_secret = "PLACEHOLDER_SECRET"
		rs.flags.ignore_mandatory = True
		rs.save(ignore_permissions=True)
		ctx["razorpay"] = "placeholder set (disabled/fake keys)"
	except Exception as e:
		ctx["razorpay"] = f"skipped: {str(e)[:120]}"
	return ctx


def admission_setup():
	g = frappe.db.get_value("Guardian", {"user": "guardian_meera@demo.school"}, "name")
	email = "diya@demo.school"
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Diya",
				"send_welcome_email": 0,
				"new_password": "Test@12345",
			}
		).insert(ignore_permissions=True)
	u = frappe.get_doc("User", email)
	if "Student" not in {r.role for r in u.roles}:
		u.append("roles", {"role": "Student"})
		u.save(ignore_permissions=True)
	if not frappe.db.get_value("Student", {"user": email}, "name"):
		s = frappe.get_doc(
			{
				"doctype": "Student",
				"first_name": "Diya",
				"student_email_id": email,
				"user": email,
				"joining_date": nowdate(),
			}
		)
		s.append("guardians", {"guardian": g, "relation": "Mother"})
		s.insert(ignore_permissions=True)
	ctx["diya"] = frappe.db.get_value("Student", {"user": email}, "name")
	return ctx["diya"]


def admission():
	name = frappe.db.get_value("Program Enrollment", {"student": ctx["diya"]}, "name")
	if not name:
		pe = frappe.get_doc(
			{
				"doctype": "Program Enrollment",
				"student": ctx["diya"],
				"program": "Grade 5",
				"academic_year": academic_year_name(),
				"enrollment_date": nowdate(),
			}
		)
		pe.insert(ignore_permissions=True)
		name = pe.name
	pe = frappe.get_doc("Program Enrollment", name)
	if (pe.get("workflow_state") or "Draft") == "Draft":
		pe = apply_workflow(pe, "Apply for Approval")
	if pe.get("workflow_state") == "Pending Principal Approval":
		pe = apply_workflow(pe, "Approve")
	ctx["program_enrollment"] = pe.name
	return {"workflow_state": pe.get("workflow_state"), "docstatus": pe.docstatus}


def enrol_in_class():
	g = frappe.get_doc("Student Group", "Class 1A")
	if not any(r.student == ctx["diya"] for r in g.students):
		g.append("students", {"student": ctx["diya"], "active": 1})
		g.save(ignore_permissions=True)
	ol.sync_student_group("Class 1A")
	return sorted([r.student for r in frappe.get_doc("Student Group", "Class 1A").students])


def fees():
	existing = frappe.db.get_value("Fees", {"student": ctx["diya"], "docstatus": 1}, "name")
	if existing:
		fe = frappe.get_doc("Fees", existing)
		ctx["fee"] = fe.name
		return {
			"fee": fe.name,
			"grand_total": fe.grand_total,
			"outstanding": fe.outstanding_amount,
			"note": "reused existing",
		}
	f = frappe.get_doc(
		{
			"doctype": "Fees",
			"student": ctx["diya"],
			"company": "Demo School",
			"posting_date": nowdate(),
			"due_date": add_days(nowdate(), 30),
			"program_enrollment": ctx["program_enrollment"],
			"program": "Grade 5",
			"academic_year": academic_year_name(),
			"fee_structure": ctx["fee_structure"],
			"receivable_account": ctx["receivable"],
			"income_account": ctx["income"],
		}
	)
	f.append("components", {"fees_category": "Tuition", "item": ctx["item"], "amount": 5000})
	f.insert(ignore_permissions=True)
	f.submit()
	ctx["fee"] = f.name
	return {"fee": f.name, "grand_total": f.grand_total, "outstanding": f.outstanding_amount}


def payment_request():
	# Education Fees books a receivable against the student's Customer. Collecting
	# online needs: (1) real Razorpay TEST keys in Razorpay Settings, (2) a Payment
	# Gateway Account linking the "Razorpay" gateway to the company + a bank account.
	# We verify the gateway is wired (with placeholder keys) and report the balance;
	# actually charging a card requires the school's own rzp_test_ keys.
	fee = frappe.get_doc("Fees", ctx["fee"])
	gateway_exists = frappe.db.exists("Payment Gateway", "Razorpay")
	rzp_configured = bool(frappe.db.get_single_value("Razorpay Settings", "api_key"))
	return {
		"fee": fee.name,
		"outstanding": fee.outstanding_amount,
		"razorpay_gateway_record": bool(gateway_exists),
		"razorpay_keys_set": rzp_configured,
		"note": "Placeholder keys only. To take a real test payment, enter the school's "
		"rzp_test_ key/secret in Razorpay Settings and create a Payment Gateway "
		"Account (Razorpay -> Demo School -> a bank account).",
	}


def timetable():
	instr = frappe.db.get_value("Student Group Instructor", {"parent": "Class 1A"}, "instructor")
	existing = frappe.db.get_value(
		"Course Schedule",
		{"student_group": "Class 1A", "schedule_date": nowdate(), "from_time": "09:00:00"},
		"name",
	)
	if existing:
		return {"course_schedule": existing, "instructor": instr, "note": "reused existing"}
	cs = frappe.get_doc(
		{
			"doctype": "Course Schedule",
			"student_group": "Class 1A",
			"instructor": instr,
			"course": "Mathematics",
			"room": ctx["room"],
			"schedule_date": nowdate(),
			"from_time": "09:00:00",
			"to_time": "10:00:00",
		}
	)
	cs.insert(ignore_permissions=True)
	return {"course_schedule": cs.name, "instructor": instr}


def quiz():
	course = frappe.db.get_value("LMS Course", {"title": "Fractions Basics"}, "name")
	if not frappe.db.exists("LMS Quiz", {"title": "Fractions Quiz 1"}):
		frappe.get_doc(
			{
				"doctype": "LMS Quiz",
				"title": "Fractions Quiz 1",
				"total_marks": 10,
				"passing_percentage": 50,
				"course": course,
			}
		).insert(ignore_permissions=True)
	quiz = frappe.db.get_value("LMS Quiz", {"title": "Fractions Quiz 1"}, "name")
	diya_user = frappe.db.get_value("Student", ctx["diya"], "user")
	sub = frappe.db.get_value("LMS Quiz Submission", {"quiz": quiz, "member": diya_user}, "name")
	if not sub:
		doc = frappe.get_doc(
			{
				"doctype": "LMS Quiz Submission",
				"quiz": quiz,
				"course": course,
				"member": diya_user,
				"score": 8,
				"score_out_of": 10,
				"percentage": 80,
				"passing_percentage": 50,
			}
		)
		doc.insert(ignore_permissions=True)
		sub = doc.name
	return {"quiz": quiz, "submission": sub, "percentage": 80}


def online_class_and_attendance():
	# Live-class creation needs real Zoom creds (placeholder settings are disabled);
	# here we exercise the online-mode attendance engine which falls back to LMS activity.
	# Only online-mode classes/students are processed, so flag the class (db write:
	# skips the on_update LMS re-sync, which step 3 already ran).
	frappe.db.set_value("Student Group", "Class 1A", "enable_online_batch", 1)
	res = ol.mark_online_attendance("Class 1A", nowdate())
	return {
		"attendance": res,
		"note": "LMS Live Class scheduling requires real Zoom S2S creds; placeholder disabled.",
	}


def report():
	d = api.get_student_dashboard(ctx["diya"])
	return {
		"student": d["student_name"],
		"attendance": d["attendance"],
		"fees": d["fees"],
		"timetable_entries": len(d["timetable"]),
		"lms_quizzes": d["lms"]["quizzes"],
		"lms_enrollments": [e["course"] for e in d["lms"]["enrollments"]],
	}


def find_fetch():
	out = {}
	for dt in ["Fees", "Fee Component", "Fee Structure"]:
		out[dt] = [
			f"{f.fieldname} <- {f.fetch_from}" for f in frappe.get_meta(dt).fields if f.get("fetch_from")
		]
	out["fee_structure_has_income_account"] = bool(
		frappe.get_meta("Fee Structure").get_field("income_account")
	)
	return out


def run():
	assert_dev_site()
	frappe.set_user("Administrator")
	flow.clear()
	ctx.clear()
	step("0_prereq", prereq)
	step("1_admission_setup", admission_setup)
	step("2_admission_workflow", admission)
	step("3_enrol_in_class", enrol_in_class)
	step("4_fees", fees)
	step("5_payment_request_razorpay", payment_request)
	step("6_timetable", timetable)
	step("7_quiz", quiz)
	step("8_online_class_attendance", online_class_and_attendance)
	step("9_report", report)
	frappe.db.commit()
	with open(frappe.get_site_path("school_suite_flow.json"), "w") as f:
		f.write(json.dumps(flow, indent=1, default=str))
	return flow
