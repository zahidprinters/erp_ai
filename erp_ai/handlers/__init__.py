# ---------------------------------------------------------------------------
# Document handlers — single-document operations (create, view, print, query).
#
# Each handler takes (prompt, mcp) and returns a response string.
# Handlers are stateless — they use the MCP tool layer for all DB access.
# ---------------------------------------------------------------------------
import re
from typing import Any, Dict


def handle_create_item(prompt: str, mcp) -> str:
	"""Extract item details from natural language and create."""
	import frappe

	from erp_ai.rbac import check_permission

	err = check_permission(frappe.session.user, "Item", "create")
	if err:
		return "🚫 " + err
	from erp_ai.draft_workflow import extract_item_fields

	data = extract_item_fields(prompt) or {}
	item_name = data.get("item_name")
	if not item_name:
		return "To create an item I need at least a name. Example: 'Add item Steel Rod, group Raw Material, price 100, opening stock 500'"

	try:
		from erp_ai.duplication import check_duplicate
	except ImportError:
		check_duplicate = None
	dup = check_duplicate(mcp, "Item", data) if check_duplicate else None
	if dup:
		return "Item '%s' already exists (%s). Use a different name." % (item_name, dup["name"])

	code = item_name.replace(" ", "-").upper()
	from erp_ai.schema import get_defaults

	defaults = get_defaults("Item")
	data["doctype"] = "Item"
	data["item_code"] = data.get("item_code", code)
	for k, v in defaults.items():
		data.setdefault(k, v)

	result = mcp.call_tool("create_document", {"doctype": "Item", "data": data})
	if "error" in result:
		return "Could not create item: " + result["error"]
	return "✅ Item created: %s (%s)\n  Group: %s | Price: %s | UOM: %s" % (
		item_name,
		data["item_code"],
		data.get("item_group", "-"),
		data.get("standard_rate", 0),
		data.get("stock_uom", "-"),
	)


def handle_create_customer(prompt: str, mcp) -> str:
	"""Extract customer details and create."""
	import frappe

	from erp_ai.rbac import check_permission

	err = check_permission(frappe.session.user, "Customer", "create")
	if err:
		return "🚫 " + err
	name_match = re.search(r"(?:named|name|called|ka naam)\s+[\"']?([^\"',.]+)", prompt, re.I)
	name = name_match.group(1).strip() if name_match else None
	if not name:
		return "Please provide customer name. Example: 'Create customer named ABC Traders'"

	try:
		from erp_ai.duplication import check_duplicate
	except ImportError:
		check_duplicate = None
	dup = check_duplicate(mcp, "Customer", {"customer_name": name}) if check_duplicate else None
	if dup:
		return "Customer '%s' already exists (%s). Use a different name." % (name, dup["name"])

	from erp_ai.schema import get_defaults

	data = {"doctype": "Customer", "customer_name": name}
	data.update(get_defaults("Customer"))
	result = mcp.call_tool("create_document", {"doctype": "Customer", "data": data})
	if "error" in result:
		return "Could not create customer: " + result["error"]
	return "✅ Customer created: %s" % name


def handle_create_supplier(prompt: str, mcp) -> str:
	"""Extract supplier details and create."""
	import frappe

	from erp_ai.rbac import check_permission

	err = check_permission(frappe.session.user, "Supplier", "create")
	if err:
		return "🚫 " + err
	name_match = re.search(r"(?:named|name|called|ka naam)\s+[\"']?([^\"',.]+)", prompt, re.I)
	name = name_match.group(1).strip() if name_match else None
	if not name:
		return "Please provide supplier name. Example: 'Create supplier named XYZ Corp'"

	try:
		from erp_ai.duplication import check_duplicate
	except ImportError:
		check_duplicate = None
	dup = check_duplicate(mcp, "Supplier", {"supplier_name": name}) if check_duplicate else None
	if dup:
		return "Supplier '%s' already exists (%s). Use a different name." % (name, dup["name"])

	from erp_ai.schema import get_defaults

	data = {"doctype": "Supplier", "supplier_name": name}
	data.update(get_defaults("Supplier"))
	result = mcp.call_tool("create_document", {"doctype": "Supplier", "data": data})
	if "error" in result:
		return "Could not create supplier: " + result["error"]
	return "✅ Supplier created: %s" % name


def handle_print(prompt: str, mcp) -> str:
	"""Handle print requests."""
	inv_match = re.search(r"(?:invoice|bill)\s+(\S+)", prompt, re.I)
	if inv_match:
		name = inv_match.group(1)
		result = mcp.call_tool("print_document", {"doctype": "Sales Invoice", "name": name})
		if "error" in result:
			return "Error: " + result["error"]
		return result.get("message", "Print ready")
	return "To print, specify: 'print invoice INV-001'"


def handle_count_query(prompt: str, mcp) -> str:
	"""Handle count/how many queries."""
	pl = prompt.lower()
	count_map = {
		"item": ("Item", {"disabled": 0}),
		"customer": ("Customer", {}),
		"supplier": ("Supplier", {}),
		"sales order": ("Sales Order", {"docstatus": 1}),
		"purchase order": ("Purchase Order", {"docstatus": 1}),
	}
	for keyword, (dt, filters) in count_map.items():
		if keyword in pl:
			result = mcp.call_tool(
				"query_doctype", {"doctype": dt, "filters": filters, "fields": ["name"], "limit": 10000}
			)
			count = result.get("count", 0)
			return "We have %s %s in the system." % (count, keyword + ("s" if count != 1 else ""))
	return None  # Not a count query — let caller handle it
