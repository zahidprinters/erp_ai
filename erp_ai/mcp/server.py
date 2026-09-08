import json
import frappe


class FrappeMCP:
    def __init__(self):
        self.tools = self._get_tools()

    def _get_tools(self):
        return [
            {"name": "query_doctype", "description": "Query any ERPNext doctype with filters", "inputSchema": {"type": "object", "properties": {"doctype": {"type": "string"}, "filters": {"type": "object"}, "fields": {"type": "array", "items": {"type": "string"}}, "limit": {"type": "integer"}, "order_by": {"type": "string"}}, "required": ["doctype"]}},
            {"name": "get_document", "description": "Get a single document by name", "inputSchema": {"type": "object", "properties": {"doctype": {"type": "string"}, "name": {"type": "string"}}, "required": ["doctype", "name"]}},
            {"name": "create_document", "description": "Create a new document", "inputSchema": {"type": "object", "properties": {"doctype": {"type": "string"}, "data": {"type": "object"}}, "required": ["doctype", "data"]}},
            {"name": "update_document", "description": "Update a document", "inputSchema": {"type": "object", "properties": {"doctype": {"type": "string"}, "name": {"type": "string"}, "data": {"type": "object"}}, "required": ["doctype", "name", "data"]}},
            {"name": "print_document", "description": "Get print URL for a document", "inputSchema": {"type": "object", "properties": {"doctype": {"type": "string"}, "name": {"type": "string"}, "format": {"type": "string"}}, "required": ["doctype", "name"]}},
            {"name": "search_documents", "description": "Search documents by text", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "doctype": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}},
            {"name": "get_doctype_meta", "description": "Get doctype fields and structure", "inputSchema": {"type": "object", "properties": {"doctype": {"type": "string"}}, "required": ["doctype"]}},
            {"name": "submit_document", "description": "Submit a draft document", "inputSchema": {"type": "object", "properties": {"doctype": {"type": "string"}, "name": {"type": "string"}}, "required": ["doctype", "name"]}}
        ]

    def call_tool(self, name, args):
        try:
            method = getattr(self, f"tool_{name}", None)
            if not method:
                return {"error": f"Unknown tool: {name}"}
            return method(**args)
        except Exception as e:
            return {"error": str(e)}

    def tool_query_doctype(self, doctype, filters=None, fields=None, limit=20, order_by=None):
        if not frappe.db.exists("DocType", doctype):
            return {"error": f"DocType '{doctype}' not found"}
        records = frappe.get_all(doctype, filters=filters or {}, fields=fields or ["name"], limit_page_length=limit, order_by=order_by or "modified desc")
        return {"doctype": doctype, "count": len(records), "records": records}

    def tool_get_document(self, doctype, name):
        if not frappe.db.exists(doctype, name):
            return {"error": f"{doctype} '{name}' not found"}
        return frappe.get_doc(doctype, name).as_dict()

    def tool_create_document(self, doctype, data):
        try:
            doc = frappe.get_doc(data)
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            return {"success": True, "doctype": doctype, "name": doc.name, "message": f"{doctype} '{doc.name}' created"}
        except Exception as e:
            return {"error": f"Failed to create {doctype}: {str(e)}"}

    def tool_update_document(self, doctype, name, data):
        if not frappe.db.exists(doctype, name):
            return {"error": f"{doctype} '{name}' not found"}
        try:
            doc = frappe.get_doc(doctype, name)
            doc.update(data)
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            return {"success": True, "doctype": doctype, "name": doc.name, "message": f"{doctype} '{doc.name}' updated"}
        except Exception as e:
            return {"error": str(e)}

    def tool_print_document(self, doctype, name, format="Standard"):
        url = f"/api/method/frappe.utils.print_format.download_pdf?doctype={doctype}&name={name}&format={format}&no_letterhead=0&_lang=en"
        return {"doctype": doctype, "name": name, "print_url": url, "message": f"Print URL: {url}"}

    def tool_search_documents(self, query, doctype=None, limit=10):
        results = []
        if doctype:
            records = frappe.get_all(doctype, filters={"name": ["like", f"%{query}%"]}, limit_page_length=limit)
            results = [{"doctype": doctype, "name": r["name"]} for r in records]
        else:
            for dt in ["Item", "Customer", "Supplier", "Sales Invoice", "Purchase Invoice"]:
                records = frappe.get_all(dt, filters={"name": ["like", f"%{query}%"]}, limit_page_length=5)
                results.extend([{"doctype": dt, "name": r["name"]} for r in records])
        return {"query": query, "results": results[:limit]}

    def tool_get_doctype_meta(self, doctype):
        if not frappe.db.exists("DocType", doctype):
            return {"error": f"DocType '{doctype}' not found"}
        meta = frappe.get_meta(doctype)
        fields = [{"fieldname": f.fieldname, "label": f.label, "fieldtype": f.fieldtype, "reqd": f.reqd, "options": f.options} for f in meta.fields if f.fieldtype not in ("Section Break", "Column Break", "HTML", "Text Editor")]
        return {"doctype": doctype, "fields": fields}

    def tool_submit_document(self, doctype, name):
        if not frappe.db.exists(doctype, name):
            return {"error": f"{doctype} '{name}' not found"}
        try:
            doc = frappe.get_doc(doctype, name)
            if doc.docstatus == 0:
                doc.submit()
                frappe.db.commit()
                return {"success": True, "message": f"{doctype} '{name}' submitted"}
            return {"message": f"{doctype} '{name}' already submitted"}
        except Exception as e:
            return {"error": str(e)}
