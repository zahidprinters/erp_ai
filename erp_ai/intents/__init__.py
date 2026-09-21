# ---------------------------------------------------------------------------
# Intent detection — map natural language to (doctype, action).
#
# Single responsibility: given a user's prompt, figure out what they want
# to do and to which doctype. No ERP operations, no field collection.
# ---------------------------------------------------------------------------
import re
from typing import List, Optional, Tuple

# Each entry: (compiled_pattern, doctype, action, description)
INTENT_PATTERNS: List[Tuple[re.Pattern, str, str, str]] = [
	# --- Item ---
	(
		re.compile(
			r"\b(add|create|new|banao|banaiye|shuru|register)\b.*\b(item|product|maal|cheez|saman)\b", re.I
		),
		"Item",
		"create",
		"Create Item",
	),
	(
		re.compile(r"\b(item|product)\b.*\b(stock|qty|quantity|kitna|kitne|haye|mila)\b", re.I),
		"Item",
		"report",
		"Check Item Stock",
	),
	# --- Customer ---
	(
		re.compile(r"\b(add|create|new|banao|banaiye|register)\b.*\b(customer|client|grahak)\b", re.I),
		"Customer",
		"create",
		"Create Customer",
	),
	(
		re.compile(r"\b(customer|client|grahak)\b.*\b(list|show|dekho|dikhhao|sab)\b", re.I),
		"Customer",
		"report",
		"List Customers",
	),
	# --- Supplier ---
	(
		re.compile(r"\b(add|create|new|banao|banaiye|register)\b.*\b(supplier|vendor)\b", re.I),
		"Supplier",
		"create",
		"Create Supplier",
	),
	(
		re.compile(r"\b(supplier|vendor)\b.*\b(list|show|dekho|sab)\b", re.I),
		"Supplier",
		"report",
		"List Suppliers",
	),
	# --- Sales Order ---
	(
		re.compile(r"\b(create|add|new|banao|banaiye)\b.*\b(sales order|so|beel order)\b", re.I),
		"Sales Order",
		"create",
		"Create Sales Order",
	),
	# --- Purchase Order ---
	(
		re.compile(r"\b(create|add|new|banao|banaiye)\b.*\b(purchase order|po|khareed order)\b", re.I),
		"Purchase Order",
		"create",
		"Create Purchase Order",
	),
	# --- Sales Invoice ---
	(
		re.compile(
			r"\b(create|add|new|make|banao|banaiye)\b.*\b(sales invoice|bill|beel invoice|sales bill)\b", re.I
		),
		"Sales Invoice",
		"create",
		"Create Sales Invoice",
	),
	(
		re.compile(r"\b(unpaid|outstanding|pending|overdue|bakaya)\b.*\b(invoice|bill)\b", re.I),
		"Sales Invoice",
		"report",
		"Unpaid Invoices",
	),
	# --- Purchase Invoice ---
	(
		re.compile(
			r"\b(create|add|new|banao|banaiye)\b.*\b(purchase invoice|purchase bill|khareed bill|supplier bill)\b",
			re.I,
		),
		"Purchase Invoice",
		"create",
		"Create Purchase Invoice",
	),
	# --- Delivery Note ---
	(
		re.compile(r"\b(create|add|new|banao|banaiye)\b.*\b(delivery note|dispatch|parchi|shipping)\b", re.I),
		"Delivery Note",
		"create",
		"Create Delivery Note",
	),
	# --- Purchase Receipt ---
	(
		re.compile(
			r"\b(receive|arrival|aa gaya|aagya|mil gaya|resiv|reciv|arriv)\b.*\b(shipment|goods|maal|saman|stock)\b",
			re.I,
		),
		"Purchase Receipt",
		"create",
		"Record Goods Receipt",
	),
	(
		re.compile(r"\b(create|add|new|banao|banaiye)\b.*\b(purchase receipt|goods receipt)\b", re.I),
		"Purchase Receipt",
		"create",
		"Create Purchase Receipt",
	),
	# --- Stock Entry ---
	(
		re.compile(r"\b(issue|transfer|jari|dena|bhijwana)\b.*\b(stock|maal|saman|item)\b", re.I),
		"Stock Entry",
		"create",
		"Issue/Transfer Stock",
	),
	(
		re.compile(
			r"\b(create|add|new|banao|banaiye)\b.*\b(stock entry|stock transfer|material receipt|material issue)\b",
			re.I,
		),
		"Stock Entry",
		"create",
		"Create Stock Entry",
	),
	# --- Payment Entry ---
	(
		re.compile(r"\b(receive|collect|jama|wasool)\b.*\b(payment|money|paisa|rupee|amount)\b", re.I),
		"Payment Entry",
		"create",
		"Record Payment Received",
	),
	(
		re.compile(r"\b(pay|bhugtan|pardakht)\b.*\b(supplier|vendor|payment|bill)\b", re.I),
		"Payment Entry",
		"create",
		"Record Payment Made",
	),
	(
		re.compile(r"\b(create|add|new|banao|banaiye)\b.*\b(payment entry|payment|receipt)\b", re.I),
		"Payment Entry",
		"create",
		"Create Payment Entry",
	),
	# --- Journal Entry ---
	(
		re.compile(
			r"\b(create|add|new|banao|banaiye)\b.*\b(journal entry|journal|j\.v\.|adjustment entry)\b", re.I
		),
		"Journal Entry",
		"create",
		"Create Journal Entry",
	),
	# --- Material Request ---
	(
		re.compile(r"\b(create|add|new|banao|banaiye|request)\b.*\b(material request|requirement)\b", re.I),
		"Material Request",
		"create",
		"Create Material Request",
	),
	# --- Quotation ---
	(
		re.compile(r"\b(create|add|new|banao|banaiye|quote)\b.*\b(quotation|quote|rate list)\b", re.I),
		"Quotation",
		"create",
		"Create Quotation",
	),
	# --- Warehouse ---
	(
		re.compile(r"\b(add|create|new|banao|banaiye)\b.*\b(warehouse|store|godam)\b", re.I),
		"Warehouse",
		"create",
		"Create Warehouse",
	),
	# --- Price List ---
	(
		re.compile(r"\b(add|create|new|banao|banaiye)\b.*\b(price list|pricing|daam|keemat list)\b", re.I),
		"Price List",
		"create",
		"Create Price List",
	),
	# --- Lead ---
	(
		re.compile(r"\b(add|create|new|banao|banaiye)\b.*\b(lead|inquiry)\b", re.I),
		"Lead",
		"create",
		"Create Lead",
	),
	# --- Reports ---
	(
		re.compile(r"\b(sales|beed|farokht)\b.*\b(this month|aj month|is mahine|monthly)\b", re.I),
		"Sales Invoice",
		"report",
		"Monthly Sales Report",
	),
	(
		re.compile(r"\b(sales|beed|farokht)\b.*\b(today|aj|daily)\b", re.I),
		"Sales Invoice",
		"report",
		"Daily Sales Report",
	),
	(
		re.compile(r"\b(expense|kharcha|kharch)\b.*\b(this month|is mahine|monthly|today|aj|daily)\b", re.I),
		"Journal Entry",
		"report",
		"Expense Report",
	),
	(
		re.compile(r"\b(stock|inventory|maal|saman)\b.*\b(report|status|total|kitna|kitne)\b", re.I),
		"Item",
		"report",
		"Stock Report",
	),
	(
		re.compile(r"\b(top|best|sabse zyada)\b.*\b(customer|client|grahak)\b", re.I),
		"Sales Invoice",
		"report",
		"Top Customers",
	),
	(
		re.compile(r"\b(top|best|sabse zyada)\b.*\b(item|product|maal|bechna)\b", re.I),
		"Sales Invoice",
		"report",
		"Top Items",
	),
	# --- Print ---
	(
		re.compile(r"\b(print|chhapa|pdf|download)\b.*\b(invoice|bill|receipt|parchi)\b", re.I),
		"Sales Invoice",
		"print",
		"Print Document",
	),
	# --- View ---
	(
		re.compile(r"\b(show|view|details|info|dekho|dikhhao|kya hai|batao)\b", re.I),
		"View",
		"view",
		"View Document",
	),
	# --- Import / Export ---
	(re.compile(r"\b(import|upload|csv|excel|bulk)\b", re.I), "Import", "import", "Import Data"),
	(re.compile(r"\b(export|download|extract|nikalna)\b", re.I), "Export", "export", "Export Data"),
]


def detect_intent(prompt: str) -> Optional[Tuple[str, str]]:
	"""Return (doctype, action) from natural language, or None if unclear."""
	pl = prompt.lower().strip()
	for _pattern, doctype, action, _desc in INTENT_PATTERNS:
		if _pattern.search(pl):
			return (doctype, action)
	return None
