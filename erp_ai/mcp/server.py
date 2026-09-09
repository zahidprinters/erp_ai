import json
import frappe

# ---------------------------------------------------------------------------
# Phase 1 security guardrails for the internal FrappeMCP tool layer.
#
# These tools are reachable over HTTP via the whitelisted RPC
# `erp_ai.mcp.mcp_call_tool` (mcp/__init__.py). Without guardrails an
# authenticated caller could create/update/submit ANY DocType with
# ignore_permissions=True (User, Role, Accounting, HR, ...). The rules below
# implement the audit's Phase 1 containment:
#   * only an allowlist of business DocTypes is accepted
#   * security/system DocTypes are always denied
#   * every operation enforces frappe.has_permission() instead of bypassing it
#   * create/update no longer use ignore_permissions=True
# Phase 3: commits removed from low-level tools — callers are responsible
# for committing at the workflow boundary (see draft_workflow.create_document_from_draft).
# ---------------------------------------------------------------------------

ALLOWED_DOCTYPES = {
    "Item", "Item Group", "Customer", "Customer Group", "Supplier", "Supplier Group",
    "Sales Invoice", "Purchase Invoice", "Purchase Order", "Purchase Receipt",
    "Sales Order", "Delivery Note", "Material Request", "Stock Entry",
    "Payment Entry", "Payment Request", "Warehouse", "Territory",
    "Price List", "Currency", "UOM", "UoM", "Account", "Company",
    "Cost Center", "Project", "Tax Rule", "Item Tax Template",
}

# Explicitly denied: never read/create/update/submit these via the assistant.
BLOCKED_DOCTYPES = {
    "User", "Role", "Role Profile", "Custom Role", "Permission",
    "User Permission", "Role Permission", "Access Log", "Scheduled Job",
    "System Console", "Log Setting", "Log Entry", "DocType", "DocField",
    "Custom DocPerm", "Custom Field", "Property Setter",
}


def _validate_doctype(doctype):
    """Return an error message if doctype is not permitted, else None."""
    if not doctype:
        return "doctype is required"
    if doctype in BLOCKED_DOCTYPES:
        return f"DocType '{doctype}' is blocked for assistant operations"
    if doctype not in ALLOWED_DOCTYPES:
        return f"DocType '{doctype}' is not available through the assistant"
    return None


def _require_permission(doctype, action):
    """Return an error message if the current user lacks <action>, else None."""
    try:
        if not frappe.has_permission(doctype, action, user=frappe.session.user):
            return f"Not permitted to {action} {doctype}"
    except Exception:
        return f"Not permitted to {action} {doctype}"
    return None


