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
    # Stock / Items
    "Item", "Item Group", "Stock Entry", "Stock Reconciliation",
    "Warehouse", "Batch", "Serial No", "Price List",
    "UOM", "UoM",
    # Selling
    "Customer", "Customer Group", "Sales Order", "Delivery Note",
    "Sales Invoice", "Quotation", "Lead", "Opportunity",
    # Buying
    "Supplier", "Supplier Group", "Purchase Order", "Purchase Receipt",
    "Purchase Invoice", "Material Request",
    "Request for Quotation", "Supplier Quotation",
    # Accounting
    "Payment Entry", "Payment Request", "Journal Entry",
    "Account", "Company", "Cost Center", "Tax Rule", "Item Tax Template",
    "Currency", "Territory",
    # Manufacturing
    "BOM", "Work Order", "Job Card", "Production Plan",
    # Quality
    "Quality Inspection",
    # Maintenance / Assets
    "Asset", "Asset Category", "Asset Maintenance", "Asset Repair", "Asset Movement",
    # HR
    "Employee", "Leave Application", "Attendance", "Payroll Entry",
    "Salary Structure", "Expense Claim",
    # Projects
    "Project", "Task", "Timesheet",
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
    if not doctype or not action:
        return "doctype and action are required"
    allowed_actions = ("read", "write", "create", "submit", "cancel", "amend")
    if action not in allowed_actions:
        return f"Unsupported action: {action}"
    try:
        if not frappe.has_permission(doctype, action, user=frappe.session.user):
            return f"Not permitted to {action} {doctype}"
    except Exception:
        return f"Not permitted to {action} {doctype}"
    return None


# Keys the model/assistant must never be able to write directly. The server
# decides the DocType from the tool argument and the framework manages
# identity, timestamps, status, docstatus and parent links.
_BLOCKED_PAYLOAD_KEYS = frozenset({
    "doctype", "name", "creation", "modified", "modified_by", "idx",
    "docstatus", "owner", "parent", "parentfield", "parenttype",
    "old_parent", "amended_from",
})


def _sanitize_write_payload(data):
    """Return a copy of ``data`` containing only safe, writable field values.

    Payloads from the LLM/approval flow may contain framework-managed keys
    (``owner``, timestamps, ``docstatus``, parent links, the DocType itself)
    that must never be applied verbatim. Identity and DocType are decided by
    the server, never by the payload. ``None`` values are dropped so a
    malformed payload cannot silently blank existing fields on update.
    """
    if not isinstance(data, dict):
        return {}
    return {
        k: v
        for k, v in data.items()
        if k not in _BLOCKED_PAYLOAD_KEYS and not k.startswith("_") and v is not None
    }


