"""
Draft-then-confirm workflow for all ERPNext operations.

Flow:
1. User speaks naturally → AI detects intent (doctype)
2. AI extracts available data from prompt
3. AI checks required fields → asks for missing ones
4. AI stores draft as JSON in chat: [DRAFT]|doctype|json_data
5. When complete → AI shows preview/overview
6. User confirms → AI creates document (Draft)
7. User says "submit" → AI submits document
8. User modifies → AI updates draft, shows updated preview
"""

import json
import re
import frappe

# =============================================================================
# DOCTYPE SCHEMAS — define required & optional fields for each operation
# =============================================================================

DOCTYPE_SCHEMAS = {
    "Item": {
        "required": ["item_name"],
        "optional": ["item_group", "standard_rate", "stock_uom", "opening_stock", "item_code"],
        "defaults": {"item_group": "Products", "stock_uom": "Nos", "standard_rate": 0, "is_stock_item": 1},
        "labels": {
            "item_name": "Item Name",
            "item_group": "Item Group",
            "standard_rate": "Price / Rate",
            "stock_uom": "Unit (UOM)",
            "opening_stock": "Opening Stock Qty",
            "item_code": "Item Code",
        },
    },
    "Sales Invoice": {
        "required": ["customer", "items"],
        "optional": ["due_date", "discount_percent", "taxes_and_charges", "remarks", "update_stock"],
        "defaults": {"update_stock": 1},
        "labels": {
            "customer": "Customer",
            "items": "Items",
            "due_date": "Due Date",
            "discount_percent": "Discount %",
            "taxes_and_charges": "Tax Template",
            "remarks": "Remarks",
        },
    },
    "Purchase Invoice": {
        "required": ["supplier", "items"],
        "optional": ["due_date", "discount_percent", "taxes_and_charges", "remarks", "update_stock"],
        "defaults": {"update_stock": 1},
        "labels": {
            "supplier": "Supplier",
            "items": "Items",
            "due_date": "Due Date",
            "discount_percent": "Discount %",
            "taxes_and_charges": "Tax Template",
            "remarks": "Remarks",
        },
    },
    "Customer": {
        "required": ["customer_name"],
        "optional": ["customer_group", "territory", "mobile_no", "email"],
        "defaults": {"customer_group": "Commercial", "territory": "Pakistan"},
        "labels": {
            "customer_name": "Customer Name",
            "customer_group": "Customer Group",
            "territory": "Territory",
            "mobile_no": "Mobile",
            "email": "Email",
        },
    },
    "Supplier": {
        "required": ["supplier_name"],
        "optional": ["supplier_group", "mobile_no", "email"],
        "defaults": {"supplier_group": "All Supplier Groups"},
        "labels": {
            "supplier_name": "Supplier Name",
            "supplier_group": "Supplier Group",
            "mobile_no": "Mobile",
            "email": "Email",
        },
    },
    "Payment Entry": {
        "required": ["payment_type", "party_type", "party", "paid_amount"],
        "optional": ["reference_no", "reference_date", "remarks"],
        "defaults": {},
        "labels": {
            "payment_type": "Type (Receive/Pay)",
            "party_type": "Party Type (Customer/Supplier)",
            "party": "Party Name",
            "paid_amount": "Amount",
            "reference_no": "Reference No",
        },
    },
}


# =============================================================================
# DRAFT STORE — use AI Chat Message with [DRAFT] prefix
# =============================================================================

def _draft_key(session):
    return "[DRAFT]|"


