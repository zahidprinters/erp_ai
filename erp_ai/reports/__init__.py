# ---------------------------------------------------------------------------
# Report patterns — recognize report requests and build ERP queries.
#
# Single responsibility: given a natural language prompt, detect if it's a
# report request and return the query config. No DB execution.
# ---------------------------------------------------------------------------
import re
from typing import Any, Dict, List, Optional, Tuple

REPORT_PATTERNS: List[Tuple[re.Pattern, str, Dict[str, Any]]] = [
    # Monthly sales
    (
        re.compile(r"\b(sales|beed|farokht)\b.*\b(this month|is mahine|monthly)\b", re.I),
        "monthly_sales",
        {"doctype": "Sales Invoice", "docstatus": 1, "agg": "SUM(grand_total)", "label": "Sales this month"},
    ),
    # Today's sales
    (
        re.compile(r"\b(sales|beed|farokht)\b.*\b(today|aj|daily)\b", re.I),
        "daily_sales",
        {"doctype": "Sales Invoice", "docstatus": 1, "agg": "SUM(grand_total)", "label": "Sales today"},
    ),
    # Monthly expenses
    (
        re.compile(r"\b(expense|kharcha|kharch)\b.*\b(this month|is mahine|monthly)\b", re.I),
        "monthly_expenses",
        {"doctype": "Journal Entry", "docstatus": 1, "agg": "SUM(total_debit)", "label": "Expenses this month"},
    ),
    # Today's expenses
    (
        re.compile(r"\b(expense|kharcha|kharch)\b.*\b(today|aj|daily)\b", re.I),
        "daily_expenses",
        {"doctype": "Journal Entry", "docstatus": 1, "agg": "SUM(total_debit)", "label": "Expenses today"},
    ),
    # Unpaid invoices
    (
        re.compile(r"\b(unpaid|outstanding|pending|overdue|bakaya)\b.*\b(invoice|bill)\b", re.I),
        "unpaid_invoices",
        {"doctype": "Sales Invoice", "docstatus": 1, "outstanding_gt": 0, "agg": "SUM(outstanding_amount)", "label": "Unpaid invoices"},
    ),
    # Stock report
    (
        re.compile(r"\b(stock|inventory|maal|saman)\b.*\b(report|status|total|kitna|kitne)\b", re.I),
        "stock_report",
        {"doctype": "Bin", "agg": "SUM(actual_qty)", "label": "Total stock"},
    ),
    # Top customers
    (
        re.compile(r"\b(top|best|sabse zyada)\b.*\b(customer|client|grahak)\b", re.I),
        "top_customers",
        {"doctype": "Sales Invoice", "docstatus": 1, "group_by": "customer", "order_by": "SUM(grand_total) DESC", "limit": 10},
    ),
    # Top items
    (
        re.compile(r"\b(top|best|sabse zyada)\b.*\b(item|product|maal|bechna)\b", re.I),
        "top_items",
        {"doctype": "Sales Invoice Item", "group_by": "item_code", "order_by": "SUM(amount) DESC", "limit": 10},
    ),
]


def detect_report(prompt: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Return (report_name, config) if prompt is a report request, else None."""
    pl = prompt.lower().strip()
    for pattern, name, config in REPORT_PATTERNS:
        if pattern.search(pl):
            return (name, config)
    return None
