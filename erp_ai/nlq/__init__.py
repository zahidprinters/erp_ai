# ---------------------------------------------------------------------------
# Natural Language Query — robust Q&A with natural responses.
#
# Single responsibility: take raw ERP data and turn it into natural,
# conversational answers. Handles edge cases like zero results, errors,
# and ambiguous queries gracefully.
# ---------------------------------------------------------------------------
import re
from typing import Any, Dict, List, Optional


def format_count_answer(count: int, noun: str, filters_desc: str = "") -> str:
    """Turn a count into a natural sentence."""
    if count == 0:
        base = "There are no %s" % noun
    elif count == 1:
        base = "There is 1 %s" % noun
    else:
        base = "There are {:,} {}".format(count, noun)
    if filters_desc:
        base += " " + filters_desc
    base += "."
    return base


def format_money_answer(amount: float, currency: str = "", label: str = "total") -> str:
    """Turn a money amount into a natural sentence."""
    if not currency:
        try:
            import frappe
            currency = frappe.db.get_single_value("Global Defaults", "default_currency") or ""
        except Exception:
            currency = ""

    from frappe.utils import fmt_money
    try:
        money_str = fmt_money(amount, currency=currency)
    except Exception:
        money_str = "{:,.2f}".format(amount)
        if currency:
            money_str += " " + currency

    if amount == 0:
        return "The %s is zero." % label
    return "The %s is %s." % (label, money_str)


def format_list_answer(items: List[Dict], fields: List[str] = None, label: str = "records") -> str:
    """Turn a list of records into a natural summary."""
    if not items:
        return "No %s found." % label
    count = len(items)
    if count == 1:
        return "Found 1 %s." % label.rstrip("s")
    return "Found %d %s." % (count, label)


def format_stock_answer(item_name: str, qty: float, warehouse: str = "all warehouses") -> str:
    """Turn stock data into a natural answer."""
    if qty == 0:
        return "'%s' is currently out of stock in %s." % (item_name, warehouse)
    if qty < 0:
        return "'%s' has a negative stock of %.0f in %s — please reconcile." % (item_name, qty, warehouse)
    return "'%s' has %.0f units in stock in %s." % (item_name, qty, warehouse)


def format_duplicate_warning(doctype: str, name: str, fields: Dict[str, Any]) -> str:
    """Natural warning about a duplicate record."""
    field_str = ", ".join("%s: %s" % (k, v) for k, v in fields.items() if v)
    return "⚠️ A %s with %s already exists (%s). Use a different name or update the existing record." % (doctype, field_str, name)


def format_missing_fields(missing: List[str], doctype: str) -> str:
    """Natural message about missing required fields."""
    if not missing:
        return ""
    if len(missing) == 1:
        return "To create a %s, I still need: %s." % (doctype, missing[0])
    fields_str = ", ".join(missing[:-1]) + " and " + missing[-1]
    return "To create a %s, I still need: %s." % (doctype, fields_str)


def format_preview(doctype: str, data: Dict[str, Any]) -> str:
    """Natural preview of a document before creation."""
    lines = ["📋 %s Preview:" % doctype]
    for key, value in data.items():
        if value in (None, "", 0, []):
            continue
        label = key.replace("_", " ").title()
        if isinstance(value, list):
            lines.append("  %s:" % label)
            for item in value[:10]:
                if isinstance(item, dict):
                    item_str = ", ".join("%s: %s" % (k, v) for k, v in item.items() if v)
                    lines.append("    - %s" % item_str)
                else:
                    lines.append("    - %s" % str(item))
        else:
            lines.append("  %s: %s" % (label, value))
    lines.append("\nReply 'yes' to create, or tell me what to change.")
    return "\n".join(lines)


def format_error(action: str, reason: str) -> str:
    """Natural error message."""
    return "❌ Could not %s. %s." % (action, reason)


def format_success(action: str, doctype: str, name: str) -> str:
    """Natural success message."""
    return "✅ %s %s '%s' successfully." % (action, doctype, name)


def clarify(question: str, options: List[str] = None) -> str:
    """Ask a clarifying question."""
    msg = question
    if options:
        msg += "\n" + "\n".join("  %d. %s" % (i + 1, opt) for i, opt in enumerate(options))
    return msg
