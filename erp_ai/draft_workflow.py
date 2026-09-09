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
# UOM CONVERSION FACTORS (relative to base unit)
# Base units: Gram (weight), Meter (length), Litre (volume), Nos (count)
# =============================================================================

UOM_CONVERSIONS = {
    # Weight (base: Gram)
    "Gram": ("weight", 1),
    "Microgram": ("weight", 0.000001),
    "Milligram": ("weight", 0.001),
    "Kg": ("weight", 1000),
    "Tonne": ("weight", 1000000),
    "Quintal": ("weight", 100000),
    "Carat": ("weight", 0.2),
    "Ounce": ("weight", 28.3495),
    "Pound": ("weight", 453.592),
    "Stone": ("weight", 6350.29),
    "Grain": ("weight", 0.0648),
    "Dram": ("weight", 1.7718),
    # Length (base: Meter)
    "Meter": ("length", 1),
    "Millimeter": ("length", 0.001),
    "Centimeter": ("length", 0.01),
    "Decimeter": ("length", 0.1),
    "Kilometer": ("length", 1000),
    "Inch": ("length", 0.0254),
    "Foot": ("length", 0.3048),
    "Yard": ("length", 0.9144),
    "Mile": ("length", 1609.34),
    "Fathom": ("length", 1.8288),
    "Hand": ("length", 0.1016),
    "Micrometer": ("length", 0.000001),
    "Nanometer": ("length", 0.000000001),
    # Volume (base: Litre)
    "Litre": ("volume", 1),
    "Millilitre": ("volume", 0.001),
    "Centilitre": ("volume", 0.01),
    "Decilitre": ("volume", 0.1),
    "Cubic Meter": ("volume", 1000),
    "Cubic Centimeter": ("volume", 0.001),
    "Cubic Millimeter": ("volume", 0.000001),
    "Cubic Inch": ("volume", 0.0163871),
    "Cubic Foot": ("volume", 28.3168),
    "Gallon (UK)": ("volume", 4.54609),
    "Gallon Liquid (US)": ("volume", 3.78541),
    # Count
    "Nos": ("count", 1),
    "Unit": ("count", 1),
    "Pair": ("count", 1),
    "Set": ("count", 1),
    "Box": ("count", 1),
    "Dozen": ("count", 12),
    "Piece": ("count", 1),
}


def convert_uom(qty, from_uom, to_uom):
    """Convert quantity from one UOM to another. Returns converted qty or None if incompatible."""
    from_info = UOM_CONVERSIONS.get(from_uom)
    to_info = UOM_CONVERSIONS.get(to_uom)
    if not from_info or not to_info:
        return None
    if from_info[0] != to_info[0]:  # Different categories (weight vs length)
        return None
    # Convert: qty * from_factor / to_factor
    return qty * from_info[1] / to_info[1]