class FrappeMCP:
    def __init__(self):
        self.tools = self._get_tools()

    def _get_tools(self):
        return [
            {"name": "query_doctype", "description": "Query an allowed ERPNext DocType with filters (read-permission enforced)", "inputSchema": {"type": "object", "properties": {"doctype": {"type": "string"}, "filters": {"type": "object"}, "fields": {"type": "array", "items": {"type": "string"}}, "limit": {"type": "integer"}, "order_by": {"type": "string"}}, "required": ["doctype"]}},
            {"name": "get_document", "description": "Get a single document by name (read-permission enforced)", "inputSchema": {"type": "object", "properties": {"doctype": {"type": "string"}, "name": {"type": "string"}}, "required": ["doctype", "name"]}},
            {"name": "create_document", "description": "Create a new document (create-permission enforced, no ignore_permissions)", "inputSchema": {"type": "object", "properties": {"doctype": {"type": "string"}, "data": {"type": "object"}}, "required": ["doctype", "data"]}},
            {"name": "update_document", "description": "Update a document (write-permission enforced, no ignore_permissions)", "inputSchema": {"type": "object", "properties": {"doctype": {"type": "string"}, "name": {"type": "string"}, "data": {"type": "object"}}, "required": ["doctype", "name", "data"]}},
            {"name": "print_document", "description": "Get print URL for a document (read-permission enforced)", "inputSchema": {"type": "object", "properties": {"doctype": {"type": "string"}, "name": {"type": "string"}, "format": {"type": "string"}}, "required": ["doctype", "name"]}},
            {"name": "search_documents", "description": "Search documents by text (read-permission enforced per DocType)", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "doctype": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}},
            {"name": "get_doctype_meta", "description": "Get doctype fields and structure (read-permission enforced)", "inputSchema": {"type": "object", "properties": {"doctype": {"type": "string"}}, "required": ["doctype"]}},
            {"name": "submit_document", "description": "Submit a draft document (submit-permission enforced)", "inputSchema": {"type": "object", "properties": {"doctype": {"type": "string"}, "name": {"type": "string"}}, "required": ["doctype", "name"]}}
        ]

    def call_tool(self, name, args):
        try:
            method = getattr(self, f"tool_{name}", None)
            if not method:
                return {"error": f"Unknown tool: {name}"}
            return method(**args)
        except Exception as e:
            frappe.log_error("erp_ai.mcp.call_tool", str(e))
            return {"error": str(e)}

    def tool_query_doctype(self, doctype, filters=None, fields=None, limit=20, order_by=None):
        err = _validate_doctype(doctype) or _require_permission(doctype, "read")
        if err:
            return {"error": err}
        records = frappe.get_all(doctype, filters=filters or {}, fields=fields or ["name"], limit_page_length=limit, order_by=order_by or "modified desc")
        return {"doctype": doctype, "count": len(records), "records": records}

    def tool_get_document(self, doctype, name):
        err = _validate_doctype(doctype) or _require_permission(doctype, "read")
        if err:
            return {"error": err}
        if not frappe.db.exists(doctype, name):
            return {"error": f"{doctype} '{name}' not found"}
        return frappe.get_doc(doctype, name).as_dict()

    def tool_create_document(self, doctype, data):
        err = _validate_doctype(doctype) or _require_permission(doctype, "create")
        if err:
            return {"error": err}
        try:
            doc = frappe.get_doc(data)
            doc.insert()  # permissions enforced (was ignore_permissions=True)
            return {"success": True, "doctype": doctype, "name": doc.name, "message": f"{doctype} '{doc.name}' created"}
        except Exception as e:
            frappe.log_error("erp_ai.mcp.create_document", str(e))
            return {"error": f"Failed to create {doctype}: {str(e)}"}

    def tool_update_document(self, doctype, name, data):
        err = _validate_doctype(doctype) or _require_permission(doctype, "write")
        if err:
            return {"error": err}
        if not frappe.db.exists(doctype, name):
            return {"error": f"{doctype} '{name}' not found"}
        try:
            doc = frappe.get_doc(doctype, name)
            doc.update(data)
            doc.save()  # permissions enforced (was ignore_permissions=True)
            return {"success": True, "doctype": doctype, "name": doc.name, "message": f"{doctype} '{doc.name}' updated"}
        except Exception as e:
            frappe.log_error("erp_ai.mcp.update_document", str(e))
            return {"error": str(e)}

    def tool_print_document(self, doctype, name, format="Standard"):
        err = _validate_doctype(doctype) or _require_permission(doctype, "read")
        if err:
            return {"error": err}
        url = f"/api/method/frappe.utils.print_format.download_pdf?doctype={doctype}&name={name}&format={format}&no_letterhead=0&_lang=en"
        return {"doctype": doctype, "name": name, "print_url": url, "message": f"Print URL: {url}"}

    def tool_search_documents(self, query, doctype=None, limit=10):
        results = []
        if doctype:
            err = _validate_doctype(doctype) or _require_permission(doctype, "read")
            if err:
                return {"error": err}
            records = frappe.get_all(doctype, filters={"name": ["like", f"%{query}%"]}, limit_page_length=limit)
            results = [{"doctype": doctype, "name": r["name"]} for r in records]
        else:
            for dt in ["Item", "Customer", "Supplier", "Sales Invoice", "Purchase Invoice"]:
                if not _require_permission(dt, "read"):
                    records = frappe.get_all(dt, filters={"name": ["like", f"%{query}%"]}, limit_page_length=5)
                    results.extend([{"doctype": dt, "name": r["name"]} for r in records])
        return {"query": query, "results": results[:limit]}

    def tool_get_doctype_meta(self, doctype):
        err = _validate_doctype(doctype) or _require_permission(doctype, "read")
        if err:
            return {"error": err}
        meta = frappe.get_meta(doctype)
        fields = [{"fieldname": f.fieldname, "label": f.label, "fieldtype": f.fieldtype, "reqd": f.reqd, "options": f.options} for f in meta.fields if f.fieldtype not in ("Section Break", "Column Break", "HTML", "Text Editor")]
        return {"doctype": doctype, "fields": fields}

    def tool_submit_document(self, doctype, name):
        err = _validate_doctype(doctype) or _require_permission(doctype, "submit")
        if err:
            return {"error": err}
        if not frappe.db.exists(doctype, name):
            return {"error": f"{doctype} '{name}' not found"}
        try:
            doc = frappe.get_doc(doctype, name)
            if doc.docstatus == 0:
                doc.submit()  # enforces submit permission (was unchecked)
                return {"success": True, "message": f"{doctype} '{name}' submitted"}
            return {"message": f"{doctype} '{name}' already submitted"}
        except Exception as e:
            frappe.log_error("erp_ai.mcp.submit_document", str(e))
            return {"error": str(e)}
