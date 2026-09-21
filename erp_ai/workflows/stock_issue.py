# ---------------------------------------------------------------------------
# Stock issue workflow — issue/transfer stock to a department or person.
# ---------------------------------------------------------------------------
import re
from typing import Any, Dict


def handle_issue_nl(text: str, mcp) -> Dict[str, Any]:
	"""Parse natural language stock issue text."""
	from erp_ai.schema import resolve_warehouse

	qty = None
	m = re.search(r"(?:issue|transfer|jari)\s+([0-9,.]+)", text, re.I)
	if m:
		qty = float(m.group(1).replace(",", ""))

	item = None
	# Stop the item capture at " to " AND at " from ": with a warehouse clause
	# ("issue 5 bolts from Stores to John") the name would otherwise swallow
	# the warehouse tail and blow the length cap.
	m = re.search(
		r"(?:issue|transfer|jari)[^a-z]*([0-9,.]+)\s*(?:pcs|nos|units|kg)?\s*([A-Za-z][A-Za-z0-9 -]{2,40}?)(?:\s+to\s+|\s+from\s+|,|\.|$)",
		text,
		re.I,
	)
	if m and m.group(2):
		item = m.group(2).strip()

	person = None
	m = re.search(r"(?:to|for)\s+(?:mr\.|mr\s|engr\.|engr\s)?([A-Za-z]+(?:\s[A-Za-z]+)?)", text, re.I)
	if m:
		person = m.group(1).strip()

	missing = []
	if not item:
		missing.append("item name")
	if not qty:
		missing.append("quantity")
	if not person:
		missing.append("person/department to issue to")

	# from_warehouse is mandatory on a Material Issue Stock Entry. Resolve it
	# from the text ("from Stores", "se store x"), else fall back to the
	# site's default/single leaf warehouse, else ask the operator up front.
	warehouse = None
	m = re.search(
		r"(?:from|se)\s+([A-Za-z0-9 -]{2,40}?)(?:\s+warehouse|\s+store)?(?:\s+to\s+|,|\.|$)", text, re.I
	)
	if m:
		warehouse = resolve_warehouse(mcp, m.group(1).strip())
	if not warehouse:
		warehouse = resolve_warehouse(mcp)
	if not warehouse:
		missing.append("from warehouse (which store do we issue from?)")

	if missing:
		return {
			"ok": False,
			"missing": missing,
			"message": "To issue stock, please provide:\n" + "\n".join("- " + x for x in missing),
		}

	# Find item in DB (fuzzy)
	found = mcp.call_tool("search_documents", {"query": item, "doctype": "Item", "limit": 3})
	results = found.get("results", [])
	if not results:
		return {"ok": False, "error": "Item '%s' not found in system." % item}
	item_code = results[0]["name"]

	data = {
		"item_code": item_code,
		"qty": qty,
		"issue_type": "Material Issue",
		"issued_to": person,
		"from_warehouse": warehouse,
		"remarks": text[:200],
	}
	return create_stock_issue(data, mcp)


def create_stock_issue(data: Dict[str, Any], mcp) -> Dict[str, Any]:
	"""Create a Stock Entry for material issue."""
	import frappe

	from erp_ai.mcp.server import _validate_required_fields
	from erp_ai.rbac import check_permission

	err = check_permission(frappe.session.user, "Stock Entry", "create")
	if err:
		return {"ok": False, "error": err}
	import frappe

	item_code = data.get("item_code")
	qty = data.get("qty")
	from_wh = data.get("from_warehouse")
	if not (item_code and qty and from_wh):
		return {
			"ok": False,
			"error": "item_code, qty and from_warehouse required (which store do we issue from?)",
		}

	company = frappe.defaults.get_global_default("company")
	if not company:
		return {
			"ok": False,
			"error": "No default company is configured — set one in Company or Global Defaults.",
		}

	se_data = {
		"doctype": "Stock Entry",
		"stock_entry_type": "Material Issue",
		"purpose": "Material Issue",
		"company": company,
		"items": [{"item_code": item_code, "qty": qty, "s_warehouse": from_wh}],
		"remarks": data.get("remarks", ""),
	}
	# Fail early on live-metadata mandatory fields (including Custom Fields and
	# child-row requirements) with a clear, listable message.
	missing_err = _validate_required_fields("Stock Entry", se_data)
	if missing_err:
		return {"ok": False, "error": missing_err}
	se = mcp.call_tool("create_document", {"doctype": "Stock Entry", "data": se_data})
	if "error" in se:
		return {"ok": False, "error": se["error"]}
	return {
		"ok": True,
		"name": se.get("name"),
		"doctype": "Stock Entry",
		"purpose": "Material Issue",
		"next": "Submit to confirm the stock movement.",
	}
