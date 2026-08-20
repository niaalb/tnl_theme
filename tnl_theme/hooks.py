app_name = "tnl_theme"
app_title = "Tnl Theme"
app_publisher = "TNL"
app_description = "Custom ERPNext theme for TNL"
app_email = "nihal@tnl.sa"
app_license = "mit"

# Apps
# ------------------

# Bid Management's CRM integration (create_bid_from_deal, the "Create Bid"
# Form Script button on CRM Deal, and Bid.crm_deal) all depend on the CRM
# Deal doctype existing, so this app cannot install without it.
required_apps = ["crm"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "tnl_theme",
# 		"logo": "/assets/tnl_theme/logo.png",
# 		"title": "Tnl Theme",
# 		"route": "/tnl_theme",
# 		"has_permission": "tnl_theme.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "tnl_theme.bundle.css"
app_include_js = "tnl_theme.bundle.js"

# include js, css files in header of web template
web_include_css = "tnl_theme.bundle.css"
# web_include_js = "/assets/tnl_theme/js/tnl_theme.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "tnl_theme/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "tnl_theme/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

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
# 	"methods": "tnl_theme.utils.jinja_methods",
# 	"filters": "tnl_theme.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "tnl_theme.install.before_install"
after_install = "tnl_theme.install.after_install"

# Re-applies idempotent settings fixups (e.g. hiding Frappe-branded help
# links, retiring the legacy CRM workspace) on every deploy, not just on
# fresh installs — after_install alone wouldn't touch a site that already
# existed before one of these hooks was added.
after_migrate = [
	"tnl_theme.install.hide_frappe_help_links",
	"tnl_theme.install.retire_legacy_crm_workspace",
]

# Uninstallation
# ------------

# before_uninstall = "tnl_theme.uninstall.before_uninstall"
# after_uninstall = "tnl_theme.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "tnl_theme.utils.before_app_install"
# after_app_install = "tnl_theme.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "tnl_theme.utils.before_app_uninstall"
# after_app_uninstall = "tnl_theme.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "tnl_theme.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "tnl_theme.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"tnl_theme.bid_management.tasks.check_bid_escalations",
	],
}

# scheduler_events = {
# 	"all": [
# 		"tnl_theme.tasks.all"
# 	],
# 	"daily": [
# 		"tnl_theme.tasks.daily"
# 	],
# 	"hourly": [
# 		"tnl_theme.tasks.hourly"
# 	],
# 	"weekly": [
# 		"tnl_theme.tasks.weekly"
# 	],
# 	"monthly": [
# 		"tnl_theme.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "tnl_theme.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "tnl_theme.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "tnl_theme.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "tnl_theme.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["tnl_theme.utils.before_request"]
# after_request = ["tnl_theme.utils.after_request"]

# Job Events
# ----------
# before_job = ["tnl_theme.utils.before_job"]
# after_job = ["tnl_theme.utils.after_job"]

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
# 	"tnl_theme.auth.validate"
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

# Fixtures
# --------
# Bid Management's supporting records (Roles, Workflow) are created via the
# Desk UI / bench console during setup, not hand-written as doctype JSON —
# exporting them here via `bench export-fixtures` captures them into
# version control so a fresh deploy/site gets them automatically too.
fixtures = [
	{
		"dt": "Role",
		"filters": [
			[
				"name",
				"in",
				[
					"Business Development",
					"Sales",
					"Bid Manager",
					"Technical Lead",
					"Financial Lead",
					"Administrative Lead",
					"Leadership",
				],
			]
		],
	},
	{"dt": "Workflow", "filters": [["name", "=", "Bid Workflow"]]},
	# The Workflow's states/transitions Link to these — without exporting
	# them too, importing the Workflow fixture on a fresh site would fail
	# on missing Link targets.
	{
		"dt": "Workflow State",
		"filters": [
			[
				"name",
				"in",
				[
					"Identified",
					"Handed Off",
					"Qualifying",
					"Kickoff",
					"In Progress",
					"Submitted",
					"Closed",
				],
			]
		],
	},
	{
		"dt": "Workflow Action Master",
		"filters": [
			[
				"name",
				"in",
				[
					"Hand Off to Sales",
					"Acknowledge Receipt",
					"Mark as Go",
					"Mark as No-Bid",
					"Confirm Kickoff & Assign Leads",
					"Submit Consolidated Package",
					"Record Outcome",
				],
			]
		],
	},
	{"dt": "Kanban Board", "filters": [["name", "=", "Bid Pipeline"]]},
	{"dt": "CRM Form Script", "filters": [["name", "=", "Create Bid from Deal"]]},
]