def _validate_required_fields(doctype, data):
    """Return an error message if data is missing live-mandatory fields, else None.

    Checks frappe.get_meta() directly so Custom Fields added by other apps
    (e.g. tax integrations making NTN/CNIC mandatory) are caught with a clear,
    listable message instead of a cryptic database failure at insert time.
    Conditional requirements (depends_on / mandatory_depends_on) are skipped.
    """
    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return None  # metadata unavailable — let insert() report the problem
    layout_types = {"Section Break", "Column Break", "Tab Break", "Fold",
                    "HTML", "Heading", "Image", "Button"}
    missing = []
    for df in meta.fields:
        if not getattr(df, "reqd", 0) or df.fieldtype in layout_types:
            continue
        if getattr(df, "depends_on", None) or getattr(df, "mandatory_depends_on", None):
            continue  # conditionally required, evaluated on save
        if df.fieldname == "naming_series":
            continue  # auto-naming covers it when omitted
        val = data.get(df.fieldname) if isinstance(data, dict) else None
        if val in (None, "", []) and not getattr(df, "default", None):
            missing.append(df.label or df.fieldname)
    if missing:
        return "Missing required fields: " + ", ".join(missing)
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
        # Strict query guardrails
        limit = min(int(limit or 20), 100)
        allowed_fields = {f.fieldname for f in frappe.get_meta(doctype).fields}
        if fields:
            fields = [f for f in fields if f in allowed_fields][:10]
        else:
            fields = ["name"]
        allowed_order_fields = {"modified", "creation", "name", "idx"}
        if order_by:
            order_field = order_by.split()[0].lower()
            if order_field not in allowed_order_fields:
                order_by = "modified desc"
        else:
            order_by = "modified desc"
        if filters:
            filters = {k: v for k, v in filters.items() if k in allowed_fields}
        records = frappe.get_all(doctype, filters=filters or {}, fields=fields, limit_page_length=limit, order_by=order_by)
        return {"doctype": doctype, "count": len(records), "records": records}

    def tool_get_document(self, doctype, name):
        err = _validate_doctype(doctype) or _require_permission(doctype, "read")
        if err:
            return {"error": err}
        if not frappe.db.exists(doctype, name):
            return {"error": f"{doctype} '{name}' not found"}
        return frappe.get_doc(doctype, name).as_dict()

    def tool_create_document(self, doctype, data, idempotency_key=None):
        err = _validate_doctype(doctype) or _require_permission(doctype, "create")
        if err:
            return {"error": err}
        # Live-metadata validation: catch fields made mandatory by Custom Fields
        # (e.g. tax app's NTN/CNIC) with a clear message, before insert() fails.
        missing_err = _validate_required_fields(doctype, data)
        if missing_err:
            return {"error": missing_err}
        # Idempotency: retry-safe creation. A repeated request with the same key
        # returns the earlier result instead of creating a duplicate document.
        if idempotency_key:
            from erp_ai.idempotency import check_idempotency, claim_idempotency
            prev = check_idempotency(idempotency_key, user=frappe.session.user)
            if prev:
                if prev.get("status") == "forbidden":
                    return {"error": "This idempotency key belongs to another user"}
                if prev.get("docname"):
                    return {"success": True, "doctype": prev.get("doctype") or doctype,
                            "name": prev.get("docname"), "duplicate": True,
                            "message": f"Already created {prev.get('doctype')} '{prev.get('docname')}'"}
                return {"error": "Operation with this idempotency key is already pending"}
            claim = claim_idempotency(
                key=idempotency_key, session=frappe.session.sid, user=frappe.session.user,
                action="create", target_doctype=doctype, proposed_data=data or {})
            if claim.get("status") in ("duplicate", "forbidden"):
                return {"error": "Duplicate idempotency key: %s" % claim.get("action_id")}
        data = _sanitize_write_payload(data)
        if not data:
            return {"error": "No writable fields provided"}
        data = dict(data)
        data["doctype"] = doctype
        try:
            doc = frappe.get_doc(data)
            doc.insert()  # permissions enforced (was ignore_permissions=True)
            if idempotency_key:
                from erp_ai.audit import record_completion
                try:
                    record_completion(claim.get("action_id"), doc.name,
                                      {"doctype": doctype, "name": doc.name})
                except Exception:
                    pass
            return {"success": True, "doctype": doctype, "name": doc.name, "message": f"{doctype} '{doc.name}' created"}
        except Exception as e:
            if idempotency_key:
                from erp_ai.audit import record_failure
                try:
                    record_failure(claim.get("action_id"), str(e))
                except Exception:
                    pass
            frappe.log_error("erp_ai.mcp.create_document", str(e))
            return {"error": f"Failed to create {doctype}: {str(e)}"}

    def tool_update_document(self, doctype, name, data):
        err = _validate_doctype(doctype) or _require_permission(doctype, "write")
        if err:
            return {"error": err}
        if not frappe.db.exists(doctype, name):
            return {"error": f"{doctype} '{name}' not found"}
        data = _sanitize_write_payload(data)
        if not data:
            return {"error": "No writable fields provided"}
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
        limit = min(int(limit or 10), 50)
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
