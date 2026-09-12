# ---------------------------------------------------------------------------
# Stock issue workflow — issue/transfer stock to a department or person.
# ---------------------------------------------------------------------------
import re
from typing import Any, Dict


def handle_issue_nl(text: str, mcp) -> Dict[str, Any]:
    """Parse natural language stock issue text."""
    qty = None
    m = re.search(r"(?:issue|transfer|jari)\s+([0-9,.]+)", text, re.I)
    if m:
        qty = float(m.group(1).replace(",", ""))

    item = None
    m = re.search(r"(?:issue|transfer|jari)[^a-z]*([0-9,.]+)\s*(?:pcs|nos|units|kg)?\s*([A-Za-z][A-Za-z0-9 -]{2,40}?)(?:\s+to\s+|,|\.|$)", text, re.I)
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

    data = {"item_code": item_code, "qty": qty, "issue_type": "Material Issue",
            "issued_to": person, "remarks": text[:200]}
    return create_stock_issue(data, mcp)


def create_stock_issue(data: Dict[str, Any], mcp) -> Dict[str, Any]:
    """Create a Stock Entry for material issue."""
    import frappe

    from erp_ai.rbac import check_permission
    err = check_permission(frappe.session.user, "Stock Entry", "create")
    if err:
        return {"ok": False, "error": err}
    import frappe
    item_code = data.get("item_code")
    qty = data.get("qty")
    from_wh = data.get("from_warehouse")
    if not (item_code and qty and from_wh):
        return {"ok": False, "error": "item_code, qty and from_warehouse required"}

    se_data = {
        "doctype": "Stock Entry", "stock_entry_type": "Material Issue",
        "purpose": "Material Issue",
        "company": frappe.defaults.get_global_default("company"),
        "items": [{"item_code": item_code, "qty": qty, "s_warehouse": from_wh}],
        "remarks": data.get("remarks", ""),
    }
    se = mcp.call_tool("create_document", {"doctype": "Stock Entry", "data": se_data})
    if "error" in se:
        return {"ok": False, "error": se["error"]}
    return {"ok": True, "name": se.get("name"), "doctype": "Stock Entry",
            "purpose": "Material Issue",
            "next": "Submit to confirm the stock movement."}
