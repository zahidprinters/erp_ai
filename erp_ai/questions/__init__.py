# ---------------------------------------------------------------------------
# Field questions & hints — what to ask the user for each field.
#
# Single responsibility: given a doctype and field name, return the natural
# language question to ask, and an optional format hint.
# ---------------------------------------------------------------------------
from typing import Optional

FIELD_QUESTIONS = {
    # Item
    "item_name": "What is the name of this item?",
    "item_group": "Which group? (e.g. Products, Raw Material, Services)",
    "standard_rate": "What is the standard selling price / rate?",
    "stock_uom": "What unit? (e.g. Nos, Kg, Litre, Meter, Box)",
    "opening_stock": "Any opening stock? If yes, how many?",
    "item_code": "Item code / SKU? (or press Enter to auto-generate)",
    "description": "Any description? (optional)",
    # Customer / Supplier
    "customer_name": "What is the customer name?",
    "supplier_name": "What is the supplier name?",
    "customer_group": "Which customer group? (e.g. Commercial, Retail, Wholesale)",
    "supplier_group": "Which supplier group?",
    "territory": "Which territory? (e.g. Pakistan, Karachi, Lahore)",
    "mobile_no": "Mobile number?",
    "email": "Email address?",
    "customer_type": "Company or Individual?",
    "supplier_type": "Company or Individual?",
    "tax_id": "Tax / NTN number? (optional)",
    "address": "Address? (optional)",
    # Sales / Purchase documents
    "customer": "Which customer is this for?",
    "supplier": "Which supplier is this from?",
    "delivery_date": "When should this be delivered?",
    "due_date": "Payment due date?",
    "items": "Which items? (one per line: name, qty, rate)",
    "company": "Which company? (or Enter for default)",
    "taxes_and_charges": "Tax template? (or Enter for none)",
    "payment_terms_template": "Payment terms? (optional)",
    "remarks": "Any remarks? (optional)",
    "po_no": "Customer PO number? (optional)",
    "bill_no": "Supplier bill number? (optional)",
    "bill_date": "Supplier bill date? (optional)",
    "discount_percent": "Discount %? (or Enter for 0)",
    "update_stock": "Update stock/inventory? (yes/no)",
    # Stock Entry
    "stock_entry_type": "Type? (Material Receipt / Issue / Transfer / Manufacture)",
    "from_warehouse": "Source warehouse?",
    "to_warehouse": "Target warehouse?",
    "vehicle_no": "Vehicle number? (optional)",
    # Payment Entry
    "payment_type": "Receive (money in) or Pay (money out)?",
    "party_type": "Party type? (Customer, Supplier, Employee)",
    "party": "Party name?",
    "paid_amount": "Payment amount?",
    "reference_no": "Cheque / Reference number? (optional)",
    "reference_date": "Reference date? (optional)",
    # Journal Entry
    "accounts": "Account entries? (one per line: account, debit, credit)",
    "cheque_no": "Cheque / Reference number? (optional)",
    "cheque_date": "Cheque date? (optional)",
    "voucher_type": "Voucher type? (Journal Entry / Bank Entry / Cash Entry)",
    # Material Request
    "material_request_type": "Type? (Purchase / Transfer / Issue)",
    # Quotation
    "quotation_to": "Quotation to: Customer or Lead?",
    "party_name": "Customer or Lead name?",
    "valid_till": "Valid until? (optional)",
    # Warehouse
    "warehouse_name": "Warehouse name?",
    "parent_warehouse": "Parent warehouse? (optional, blank for top-level)",
    # Price List
    "price_list_name": "Price list name?",
    "currency": "Currency? (e.g. PKR, USD)",
    "selling": "Is selling price list? (yes/no)",
    "buying": "Is buying price list? (yes/no)",
    # Lead
    "lead_name": "Lead name?",
    "company_name": "Company name? (optional)",
    "source": "Source? (e.g. Website, Cold Call, Exhibition)",
    "status": "Status? (Lead / Open / Interested / Opportunity)",
}

FIELD_HINTS = {
    "items": "Format: item name, quantity, rate (one per line)\nExample:\nPump Springs, 500, 150\nSteel Rod, 100, 250",
    "accounts": "Format: account name, debit, credit (one per line)\nExample:\nCash - SPI, 50000, 0\nSales - SPI, 0, 50000",
    "qty": "Enter a number (e.g. 500)",
    "rate": "Rate per unit (e.g. 150 or 250.50)",
    "amount": "Enter the amount (e.g. 50000)",
    "paid_amount": "Payment amount (e.g. 50000)",
    "discount_percent": "Discount % (e.g. 5 for 5%)",
    "standard_rate": "Price per unit (e.g. 150)",
    "opening_stock": "Opening quantity (e.g. 1000)",
    "delivery_date": "Date (e.g. 2026-09-15 or 'next Monday')",
    "due_date": "Date (e.g. 2026-10-15 or '30 days')",
    "mobile_no": "Mobile (e.g. 0300-1234567)",
    "email": "Email (e.g. contact@company.com)",
}


def get_question(doctype: str, field: str) -> str:
    """Return the natural language question for a field."""
    q = FIELD_QUESTIONS.get(field)
    if q:
        return q
    # Fall back to a generic label
    from erp_ai.schema import get_label
    label = get_label(doctype, field)
    return "Please provide: %s" % label


def get_hint(field: str) -> Optional[str]:
    """Return the format hint for a field, if any."""
    return FIELD_HINTS.get(field)
