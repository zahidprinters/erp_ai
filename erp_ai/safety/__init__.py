# ---------------------------------------------------------------------------
# Safety rules — prevent illegal operations, duplication, and data loss.
#
# Single responsibility: given a prompt or a document being created, decide
# whether it should be blocked. No ERP operations, no field collection.
# ---------------------------------------------------------------------------
import re
from typing import Dict, List, Optional, Tuple

# Duplication check: for each doctype, which fields to check for existing records
DUPLICATION_CHECKS: Dict[str, List[str]] = {
    "Item": ["item_name", "item_code"],
    "Customer": ["customer_name"],
    "Supplier": ["supplier_name"],
    "Warehouse": ["warehouse_name"],
    "Price List": ["price_list_name"],
    "Lead": ["lead_name"],
}

# Illegal operation patterns — never allow these
ILLEGAL_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(delete|mitaao|hatao|remove|mitao)\b.*\b(submitted|jama|final)\b", re.I),
     "Cannot delete submitted documents. Cancel them instead."),
    (re.compile(r"\b(submit|jama)\b.*\b(again|dobara|phir)\b", re.I),
     "Document is already submitted."),
    (re.compile(r"\b(modify|change|edit|badlo)\b.*\b(submitted|jama|final)\b", re.I),
     "Submitted documents cannot be edited. Cancel and create a new one."),
    (re.compile(r"\b(overwrite|replace|purana mitao)\b", re.I),
     "Overwriting existing records is not allowed."),
]


def get_duplication_fields(doctype: str) -> List[str]:
    """Return fields to check for duplicates before creating."""
    return DUPLICATION_CHECKS.get(doctype, [])


def check_illegal_operation(prompt: str) -> Optional[str]:
    """Return error message if the prompt describes an illegal operation, else None."""
    pl = prompt.lower().strip()
    for pattern, error_msg in ILLEGAL_PATTERNS:
        if pattern.search(pl):
            return error_msg
    return None
