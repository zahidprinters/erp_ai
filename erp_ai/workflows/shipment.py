# ---------------------------------------------------------------------------
# Shipment receipt workflow — record incoming goods.
# Parses natural language shipment text, resolves items/suppliers,
# and creates a Purchase Receipt or Stock Entry (Material Receipt).
# ---------------------------------------------------------------------------
import re
from typing import Any, Dict


def handle_shipment_nl(text: str, mcp) -> Dict[str, Any]:
    """Parse natural language shipment text and create receipt workflow."""
    supplier = None
    m = re.search(r"(?:from|supplier|vendor)\s+([A-Za-z0-9 .&-]{2,40}?)(?:,|\.|vehicle|arriv|$)", text, re.I)
    if m:
        supplier = m.group(1).strip()

    vehicle = None
    m = re.search(r"(?:vehicle|truck|van|no\.|number)\s*[:\\-]?\s*([A-Z]{2,4}[- ][0-9]{3,4})", text, re.I)
    if m:
        vehicle = m.group(1).strip()

    items = []
    for m in re.finditer(r"([0-9][0-9,.]*)\s*(?:pcs|pieces|nos|units|kg|boxes|sets)?\s+([A-Za-z][A-Za-z0-9 -]{2,40}?)(?=\s+(?:arriv|from|to|in|,|\.)|,|\.|$)", text, re.I):
        name = m.group(2).strip()
        try:
            q = float(m.group(1).replace(",", ""))
        except (ValueError, TypeError):
            q = None
        if name and q:
            items.append({"item_name": name, "qty": q})

    if not items:
        for m in re.finditer(r"\b((?:pump\s+)?springs?|bolts?|nuts?|bearings?|gaskets?|seals?|valves?|pumps?)\b", text, re.I):
            items.append({"item_name": m.group(1).strip(), "qty": None})

    missing = []
    if not supplier:
        missing.append("supplier (who sent it?)")
    if not items:
        missing.append("items + quantities (what arrived & how many?)")

    if missing:
        return {
            "ok": False,
            "missing": missing,
            "message": "I can record this shipment. Please provide:\n" + "\n".join("- " + x for x in missing),
        }

    for it in items:
        nm = it.get("item_name", "")
        found = mcp.call_tool("search_documents", {"query": nm, "doctype": "Item", "limit": 1})
        res = found.get("results", [])
        if res:
            it["item_code"] = res[0]["name"]
        else:
            it["item_code"] = nm.replace(" ", "-").upper()

        data = {"supplier": supplier, "vehicle_no": vehicle, "items": items, "remarks": text[:200]}
    # Return the parsed data so the caller can show a preview before execution
    return {"ok": True, "data": data, "message": "Shipment parsed. Review and confirm to create receipt."}


def create_shipment_receipt(data: Dict[str, Any], mcp) -> Dict[str, Any]:
    """Create a Purchase Receipt or Stock Entry for an incoming shipment."""
    import frappe

    from erp_ai.rbac import check_permission
    user = frappe.session.user
    err = check_permission(user, "Purchase Receipt", "create")
    if err:
        return {"ok": False, "error": err}
    err = check_permission(user, "Stock Entry", "create")
    if err:
        return {"ok": False, "error": err}
    import frappe
    supplier = data.get("supplier")
    if not supplier:
        return {"ok": False, "error": "Supplier name required"}

    steps = []

    # Ensure supplier exists
    exists = mcp.call_tool("query_doctype", {"doctype": "Supplier", "filters": {"supplier_name": supplier}})
    if exists.get("count", 0) == 0:
        created = mcp.call_tool("create_document", {"doctype": "Supplier", "data": {
            "doctype": "Supplier", "supplier_name": supplier, "supplier_type": "Company",
            "supplier_group": "All Supplier Groups"}})
        steps.append("Supplier created: %s" % created.get("name", supplier))

    items = data.get("items") or []
    if not items:
        return {"ok": False, "error": "items required"}

    warehouse = data.get("warehouse") or "Stores - SPI" if frappe.db.exists("Warehouse", "Stores - SPI") else (data.get("warehouse") or "Stores")

    # Validate items exist; create if missing
    for it in items:
        ic = it.get("item_code")
        if not ic:
            return {"ok": False, "error": "item_code required in every item"}
        found = mcp.call_tool("query_doctype", {"doctype": "Item", "filters": {"name": ic}})
        if found.get("count", 0) == 0:
            created = mcp.call_tool("create_document", {"doctype": "Item", "data": {
                "doctype": "Item", "item_code": ic, "item_name": it.get("item_name", ic),
                "item_group": it.get("item_group", "Raw Material"), "stock_uom": it.get("uom", "Nos"),
                "is_stock_item": 1, "standard_rate": it.get("rate", 0)}})
            steps.append("Item created: %s" % created.get("name", ic))

    remarks = " | ".join(filter(None, ["Vehicle: %s" % data.get("vehicle_no") if data.get("vehicle_no") else None, data.get("remarks", "")]))

    # Prefer Purchase Receipt
    pr_data = {
        "doctype": "Purchase Receipt", "supplier": supplier,
        "company": frappe.defaults.get_global_default("company"),
        "items": [{"item_code": it["item_code"], "qty": it.get("qty", 0),
                    "rate": it.get("rate", 0), "t_warehouse": warehouse} for it in items],
        "remarks": remarks,
    }
    pr = mcp.call_tool("create_document", {"doctype": "Purchase Receipt", "data": pr_data})
    if "error" in pr:
        # Fallback to Stock Entry Material Receipt
        se_data = {
            "doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
            "purpose": "Material Receipt",
            "company": frappe.defaults.get_global_default("company"),
            "items": [{"item_code": it["item_code"], "qty": it.get("qty", 0),
                        "t_warehouse": warehouse, "basic_rate": it.get("rate", 0)} for it in items],
            "remarks": remarks,
        }
        se = mcp.call_tool("create_document", {"doctype": "Stock Entry", "data": se_data})
        if "error" in se:
            return {"ok": False, "error": se["error"], "steps": steps}
        entry = {"doctype": "Stock Entry", "name": se.get("name"), "status": "Draft"}
        steps.append("Stock Entry (Material Receipt) created: %s" % se.get("name"))
    else:
        entry = {"doctype": "Purchase Receipt", "name": pr.get("name"), "status": "Draft"}
        steps.append("Purchase Receipt created: %s" % pr.get("name"))

    steps.append("Next: submit to add stock, then Purchase Invoice, then Payment Entry to pay.")
    return {"ok": True, "entry": entry, "steps": steps}
