import json

import frappe

from .server import FrappeMCP


@frappe.whitelist()
def mcp_list_tools():
    """List available MCP tools."""
    mcp = FrappeMCP()
    return {"tools": mcp.tools}


@frappe.whitelist()
def mcp_call_tool(name, args=None):
    """Call an MCP tool."""
    mcp = FrappeMCP()
    args = json.loads(args) if isinstance(args, str) else (args or {})
    return mcp.call_tool(name, args)
