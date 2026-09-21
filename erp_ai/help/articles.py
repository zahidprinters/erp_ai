# ---------------------------------------------------------------------------
# AI Help System — comprehensive help articles for the ERP AI app.
# ---------------------------------------------------------------------------

import frappe
from frappe import _

from erp_ai.knowledge.erpnext_kb import get_kb_summary

CATEGORIES = [
	{"id": "getting-started", "label": "Getting Started", "icon": "rocket"},
	{"id": "data-entry", "label": "Data Entry", "icon": "file"},
	{"id": "accounting", "label": "Accounting", "icon": "dollar"},
	{"id": "selling", "label": "Selling", "icon": "cart"},
	{"id": "buying", "label": "Buying", "icon": "cart"},
	{"id": "stock", "label": "Stock", "icon": "box"},
	{"id": "manufacturing", "label": "Manufacturing", "icon": "gear"},
	{"id": "hr", "label": "HR & Payroll", "icon": "user"},
	{"id": "quality", "label": "Quality", "icon": "shield"},
	{"id": "assets", "label": "Assets", "icon": "tool"},
	{"id": "reports", "label": "Reports", "icon": "graph"},
	{"id": "setup", "label": "Setup", "icon": "gear"},
	{"id": "troubleshooting", "label": "Troubleshooting", "icon": "troubleshooting"},
]

QUICK_ACTIONS = [
	{
		"id": "chat",
		"label": "AI Chat",
		"icon": "comment",
		"description": "Ask the AI assistant anything about your ERP data",
		"color": "#4f46e5",
		"action": "open_chat",
	},
	{
		"id": "sales-invoice",
		"label": "Sales Invoice",
		"icon": "file-text",
		"description": "Create a new sales invoice via chat",
		"color": "#059669",
		"action": "create_doc",
		"doctype": "Sales Invoice",
	},
	{
		"id": "purchase-receipt",
		"label": "Purchase Receipt",
		"icon": "truck",
		"description": "Record an incoming shipment",
		"color": "#d97706",
		"action": "create_doc",
		"doctype": "Purchase Receipt",
	},
	{
		"id": "stock-entry",
		"label": "Stock Issue",
		"icon": "arrow-up-right",
		"description": "Issue stock to a department",
		"color": "#dc2626",
		"action": "create_doc",
		"doctype": "Stock Entry",
	},
	{
		"id": "item",
		"label": "New Item",
		"icon": "plus-circle",
		"description": "Create a new item master",
		"color": "#7c3aed",
		"action": "create_doc",
		"doctype": "Item",
	},
	{
		"id": "reports",
		"label": "Reports",
		"icon": "bar-chart-2",
		"description": "View AI-powered reports",
		"color": "#0891b2",
		"action": "open_reports",
	},
]


@frappe.whitelist()
def get_help_categories():
	"""Return all help categories."""
	return CATEGORIES


@frappe.whitelist()
def get_quick_actions():
	"""Return quick-action cards for the workspace."""
	return QUICK_ACTIONS


@frappe.whitelist()
def get_articles(category=None, search=None, limit=50):
	"""Return help articles, optionally filtered by category or search term."""
	filters = {"is_active": 1}
	if category:
		filters["category"] = category

	or_filters = []
	if search:
		or_filters = [
			["title", "like", f"%{search}%"],
			["description", "like", f"%{search}%"],
			["keywords", "like", f"%{search}%"],
			["content", "like", f"%{search}%"],
		]

	# ``frappe.get_list``, not ``get_all``: ``get_all`` forces ``ignore_permissions``
	# (see erp_ai/erp_tools.py::_fetch, which must go through ``get_list`` for the
	# same reason), so the help search handed out rows to users who cannot read the
	# DocType and skipped the User Permission row filters.
	articles = frappe.get_list(
		"AI Help Article",
		filters=filters,
		fields=["name", "title", "category", "icon", "description", "keywords", "modified"],
		or_filters=or_filters or None,
		limit_page_length=limit,
		order_by="modified desc",
	)

	return articles


@frappe.whitelist()
def get_article(name):
	"""Return a single help article by name."""
	article = frappe.get_doc("AI Help Article", name)
	# ``frappe.get_doc`` applies no permission check of its own (Point 6 pattern),
	# so without this any authenticated user could read any article — including
	# inactive ones — by guessing or enumerating its name.
	if not frappe.has_permission("AI Help Article", "read", doc=article):
		raise frappe.PermissionError(_("Not permitted to read help article {0}").format(name))
	return {
		"name": article.name,
		"title": article.title,
		"category": article.category,
		"icon": article.icon,
		"content": article.content,
		"description": article.description,
		"keywords": article.keywords,
		"example_queries": article.get_parsed_examples(),
		"modified": article.modified,
	}


@frappe.whitelist()
def search_articles(query):
	"""Search help articles by query string."""
	if not query or len(query) < 2:
		return []

	# Bound the LIKE pattern: an unbounded term is a full-table scan, and a bare
	# ``%`` would match every article.
	query = str(query)[:100]

	# ``get_list`` (permission-filtered) for the same reason as ``get_articles``.
	articles = frappe.get_list(
		"AI Help Article",
		filters={"is_active": 1},
		fields=["name", "title", "category", "icon", "description"],
		or_filters=[
			["title", "like", f"%{query}%"],
			["description", "like", f"%{query}%"],
			["keywords", "like", f"%{query}%"],
			["content", "like", f"%{query}%"],
		],
		limit_page_length=20,
	)
	return articles


@frappe.whitelist()
def get_knowledge_base():
	"""Return the ERPNext knowledge base summary for the AI assistant."""
	return get_kb_summary()