def get_uom_category(uom_name):
    """Get the category of a UOM (weight, length, volume, count)."""
    info = UOM_CONVERSIONS.get(uom_name)
    return info[0] if info else None



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
    # Get last 5 user messages to check for draft or clear marker
    msgs = frappe.db.get_all(
        "AI Chat Message",
        filters={"session_id": session, "role": "user"},
        fields=["content"],
        order_by="creation desc",
        limit=5,
    )
    # Find the most recent draft (skip if cleared)
    for msg in msgs:
        content = msg.content or ""
        if content.startswith(key):
            rest = content[len(key):]
            pipe_idx = rest.index("|")
            doctype = rest[:pipe_idx]
            data = json.loads(rest[pipe_idx + 1:])
            return doctype, data
        elif content == "[DRAFT_CLEARED]":
            return None, None
    return None, None

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
    """Extract item fields from natural language with UOM support."""
    p = prompt
    pl = p.lower()
    data = {}

    # Item name - extract words after "item" until price/stock/group or number+unit
    _name_patterns = [
        # "add item NAME ..."
        r'(?:add|create|banao|banaiye)\s+(?:a\s+|new\s+)?(?:item|product|itm)\s+([A-Za-z][A-Za-z0-9 .&]+?)(?=\s+(?:price|rate|cost|keemat|per|stock|qty|quantity|group|category|@)\b|\s+\d+\s*(?:mm|cm|meter|inch|foot|feet|kg|gram|gm|g|pcs|nos|unit|liter|litre|ml)\b|\s*[,;]|$)',
        # "NAME resived/recived 20 leter" (name first)
        r'^([A-Za-z][A-Za-z0-9 .&]{2,30}?)\s+(?:resived|recived|resiv|reciv|aa gaya|milay|mile)\s+\d+\s*(?:kg|liter|litre|leters|liters|gram|gm|ml|mm|meter|inch|foot|piece|leter)\b',
        # "named NAME ..."
        r'(?:named|name|called|ka naam|naam)\s+([A-Za-z][A-Za-z0-9 .&]+?)(?=\s+(?:price|rate|cost|keemat|per|stock|qty|quantity|group|category)\b|\s+\d+\s*(?:mm|cm|meter|inch|foot|feet|kg|gram|gm|g)\b|\s*[,;]|$)',
        # "lubrication oil 20 liter..." (leading words before quantity+unit)
        r'^([a-z][a-z0-9 .&]+?)\s+\d+\s*(?:kg|kilo|kilogram|gram|gm|g|mm|millimeter|cm|centimeter|meter|inch|foot|feet|literal|liter|litre|ml|millilitre|pcs|nos|unit)',
    ]
    for _pat in _name_patterns:
        m = re.search(_pat, p, re.I)
        if m:
            name = m.group(1).strip().rstrip(",").strip()
            name = re.sub(r'\s+(?:size|sz|diameter|dia|length|len|leanth|width|height|thickness)\s*$', '', name, flags=re.I)
            if len(name) >= 2:
                data["item_name"] = name
                break

    # Item group
    m = re.search(r'(?:group|category)[:]?\s*([^,;.]+?)(?:\s*(?:price|rate|cost|keemat|py|stock|qty|quantity|opening)\b|$)', p, re.I)
    if m:
        data["item_group"] = m.group(1).strip()

    # Price patterns: "20 per gram", "10 pkr on 150 ml", "price is 20 per mm"
    # First try: "X pkr on Y unit" (price for a quantity)
    m = re.search(r'(?:price|rate|cost|keemat|py)?\s*(?:is|=|:)?\s*([0-9][0-9,.]*)\s*(?:rs|rupees|pkr|/-)?\s*(?:per|on)\s*([0-9][0-9,.]*)\s*(ml|millilitre|liter|litre|leter|leters|liters|litres|l|gram|gm|g|kg|mm|cm|meter|inch|foot|piece|unit|nos)', p, re.I)
    if m:
        price_val = float(m.group(1).replace(",", ""))
        qty_val = float(m.group(2).replace(",", ""))
        unit = m.group(3).lower()
        if qty_val > 0:
            data["standard_rate"] = round(price_val / qty_val, 4)  # Price per unit
        else:
            data["standard_rate"] = price_val
        uom_map = {"ml": "Millilitre", "millilitre": "Millilitre", "liter": "Litre", "litre": "Litre", "l": "Litre", "leter": "Litre", "leters": "Litre", "liters": "Litre", "litres": "Litre",
                   "gram": "Gram", "gm": "Gram", "g": "Gram", "kg": "Kg",
                   "mm": "Millimeter", "cm": "Centimeter", "meter": "Meter",
                   "inch": "Inch", "foot": "Foot", "piece": "Nos", "unit": "Nos", "nos": "Nos"}
        data["stock_uom"] = uom_map.get(unit, "Nos")
    else:
        # Simple per-unit: "20 per gram"
        m = re.search(r'(?:price|rate|cost|keemat|py)?\s*(?:is|=|:)?\s*([0-9][0-9,.]*)\s*(?:rs|rupees|pkr|/-)?\s*(?:per|on)\s*(?:[0-9]+\s*)?(gram|gm|g|kg|kilo|kilogram|mm|millimeter|cm|centimeter|meter|inch|foot|feet|piece|unit|nos|ml|millilitre|liter|litre|l)', p, re.I)
        if m:
            data["standard_rate"] = float(m.group(1).replace(",", ""))
            unit = m.group(2).lower()
            uom_map = {"gram": "Gram", "gm": "Gram", "g": "Gram", "kg": "Kg", "kilo": "Kg", "kilogram": "Kg",
                       "mm": "Millimeter", "millimeter": "Millimeter", "cm": "Centimeter", "centimeter": "Centimeter",
                       "meter": "Meter", "inch": "Inch", "foot": "Foot", "feet": "Foot",
                       "piece": "Nos", "unit": "Nos", "nos": "Nos",
                       "ml": "Millilitre", "millilitre": "Millilitre", "liter": "Litre", "litre": "Litre", "l": "Litre"}
            data["stock_uom"] = uom_map.get(unit, "Nos")
        else:
            # Simple price
            m = re.search(r'(?:price|rate|cost|keemat|py)\s*(?:is|=|:|ki hai)\s*([0-9][0-9,.]*)', p, re.I) or \
                re.search(r'(?:price|rate|cost|keemat|py)[:=]?\s*([0-9][0-9,.]*)', p, re.I) or \
                re.search(r'([0-9][0-9,.]*)\s*(?:rs|rupees|pkr|/-)\b', p, re.I)
            if m:
                data["standard_rate"] = float(m.group(1).replace(",", ""))
    # Stock with unit: "4kg", "4 kg", "we have 4kg", "4000 grams", "12 inches", "20 leter"
    # Prefer "stock is X unit" and "we have X unit" patterns, fall back to last qty+unit
    m = re.search(r'(?:stock|qty|quantity|opening|received|milay|mile|we have)\s+(?:is|=|:)?\s*([0-9][0-9,.]*)\s*(kg|kilo|kilogram|gram|gm|g|mm|millimeter|cm|centimeter|meter|inch|foot|feet|liter|litre|leter|leters|liters|litres|l|ml|millilitre)\b', p, re.I)
    if not m:
        # Fall back: get all matches of "quantity unit", prefer the one with liter/gram (larger units)
        matches = list(re.finditer(r'([0-9][0-9,.]*)\s*(kg|kilo|kilogram|gram|gm|g|mm|millimeter|cm|centimeter|meter|inch|foot|feet|literal|liter|litre|leter|leters|liters|litres|l|ml|millilitre|pcs|nos|unit)', p, re.I))
        # Prefer kg/liter/liter over ml/gram for stock
        for match in reversed(matches):
            unit = match.group(2).lower()
            if unit in ('kg', 'kilo', 'kilogram', 'literal', 'liter', 'litre', 'leter', 'leters', 'liters', 'litres'):
                m = match
                break
        else:
            if matches:
                m = matches[-1]  # Take the last one
    if not m:
        # Still no match, try simple search
        m = re.search(r'(?:we have|stock|qty|quantity|opening|received|milay|mile|aa gaya)?\s*([0-9][0-9,.]*)\s*(kg|kilo|kilogram|gram|gm|g|mm|millimeter|cm|centimeter|meter|inch|foot|feet|liter|litre|leter|leters|liters|litres|l|ml|millilitre)\b', p, re.I)
    if m:
        qty = float(m.group(1).replace(",", ""))
        unit = m.group(2).lower()
        uom_map = {
            "kg": "Kg", "kilo": "Kg", "kilogram": "Kg",
            "gram": "Gram", "gm": "Gram", "g": "Gram",
            "mm": "Millimeter", "millimeter": "Millimeter",
            "cm": "Centimeter", "centimeter": "Centimeter",
            "meter": "Meter",
            "inch": "Inch", "foot": "Foot", "feet": "Foot",
            "liter": "Litre", "litre": "Litre", "l": "Litre", "leter": "Litre", "leters": "Litre", "liters": "Litre", "litres": "Litre",
            "ml": "Millilitre", "millilitre": "Millilitre",
        }
        stock_uom = uom_map.get(unit, "Nos")
        # Convert if UOM already set from price
        if "stock_uom" in data and data["stock_uom"] != stock_uom:
            converted = convert_uom(qty, stock_uom, data["stock_uom"])
            if converted is not None:
                data["opening_stock"] = converted
            else:
                data["opening_stock"] = qty
                data["stock_uom"] = stock_uom
        else:
            data["opening_stock"] = qty
            if "stock_uom" not in data:
                data["stock_uom"] = stock_uom
    else:
        # Simple stock
        m = re.search(r'(?:stock|qty|quantity|opening|received|milay|mile)\s*(?:of|is|=|:)?\s*([0-9][0-9,.]*)', p, re.I) or \
            re.search(r'([0-9][0-9,.]*)\s*(?:pcs|nos|units|pieces|dozen)\b', p, re.I)
        if m:
            data["opening_stock"] = float(m.group(1).replace(",", ""))

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
        rate = data.get('standard_rate', 0)
        if isinstance(rate, float) and rate < 1:
            lines.append(f"  Price: {rate:.4f}")
        else:
            lines.append(f"  Price: {rate:,.0f}")
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
    # Item arrival: "resived 20 leter", "recived 100 kg", "aa gaya 50 liter"
    if re.search(r'\b(resived|recived|resiv|reciv|aa gaya|aagya|milay|mile)\b.+\b(kg|liter|litre|leters|liters|gram|gm|ml|mm|meter|inch|leter)\b', pl):
        return "Item"
    # Stock with qty and price: "20 leter price", "100 kg rate"
    if re.search(r'\b\d+\s*(kg|liter|litre|leters|liters|gram|gm|ml|mm|meter|inch|leter)\b.+\b(price|rate|cost|keemat)\b', pl):
        return "Item"
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
