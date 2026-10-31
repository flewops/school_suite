app_name = "school_suite"
app_title = "School Suite"
app_publisher = "School Suite"
app_description = "Integration layer unifying ERPNext, Education, Frappe HR, Learning (LMS) and India Compliance for Indian schools"
app_email = "dev@example.com"
app_license = "mit"

# Apps
# ------------------

required_apps = ["frappe/erpnext", "frappe/education", "frappe/lms"]

# Each item in the list will be shown as an app in the apps page
# The "School" tile: staff and parents start here (/school sends each role to its
# page). Education's own tile shows only to Education Manager, so without this a
# teacher or parent has no visible way in.
add_to_apps_screen = [
	{
		"name": "school_suite",
		"logo": "/assets/school_suite/school.svg",
		"title": "School",
		"route": "/school",
		"has_permission": "school_suite.api.has_app_permission",
	}
]

# The dock, the rail down the left of the desk, is a document rather than a hook. Author it in
# Manage Dock on a developer-mode site and press Export to App, and it is written to
# `school_suite/dock/school_suite/school_suite.json` for git to carry. An app that ships none has no
# rail: its sidebar gets a switcher in the header instead.
#
# A companion app, one that extends a host app rather than standing on its own, says so with
# `mount_on` on that same record, and its entries are appended to the host's rail. Mounting keeps
# the companion off the apps screen, so it takes precedence over any add_to_apps_screen above.

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/school_suite/css/school_suite.css"
# app_include_js = "/assets/school_suite/js/school_suite.js"

# include js, css files in header of web template
# web_include_css = "/assets/school_suite/css/school_suite.css"
# web_include_js = "/assets/school_suite/js/school_suite.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "school_suite/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_kanban_js = {"doctype" : "public/js/doctype_kanban.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "school_suite/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# No role_home_page: it sent anyone holding Parent/Guardian (Administrator, or a
# teacher whose own child studies here) to /parent after login. Parents land on
# /parent through the School app instead (api.set_guardian_default_app, www/school.py).

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "school_suite.utils.jinja_methods",
# 	"filters": "school_suite.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "school_suite.install.before_install"
after_install = "school_suite.setup.install.after_install"
after_migrate = "school_suite.setup.install.run"

# Uninstallation
# ------------

# before_uninstall = "school_suite.uninstall.before_uninstall"
# after_uninstall = "school_suite.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "school_suite.utils.before_app_install"
# after_app_install = "school_suite.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "school_suite.utils.before_app_uninstall"
# after_app_uninstall = "school_suite.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "school_suite.build.after_build"

# To hook into the build process of other apps
# The list of apps being built is passed as an argument

# after_app_build = "school_suite.build.after_app_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "school_suite.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["school_suite.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Student": "school_suite.permissions.student_query",
	"Student Group": "school_suite.permissions.student_group_query",
	"Student Attendance": "school_suite.permissions.student_attendance_query",
	"Assessment Result": "school_suite.permissions.assessment_result_query",
	"Program Enrollment": "school_suite.permissions.program_enrollment_query",
	"Course Enrollment": "school_suite.permissions.course_enrollment_query",
	"Fees": "school_suite.permissions.fees_query",
	"Course Schedule": "school_suite.permissions.course_schedule_query",
}

has_permission = {
	"Student": "school_suite.permissions.student_has_permission",
	"Student Attendance": "school_suite.permissions.student_record_has_permission",
	"Assessment Result": "school_suite.permissions.student_record_has_permission",
	"Program Enrollment": "school_suite.permissions.student_record_has_permission",
	"Fees": "school_suite.permissions.student_record_has_permission",
	"Course Enrollment": "school_suite.permissions.student_record_has_permission",
	"Student Group": "school_suite.permissions.student_group_has_permission",
	"Course Schedule": "school_suite.permissions.course_schedule_has_permission",
}

# No fixtures: roles, custom fields, property setters and the workflow are created
# in code by school_suite.setup.install.run (after_install / after_migrate).

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Student Group": {
		"on_update": "school_suite.online_learning.on_student_group_update",
	},
	"Guardian": {
		"on_update": "school_suite.api.set_guardian_default_app",
	},
	"Student Attendance": {
		"on_submit": "school_suite.notify.on_attendance_submit",
	},
	# Education v16 bills through Sales Invoice (Fee Schedule); Fees is the legacy path.
	"Sales Invoice": {
		"before_validate": "school_suite.fees_policy.before_fee_validate",
		"validate": "school_suite.fees_policy.warn_if_rte",
	},
	"Fees": {
		"before_validate": "school_suite.fees_policy.before_fee_validate",
		"validate": [
			"school_suite.fees_policy.recompute_legacy_fee_totals",
			"school_suite.fees_policy.warn_if_rte",
		],
	},
	"Item": {
		"before_validate": "school_suite.fees_policy.default_fee_item_sac",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"school_suite.tasks.all"
# 	],
# 	"daily": [
# 		"school_suite.tasks.daily"
# 	],
# 	"hourly": [
# 		"school_suite.tasks.hourly"
# 	],
# 	"weekly": [
# 		"school_suite.tasks.weekly"
# 	],
# 	"monthly": [
# 		"school_suite.tasks.monthly"
# 	],
# }

# Testing
# -------

# Frappe runs only the tested app's own hook: complete the setup wizard on a fresh
# test site through Education's bootstrap (a required app).
before_tests = "education.education.test_utils.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "school_suite.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "school_suite.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "school_suite.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["school_suite.utils.before_request"]
# after_request = ["school_suite.utils.after_request"]

# Job Events
# ----------
# before_job = ["school_suite.utils.before_job"]
# after_job = ["school_suite.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"school_suite.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
