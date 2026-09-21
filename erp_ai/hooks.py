app_name = "erp_ai"
app_title = "ERP AI"
app_publisher = "SPI"
app_description = "Local AI assistant for ERPNext"
app_email = "developer@spi.local"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "erp_ai",
# 		"logo": "/assets/erp_ai/logo.png",
# 		"title": "ERP AI",
# 		"route": "/erp_ai",
# 		"has_permission": "erp_ai.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/erp_ai/css/erp_ai.css"
# app_include_js = "/assets/erp_ai/js/erp_ai.js"

# include js, css files in header of web template
# web_include_css = "/assets/erp_ai/css/erp_ai.css"
# web_include_js = "/assets/erp_ai/js/erp_ai.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "erp_ai/public/scss/website"

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
# app_include_icons = "erp_ai/public/icons.svg"

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

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "erp_ai.utils.jinja_methods",
# 	"filters": "erp_ai.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "erp_ai.install.before_install"
after_install = "erp_ai.install.after_install"
after_migrate = "erp_ai.install.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "erp_ai.uninstall.before_uninstall"
# after_uninstall = "erp_ai.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "erp_ai.utils.before_app_install"
# after_app_install = "erp_ai.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "erp_ai.utils.before_app_uninstall"
# after_app_uninstall = "erp_ai.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "erp_ai.notifications.get_notification_config"

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

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
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
# Runtime uses a bounded, reactivate-only worker:
#   - expire_stale_actions unblocks retries: a ``pending`` draft that was never
#     confirmed is expired, and a ``processing`` claim whose worker died is
#     closed as failed (otherwise its idempotency key blocks every retry).
#   - cleanup_expired_actions trims already-audited terminal rows.

scheduler_events = {
	"hourly": ["erp_ai.tasks.expire_stale_actions"],
	"daily": [
		"erp_ai.tasks.cleanup_expired_actions",
		"erp_ai.tasks.refresh_behavior_patterns",
		"erp_ai.tasks.draft_help_for_repeated_failures",
	],
}

# Testing
# -------

# before_tests = "erp_ai.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "erp_ai.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "erp_ai.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["erp_ai.utils.before_request"]
# after_request = ["erp_ai.utils.after_request"]

# Job Events
# ----------
# before_job = ["erp_ai.utils.before_job"]
# after_job = ["erp_ai.utils.after_job"]

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
# 	"erp_ai.auth.validate"
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

app_include_js = "/assets/erp_ai/js/ai_widget.js?v=4"