def save_draft(session, doctype, data):
    """Save draft data to chat message."""
    if not session:
        return False
    key = _draft_key(session)
    content = f"{key}{doctype}|{json.dumps(data, default=str)}"
    frappe.get_doc({
        "doctype": "AI Chat Message",
        "user": frappe.session.user,
        "session_id": session,
        "role": "user",
        "content": content,
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    return True


def get_draft(session):
    """Get the latest draft. Returns (doctype, data) or (None, None)."""
    if not session:
        return None, None
    key = _draft_key(session)
    msg = frappe.db.get_all(
        "AI Chat Message",
        filters={"session_id": session, "role": "user", "content": ["like", f"{key}%"]},
        fields=["content"],
        order_by="creation desc",
        limit=1,
    )
    if not msg:
        return None, None
    content = msg[0].content
    rest = content[len(key):]
    pipe_idx = rest.index("|")
    doctype = rest[:pipe_idx]
    data = json.loads(rest[pipe_idx + 1:])
    return doctype, data


def clear_draft(session):
    """Mark draft as consumed."""
    pass


# =============================================================================
# FIELD EXTRACTION — natural language → structured data
# =============================================================================

def extract_item_fields(prompt):
    """Extract item fields from natural language."""
    p = prompt
    pl = p.lower()
    data = {}

    # Item name
    m = re.search(r'(?:named|name|called|ka naam|naam)[:]?\s*([^,;.]+?)(?:\s+(?:group|category|price|rate|cost|keemat|py|stock|qty|quantity|opening|received|for|with|in)\b|,|;|$)', p, re.I)
    if not m:
        m = re.search(r'(?:add|create|banao|banaiye)\s*(?:a\s+|new\s+)?(?:item|product|itm)[:\-]?\s*([A-Za-z][A-Za-z0-9 .&\-]{2,40}?)(?=\s+(?:group|category|price|rate|cost|keemat|py|stock|qty|quantity|opening|received|for|with|in)\b|,|;|$)', p, re.I)
    if not m:
        m = re.search(r'(?:add|create|banao|banaiye)\s+([A-Za-z][A-Za-z0-9 .&\-]{2,40}?)(?=\s+(?:group|category|price|rate|cost|keemat|py|stock|qty|quantity|opening|received|for|with|in)\b|,|;|$)', p, re.I)
    if m:
        data["item_name"] = m.group(1).strip().rstrip(",").strip()

    # Item group
    m = re.search(r'(?:group|category)[:]?\s*([^,;.]+?)(?:\s*(?:price|rate|cost|keemat|py|stock|qty|quantity|opening)\b|$)', p, re.I)
    if m:
        data["item_group"] = m.group(1).strip()

    # Price with unit: "price is 20 per gram", "20 per kg"
    m = re.search(r'(?:price|rate|cost|keemat|py)?\s*(?:is|=|:)?\s*([0-9][0-9,.]*)\s*(?:rs|rupees|pkr|/-)?\s*(?:per|/)\s*(gram|gm|kg|kilo|kilogram|meter|litre|piece|unit)', p, re.I)
    if m:
        data["standard_rate"] = float(m.group(1).replace(",", ""))
        unit = m.group(2).lower()
        if unit in ("gram", "gm"):
            data["stock_uom"] = "Gram"
        elif unit in ("kg", "kilo", "kilogram"):
            data["stock_uom"] = "Kg"
        elif unit == "meter":
            data["stock_uom"] = "Meter"
        elif unit == "litre":
            data["stock_uom"] = "Litre"
        else:
            data["stock_uom"] = "Nos"
    else:
        # Simple price
        m = re.search(r'(?:price|rate|cost|keemat|py)\s*(?:is|=|:|ki hai)\s*([0-9][0-9,.]*)', p, re.I) or \
            re.search(r'(?:price|rate|cost|keemat|py)[:=]?\s*([0-9][0-9,.]*)', p, re.I) or \
            re.search(r'([0-9][0-9,.]*)\s*(?:rs|rupees|pkr|/-)\b', p, re.I)
        if m:
            data["standard_rate"] = float(m.group(1).replace(",", ""))

    # Stock with unit: "4kg", "4 kg", "we have 4kg", "4000 grams"
    m = re.search(r'(?:we have|stock|qty|quantity|opening|received|milay|mile|aa gaya)?\s*([0-9][0-9,.]*)\s*(kg|kilo|kilogram|gram|gm|g)\b', p, re.I)
    if m:
        qty = float(m.group(1).replace(",", ""))
        unit = m.group(2).lower()
        if unit in ("kg", "kilo", "kilogram"):
            # If UOM already set to Gram (from price per gram), convert kg to grams
            if data.get("stock_uom") == "Gram":
                data["opening_stock"] = qty * 1000  # 4kg = 4000 grams
            else:
                data["opening_stock"] = qty
                if "stock_uom" not in data:
                    data["stock_uom"] = "Kg"
        elif unit in ("gram", "gm", "g"):
            data["opening_stock"] = qty
            if "stock_uom" not in data:
                data["stock_uom"] = "Gram"
    else:
        # Simple stock
        m = re.search(r'(?:stock|qty|quantity|opening|received|milay|mile)\s*(?:of|is|=|:)?\s*([0-9][0-9,.]*)', p, re.I) or \
            re.search(r'([0-9][0-9,.]*)\s*(?:pcs|nos|units|pieces|dozen)\b', p, re.I)
        if m:
            data["opening_stock"] = float(m.group(1).replace(",", ""))

    # UOM fallback
    if "stock_uom" not in data:
        m = re.search(r'\b(pcs|nos|pieces|units|dozen|kg|gm|gram|meter|litre|lit|feet|inch|set|box|bag|roll|coil)\b', p, re.I)
        if m:
            uom = m.group(1).lower()
            uom_map = {"pcs": "Nos", "nos": "Nos", "pieces": "Nos", "units": "Nos",
                       "dozen": "Dozen", "kg": "Kg", "gm": "Gram", "gram": "Gram",
                       "meter": "Meter", "litre": "Litre", "lit": "Litre",
                       "feet": "Feet", "inch": "Inch", "set": "Set", "box": "Box",
                       "bag": "Bag", "roll": "Roll", "coil": "Coil"}
            data["stock_uom"] = uom_map.get(uom, uom.capitalize())

    return data

def extract_invoice_fields(prompt):
    """Extract invoice fields from natural language."""
    p = prompt
    data = {}
    # Customer / Supplier
    m = re.search(r'(?:for|to|customer|client|ke liye)\s+([A-Za-z0-9 .&-]{2,40}?)(?:,|\.|\d|$)', p, re.I)
    if m:
        data["customer"] = m.group(1).strip()
    # Items: '2 pump springs @ 500'
    items = []
    for m in re.finditer(r'([0-9,.]+)\s*(?:pcs|nos|units)?\s*([A-Za-z][A-Za-z0-9 -]{2,40}?)\s*(?:@|at|rate|price)\s*([0-9,.]+)', p, re.I):
        q = float(m.group(1).replace(",", ""))
        nm = m.group(2).strip()
        r = float(m.group(3).replace(",", ""))
        items.append({"description": nm, "qty": q, "rate": r})
    if items:
        data["items"] = items
    # Discount
    m = re.search(r'(?:discount|disc)\s*([0-9][0-9,.]*)\s*%?', p, re.I)
    if m:
        data["discount_percent"] = float(m.group(1).replace(",", ""))
    # Due date
    m = re.search(r'due\s*(?:in|date)?\s*([0-9]+)\s*(?:days?|din)?', p, re.I)
    if m:
        data["due_days"] = int(m.group(1))
    return data


def extract_party_fields(prompt, party_type="customer"):
    """Extract customer/supplier fields."""
    p = prompt
    data = {}
    field = "customer_name" if party_type == "customer" else "supplier_name"
    m = re.search(r'(?:named|name|called|ka naam|naam)[:]?\s*([^,;.]+?)(?:\s*(?:group|mobile|phone|email|contact)\b|,|;|$)', p, re.I)
    if not m:
        m = re.search(r'(?:add|create|banao|banaiye)\s*(?:a\s+|new\s+)?(?:customer|client|supplier|vendor)[:\-]?\s*([A-Za-z][A-Za-z0-9 .&\-]{2,40}?)(?=\s+(?:group|mobile|phone|email|contact)\b|,|;|$)', p, re.I)
    if m:
        data[field] = m.group(1).strip().rstrip(",").strip()
    # Mobile
    m = re.search(r'(?:mobile|phone|contact|number)[:]?\s*([0-9+\-() ]{7,15})', p, re.I)
    if m:
        data["mobile_no"] = m.group(1).strip()
    # Email
    m = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', p)
    if m:
        data["email"] = m.group(1).strip()
    # Group
    m = re.search(r'(?:group|category)[:]?\s*([^,;.]+)', p, re.I)
    if m:
        data[f"{party_type}_group"] = m.group(1).strip()
    return data


# =============================================================================
# MISSING FIELDS CHECK
# =============================================================================

def get_missing_fields(doctype, data):
    """Check which required fields are missing."""
    schema = DOCTYPE_SCHEMAS.get(doctype)
    if not schema:
        return []
    missing = []
    for field in schema["required"]:
        val = data.get(field)
        if val is None or val == "" or (field == "items" and not val):
            missing.append(field)
    return missing


def get_missing_labels(doctype, missing_fields):
    """Get human-readable labels for missing fields."""
    schema = DOCTYPE_SCHEMAS.get(doctype)
    if not schema:
        return missing_fields
    labels = schema.get("labels", {})
    return [labels.get(f, f.replace("_", " ").title()) for f in missing_fields]


# =============================================================================
# PREVIEW GENERATOR
# =============================================================================

def generate_preview(doctype, data):
    """Generate a human-readable preview."""
    schema = DOCTYPE_SCHEMAS.get(doctype, {})
    labels = schema.get("labels", {})
    lines = []

    if doctype == "Item":
        lines.append("📦 New Item Preview:")
        lines.append(f"  Name: {data.get('item_name', '-')}")
        lines.append(f"  Group: {data.get('item_group', 'Products')}")
        lines.append(f"  Price: {data.get('standard_rate', 0):,.0f}")
        lines.append(f"  UOM: {data.get('stock_uom', 'Nos')}")
        if data.get("opening_stock"):
            lines.append(f"  Opening Stock: {data['opening_stock']:,.0f}")

    elif doctype == "Sales Invoice":
        lines.append("🧾 Sales Invoice Preview:")
        lines.append(f"  Customer: {data.get('customer', '-')}")
        lines.append("  Items:")
        for i, it in enumerate(data.get("items", []), 1):
            qty = it.get("qty", 1)
            rate = it.get("rate", 0)
            total = qty * rate
            lines.append(f"    {i}. {it.get('description', it.get('item_code', '-'))} — {qty:g} × {rate:,.0f} = {total:,.0f}")
        subtotal = sum(it.get("qty", 1) * it.get("rate", 0) for it in data.get("items", []))
        lines.append(f"  Subtotal: {subtotal:,.0f}")
        if data.get("discount_percent"):
            disc = subtotal * data["discount_percent"] / 100
            lines.append(f"  Discount ({data['discount_percent']}%): -{disc:,.0f}")
            lines.append(f"  Total: {subtotal - disc:,.0f}")
        else:
            lines.append(f"  Total: {subtotal:,.0f}")

    elif doctype == "Purchase Invoice":
        lines.append("📋 Purchase Invoice Preview:")
        lines.append(f"  Supplier: {data.get('supplier', '-')}")
        lines.append("  Items:")
        for i, it in enumerate(data.get("items", []), 1):
            qty = it.get("qty", 1)
            rate = it.get("rate", 0)
            total = qty * rate
            lines.append(f"    {i}. {it.get('description', it.get('item_code', '-'))} — {qty:g} × {rate:,.0f} = {total:,.0f}")
        subtotal = sum(it.get("qty", 1) * it.get("rate", 0) for it in data.get("items", []))
        lines.append(f"  Subtotal: {subtotal:,.0f}")
        if data.get("discount_percent"):
            disc = subtotal * data["discount_percent"] / 100
            lines.append(f"  Discount ({data['discount_percent']}%): -{disc:,.0f}")
            lines.append(f"  Total: {subtotal - disc:,.0f}")
        else:
            lines.append(f"  Total: {subtotal:,.0f}")

    elif doctype == "Customer":
        lines.append("👤 New Customer Preview:")
        lines.append(f"  Name: {data.get('customer_name', '-')}")
        if data.get("mobile_no"):
            lines.append(f"  Mobile: {data['mobile_no']}")
        if data.get("email"):
            lines.append(f"  Email: {data['email']}")
        if data.get("customer_group"):
            lines.append(f"  Group: {data['customer_group']}")

    elif doctype == "Supplier":
        lines.append("🏭 New Supplier Preview:")
        lines.append(f"  Name: {data.get('supplier_name', '-')}")
        if data.get("mobile_no"):
            lines.append(f"  Mobile: {data['mobile_no']}")
        if data.get("email"):
            lines.append(f"  Email: {data['email']}")
        if data.get("supplier_group"):
            lines.append(f"  Group: {data['supplier_group']}")

    else:
        lines.append(f"📄 {doctype} Preview:")
        for k, v in data.items():
            label = labels.get(k, k.replace("_", " ").title())
            lines.append(f"  {label}: {v}")

    return "\n".join(lines)


# =============================================================================
# INTENT DETECTION → DOCTYPE
# =============================================================================

INTENT_MAP = {
    "create item": "Item", "add item": "Item", "item banao": "Item", "item banaiye": "Item",
    "item create": "Item", "item add": "Item", "new item": "Item", "nyaa item": "Item",
    "create invoice": "Sales Invoice", "add invoice": "Sales Invoice", "invoice banao": "Sales Invoice",
    "invoice banaiye": "Sales Invoice", "make invoice": "Sales Invoice", "bill banao": "Sales Invoice",
    "create po": "Purchase Invoice", "add po": "Purchase Invoice", "purchase order": "Purchase Invoice",
    "po banao": "Purchase Invoice", "po banaiye": "Purchase Invoice", "make po": "Purchase Invoice",
    "purchase invoice": "Purchase Invoice",
    "create customer": "Customer", "add customer": "Customer", "customer banao": "Customer",
    "customer banaiye": "Customer", "new customer": "Customer",
    "create supplier": "Supplier", "add supplier": "Supplier", "supplier banao": "Supplier",
    "supplier banaiye": "Supplier", "new supplier": "Supplier", "vendor banao": "Supplier",
    "create payment": "Payment Entry", "add payment": "Payment Entry", "payment banao": "Payment Entry",
    "payment banaiye": "Payment Entry", "receive payment": "Payment Entry", "make payment": "Payment Entry",
}


def detect_intent(prompt):
    pl = prompt.lower().strip()
    for kw, doctype in INTENT_MAP.items():
        if kw in pl:
            return doctype
    if re.search(r'\b(add|create|banao|banaiye)\b.*\b(item|product|itm)\b', pl):
        return "Item"
    if re.search(r'\b(add|create|banao|banaiye|make)\b.*\b(invoice|bill)\b', pl):
        return "Sales Invoice"
    if re.search(r'\b(add|create|banao|banaiye|make)\b.*\b(po|purchase)\b', pl):
        return "Purchase Invoice"
    if re.search(r'\b(add|create|banao|banaiye)\b.*\b(customer|client)\b', pl):
        return "Customer"
    if re.search(r'\b(add|create|banao|banaiye)\b.*\b(supplier|vendor)\b', pl):
        return "Supplier"
    if re.search(r'\b(payment|receive|paid|pay)\b', pl) and re.search(r'\b(from|to|se|ko)\b', pl):
        return "Payment Entry"
    return None


# =============================================================================
# DOCUMENT CREATION
# =============================================================================

def create_document_from_draft(doctype, data, mcp):
    schema = DOCTYPE_SCHEMAS.get(doctype, {})
    defaults = schema.get("defaults", {})
    for k, v in defaults.items():
        if k not in data or data[k] is None:
            data[k] = v
    if doctype == "Item":
        return _create_item_doc(data, mcp)
    elif doctype == "Sales Invoice":
        return _create_sales_invoice_doc(data, mcp)
    elif doctype == "Purchase Invoice":
        return _create_purchase_invoice_doc(data, mcp)
    elif doctype == "Customer":
        return _create_customer_doc(data, mcp)
    elif doctype == "Supplier":
        return _create_supplier_doc(data, mcp)
    elif doctype == "Payment Entry":
        return _create_payment_entry_doc(data, mcp)
    return {"error": f"Unsupported doctype: {doctype}"}


def _create_item_doc(data, mcp):
    item_name = data.get("item_name", "").strip()
    if not item_name:
        return {"error": "item_name required"}
    existing = frappe.db.get_value("Item", {"item_name": item_name}, "name")
    if existing:
        return {"error": f"Item '{item_name}' already exists ({existing})", "duplicate": True}
    code = item_name.replace(" ", "-").upper()
    ig = data.get("item_group", "Products")
    uom = data.get("stock_uom", "Nos")
    if not frappe.db.exists("Item Group", ig):
        try:
            frappe.get_doc({"doctype": "Item Group", "item_group_name": ig}).insert(ignore_permissions=True)
        except Exception:
            pass
    doc_data = {"doctype": "Item", "item_code": code, "item_name": item_name, "item_group": ig, "stock_uom": uom, "is_stock_item": 1, "standard_rate": data.get("standard_rate", 0)}
    result = mcp.call_tool("create_document", {"doctype": "Item", "data": doc_data})
    if "error" in result:
        doc_data["item_code"] = code + "-" + frappe.generate_hash(length=4).upper()
        result = mcp.call_tool("create_document", {"doctype": "Item", "data": doc_data})
    if "error" in result:
        return result
    if data.get("opening_stock"):
        wh = "Stores - SPI" if frappe.db.exists("Warehouse", "Stores - SPI") else "Stores"
        se = mcp.call_tool("create_document", {"doctype": "Stock Entry", "data": {"doctype": "Stock Entry", "stock_entry_type": "Material Receipt", "company": frappe.defaults.get_global_default("company"), "items": [{"item_code": result["name"], "qty": data["opening_stock"], "t_warehouse": wh, "basic_rate": data.get("standard_rate", 0)}]}})
        if "error" not in se:
            result["stock_entry"] = se.get("name")
    frappe.db.commit()
    return result


def _create_sales_invoice_doc(data, mcp):
    customer = data.get("customer")
    if not customer:
        return {"error": "customer required"}
    items = data.get("items", [])
    if not items:
        return {"error": "items required"}
    exists = mcp.call_tool("query_doctype", {"doctype": "Customer", "filters": {"name": customer}})
    if exists.get("count", 0) == 0:
        return {"error": f"Customer '{customer}' not found"}
    final_items = []
    for it in items:
        desc = it.get("description", it.get("item_code", ""))
        found = mcp.call_tool("search_documents", {"query": desc, "doctype": "Item", "limit": 1})
        res = found.get("results", [])
        code = res[0]["name"] if res else desc
        final_items.append({"item_code": code, "qty": it.get("qty", 1), "rate": it.get("rate", 0)})
    si_data = {"doctype": "Sales Invoice", "customer": customer, "company": frappe.defaults.get_global_default("company"), "update_stock": 1 if data.get("update_stock") else 0, "items": final_items}
    if data.get("taxes_and_charges"):
        si_data["taxes_and_charges"] = data["taxes_and_charges"]
    result = mcp.call_tool("create_document", {"doctype": "Sales Invoice", "data": si_data})
    if "error" in result:
        return result
    frappe.db.commit()
    result["print_url"] = f"/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Invoice&name={result.get('name')}&format=Standard"
    return result


def _create_purchase_invoice_doc(data, mcp):
    supplier = data.get("supplier")
    if not supplier:
        return {"error": "supplier required"}
    items = data.get("items", [])
    if not items:
        return {"error": "items required"}
    exists = mcp.call_tool("query_doctype", {"doctype": "Supplier", "filters": {"name": supplier}})
    if exists.get("count", 0) == 0:
        return {"error": f"Supplier '{supplier}' not found"}
    final_items = []
    for it in items:
        desc = it.get("description", it.get("item_code", ""))
        found = mcp.call_tool("search_documents", {"query": desc, "doctype": "Item", "limit": 1})
        res = found.get("results", [])
        code = res[0]["name"] if res else desc
        final_items.append({"item_code": code, "qty": it.get("qty", 1), "rate": it.get("rate", 0)})
    pi_data = {"doctype": "Purchase Invoice", "supplier": supplier, "company": frappe.defaults.get_global_default("company"), "update_stock": 1 if data.get("update_stock") else 0, "items": final_items}
    if data.get("taxes_and_charges"):
        pi_data["taxes_and_charges"] = data["taxes_and_charges"]
    result = mcp.call_tool("create_document", {"doctype": "Purchase Invoice", "data": pi_data})
    if "error" in result:
        return result
    frappe.db.commit()
    result["print_url"] = f"/api/method/frappe.utils.print_format.download_pdf?doctype=Purchase%20Invoice&name={result.get('name')}&format=Standard"
    return result


def _create_customer_doc(data, mcp):
    name = data.get("customer_name", "").strip()
    if not name:
        return {"error": "customer_name required"}
    doc_data = {"doctype": "Customer", "customer_name": name, "customer_group": data.get("customer_group", "All Customer Groups"), "territory": data.get("territory", "All Territories")}
    if data.get("mobile_no"):
        doc_data["mobile_no"] = data["mobile_no"]
    if data.get("email"):
        doc_data["email_id"] = data["email"]
    result = mcp.call_tool("create_document", {"doctype": "Customer", "data": doc_data})
    if "error" not in result:
        frappe.db.commit()
    return result


def _create_supplier_doc(data, mcp):
    name = data.get("supplier_name", "").strip()
    if not name:
        return {"error": "supplier_name required"}
    doc_data = {"doctype": "Supplier", "supplier_name": name, "supplier_group": data.get("supplier_group", "All Supplier Groups")}
    if data.get("mobile_no"):
        doc_data["mobile_no"] = data["mobile_no"]
    if data.get("email"):
        doc_data["email_id"] = data["email"]
    result = mcp.call_tool("create_document", {"doctype": "Supplier", "data": doc_data})
    if "error" not in result:
        frappe.db.commit()
    return result


def _create_payment_entry_doc(data, mcp):
    party = data.get("party")
    amount = data.get("paid_amount", 0)
    if not party or not amount:
        return {"error": "party and paid_amount required"}
    doc_data = {"doctype": "Payment Entry", "payment_type": data.get("payment_type", "Receive"), "party_type": data.get("party_type", "Customer"), "party": party, "paid_amount": amount, "received_amount": data.get("received_amount", amount), "company": frappe.defaults.get_global_default("company")}
    if data.get("reference_no"):
        doc_data["reference_no"] = data["reference_no"]
    result = mcp.call_tool("create_document", {"doctype": "Payment Entry", "data": doc_data})
    if "error" not in result:
        frappe.db.commit()
    return result 
