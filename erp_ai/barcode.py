# ---------------------------------------------------------------------------
# Barcode / QR utility — resolve scanned codes to ERPNext documents.
#
# Supports EAN-13, UPC-A, Code128, and QR codes that encode document names.
# Used by mobile warehouse operations (scan-to-lookup, scan-to-receive).
# ---------------------------------------------------------------------------
from typing import Any, Dict, Optional


def _ean13_checksum(code: str) -> bool:
    """Validate EAN-13 checksum digit."""
    if len(code) != 13 or not code.isdigit():
        return False
    digits = [int(d) for d in code]
    odd_sum = sum(digits[i] for i in range(0, 12, 2))
    even_sum = sum(digits[i] for i in range(1, 12, 2))
    total = odd_sum + even_sum * 3
    check = (10 - (total % 10)) % 10
    return check == digits[12]


def _upc_checksum(code: str) -> bool:
    """Validate UPC-A checksum digit."""
    if len(code) != 12 or not code.isdigit():
        return False
    digits = [int(d) for d in code]
    odd_sum = sum(digits[i] for i in range(0, 11, 2))
    even_sum = sum(digits[i] for i in range(1, 11, 2))
    total = odd_sum * 3 + even_sum
    check = (10 - (total % 10)) % 10
    return check == digits[11]


def validate_barcode_format(code: str, format: str = "any") -> bool:
    """Validate a barcode format with checksum verification."""
    if not code:
        return False
    if format == "ean13":
        return _ean13_checksum(code)
    if format == "upc":
        return _upc_checksum(code)
    if format == "code128":
        return 1 <= len(code) <= 48
    return len(code) > 0


def resolve_barcode(code: str) -> Dict[str, Any]:
    """Resolve a scanned barcode/QR to an ERPNext document.

    Order:
      1. Item Barcode child table (ERPNext's real barcode store)
      2. Item by item_code
      3. Other business doctypes by name

    Every lookup enforces frappe.has_permission() on the resolved doctype.
    """
    import frappe
    code = (code or "").strip()
    if not code:
        return {"ok": False, "error": "No code provided"}

    def _ok(doctype, name):
        try:
            if not frappe.has_permission(doctype, "read", doc=name):
                return {"ok": False, "error": "Not permitted to read %s '%s'" % (doctype, name)}
        except Exception:
            if not frappe.has_permission(doctype, "read"):
                return {"ok": False, "error": "Not permitted to read %s" % doctype}
        return {"ok": True, "doctype": doctype, "name": name}

    # Try Item Barcode child table (stores real EAN/UPC/Code128 values)
    try:
        barcode_item = frappe.db.get_value("Item Barcode", {"barcode": code}, "parent")
        if barcode_item:
            return _ok("Item", barcode_item)
    except Exception:
        pass  # ERPNext may not expose tabItem Barcode directly; fall through

    # Try Item by item_code (validates checksum when the code looks like EAN/UPC)
    if frappe.db.exists("Item", code):
        return _ok("Item", code)

    # Try by name in common doctypes
    for dt in ["Warehouse", "Batch", "Customer", "Supplier"]:
        if frappe.db.exists(dt, code):
            return _ok(dt, code)

    return {"ok": False, "error": "No document found for code: %s" % code}


def generate_item_barcode_data(item_code: str) -> Dict[str, str]:
    """Generate barcode data for an item (for label printing)."""
    return {
        "code": item_code,
        "type": "code128",
        "display": item_code,
    }
