# ---------------------------------------------------------------------------
# Duplication detection — check if a record already exists before creating.
#
# Single responsibility: given a doctype and field data, check the ERP DB
# for existing matches. Returns info about duplicates found.
# ---------------------------------------------------------------------------
from typing import Any, Dict, List, Optional


def check_duplicate(mcp, doctype: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Check if a record with the given field values already exists.

    Returns None if no duplicate, or a dict with duplicate info:
    {"found": True, "name": "...", "doctype": "...", "fields": {...}}
    """
    from erp_ai.safety import get_duplication_fields
    dup_fields = get_duplication_fields(doctype)
    if not dup_fields:
        return None

    for field in dup_fields:
        value = data.get(field)
        if not value:
            continue
        # Search for existing record
        result = mcp.call_tool("query_doctype", {
            "doctype": doctype,
            "filters": {field: ["like", "%" + str(value) + "%"]},
            "fields": ["name"],
            "limit": 1,
        })
        if result.get("count", 0) > 0:
            name = result["records"][0]["name"]
            # Get full doc for display
            doc = mcp.call_tool("get_document", {"doctype": doctype, "name": name})
            if "error" not in doc:
                return {"found": True, "name": name, "doctype": doctype, "doc": doc}
    return None
