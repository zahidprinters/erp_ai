import json

import frappe

from .server import FrappeMCP

# ---------------------------------------------------------------------------
# RPC-level authorization (audit point 9). The NL/chat flows use FrappeMCP()
# in-process and are already gated by per-tool permission checks plus the
# RBAC policy layer; this gate covers the whitelisted HTTP surface:
#   * any authenticated (non-Guest) user may list tools and call read-only
#     tools — every tool still enforces frappe.has_permission internally,
#   * write tools additionally require a manager role,
#   * financially sensitive DocTypes additionally require System Manager.
# ---------------------------------------------------------------------------
READ_TOOLS = frozenset({
    "query_doctype", "get_document", "search_documents",
    "get_doctype_meta", "print_document", "get_workspace",
})
WRITE_TOOLS = frozenset({"create_document", "update_document", "submit_document"})
MANAGER_ROLES = {
    "System Manager", "Accounts Manager", "Sales Manager",
    "Purchase Manager", "Stock Manager", "Manufacturing Manager", "HR Manager",
}
SENSITIVE_DOCTYPES = {
    "Payment Entry", "Payment Request", "Journal Entry", "Asset", "Asset Repair",
}


def _rpc_denied(name, args):
    """Return an error message if the RPC call is not allowed, else None."""
    if name not in READ_TOOLS and name not in WRITE_TOOLS:
        return f"Unknown tool: {name}"
    user = getattr(frappe.session, "user", None)
    if not user or user == "Guest":
        return "MCP tools require an authenticated user"
    if name in WRITE_TOOLS:
        roles = set(frappe.get_roles(user) or [])
        if not (roles & MANAGER_ROLES):
            return "Only manager roles may create or update documents through the assistant"
        doctype = (args or {}).get("doctype")
        if doctype in SENSITIVE_DOCTYPES and "System Manager" not in roles:
            return f"Only System Managers may operate on {doctype} through the assistant"
    return None


@frappe.whitelist()
def mcp_list_tools():
    """List available MCP tools."""
    err = _rpc_denied("query_doctype", None)  # same authentication requirement
    if err:
        frappe.throw(err, frappe.PermissionError)
    mcp = FrappeMCP()
    return {"tools": mcp.tools}


@frappe.whitelist()
def mcp_call_tool(name, args=None):
    """Call an MCP tool."""
    parsed_args = json.loads(args) if isinstance(args, str) else (args or {})
    err = _rpc_denied(name, parsed_args)
    if err:
        frappe.throw(err, frappe.PermissionError)
    mcp = FrappeMCP()
    return mcp.call_tool(name, parsed_args)
