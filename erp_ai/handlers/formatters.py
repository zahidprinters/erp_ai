# ---------------------------------------------------------------------------
# Document formatters — turn ERP documents into human-readable text.
#
# Single responsibility: given a doctype and document dict, return a formatted
# string for display. No DB access, no business logic.
# ---------------------------------------------------------------------------
from typing import Any, Dict


def format_document_view(doctype: str, doc: Dict[str, Any]) -> str:
    """Return a human-readable view of any document."""
    lines = ["📄 %s: **%s**" % (doctype, doc.get("name", "?"))]
    lines.append("  Status: %s (0=Draft, 1=Submitted, 2=Cancelled)" % doc.get("docstatus", 0))

    if doctype == "Item":
        lines.append("  Name: %s" % doc.get("item_name", ""))
        lines.append("  Group: %s" % doc.get("item_group", ""))
        lines.append("  Price: %s" % doc.get("standard_rate", 0))
        lines.append("  UOM: %s" % doc.get("stock_uom", ""))
    elif doctype in ("Sales Invoice", "Purchase Invoice"):
        party = doc.get("customer", doc.get("supplier", ""))
        lines.append("  %s: %s" % ("Customer" if "Sales" in doctype else "Supplier", party))
        lines.append("  Grand Total: %s" % doc.get("grand_total", 0))
        lines.append("  Status: %s" % doc.get("status", ""))
        if doc.get("items"):
            lines.append("  Items:")
            for it in doc["items"][:5]:
                lines.append("    - %s | %s × %s" % (it.get("item_code", ""), it.get("qty", 0), it.get("rate", 0)))
    elif doctype == "Customer":
        lines.append("  Name: %s" % doc.get("customer_name", ""))
        lines.append("  Group: %s" % doc.get("customer_group", ""))
        lines.append("  Mobile: %s" % doc.get("mobile_no", ""))
    elif doctype == "Supplier":
        lines.append("  Name: %s" % doc.get("supplier_name", ""))
        lines.append("  Group: %s" % doc.get("supplier_group", ""))
        lines.append("  Mobile: %s" % doc.get("mobile_no", ""))
    elif doctype in ("Sales Order", "Purchase Order"):
        party = doc.get("customer", doc.get("supplier", ""))
        lines.append("  %s: %s" % ("Customer" if "Sales" in doctype else "Supplier", party))
        lines.append("  Delivery Date: %s" % doc.get("delivery_date", ""))
        lines.append("  Status: %s" % doc.get("status", ""))
    elif doctype == "Payment Entry":
        lines.append("  Type: %s" % doc.get("payment_type", ""))
        lines.append("  Party: %s (%s)" % (doc.get("party", ""), doc.get("party_type", "")))
        lines.append("  Amount: %s" % doc.get("paid_amount", 0))
    elif doctype == "Stock Entry":
        lines.append("  Type: %s" % doc.get("stock_entry_type", ""))
        lines.append("  From: %s" % doc.get("from_warehouse", "-"))
        lines.append("  To: %s" % doc.get("to_warehouse", "-"))
    return "\n".join(lines)
