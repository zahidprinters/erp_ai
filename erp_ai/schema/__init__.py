# ---------------------------------------------------------------------------
# DOCTYPE SCHEMAS — the single registry of what the AI knows how to create.
#
# Each entry says: for this doctype, which fields are required, which are
# optional, what defaults to apply, and what the human label is for each field.
# ---------------------------------------------------------------------------
from typing import Any, Dict, List, Optional

DOCTYPE_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "Item": {
        "required": ["item_name"],
        "optional": ["item_group", "standard_rate", "stock_uom", "opening_stock", "item_code"],
        "defaults": {"item_group": "Products", "stock_uom": "Nos", "standard_rate": 0, "is_stock_item": 1},
        "labels": {"item_name": "Item Name", "item_group": "Item Group", "standard_rate": "Price / Rate", "stock_uom": "Unit (UOM)", "opening_stock": "Opening Stock Qty", "item_code": "Item Code / SKU"},
    },
    "Customer": {
        "required": ["customer_name"],
        "optional": ["customer_group", "territory", "mobile_no", "email"],
        "defaults": {"customer_group": "Commercial", "territory": "Pakistan"},
        "labels": {"customer_name": "Customer Name", "customer_group": "Customer Group", "territory": "Territory", "mobile_no": "Mobile Number", "email": "Email Address"},
    },
    "Supplier": {
        "required": ["supplier_name"],
        "optional": ["supplier_group", "mobile_no", "email"],
        "defaults": {"supplier_group": "All Supplier Groups"},
        "labels": {"supplier_name": "Supplier Name", "supplier_group": "Supplier Group", "mobile_no": "Mobile Number", "email": "Email Address"},
    },
    "Sales Invoice": {
        "required": ["customer", "items"],
        "optional": ["due_date", "discount_percent", "taxes_and_charges", "remarks", "update_stock"],
        "defaults": {"update_stock": 1},
        "labels": {"customer": "Customer", "items": "Items", "due_date": "Due Date", "discount_percent": "Discount %", "taxes_and_charges": "Tax Template", "remarks": "Remarks", "update_stock": "Update Stock"},
        "child_table": {"fieldname": "items", "required": ["item_code", "qty", "rate"], "optional": ["warehouse"], "labels": {"item_code": "Item", "qty": "Quantity", "rate": "Rate", "warehouse": "Warehouse"}},
    },
    "Purchase Invoice": {
        "required": ["supplier", "items"],
        "optional": ["due_date", "discount_percent", "taxes_and_charges", "remarks", "update_stock", "bill_no", "bill_date"],
        "defaults": {"update_stock": 1},
        "labels": {"supplier": "Supplier", "items": "Items", "due_date": "Due Date", "discount_percent": "Discount %", "taxes_and_charges": "Tax Template", "remarks": "Remarks", "bill_no": "Bill No", "bill_date": "Bill Date"},
        "child_table": {"fieldname": "items", "required": ["item_code", "qty", "rate"], "optional": ["warehouse"], "labels": {"item_code": "Item", "qty": "Quantity", "rate": "Rate", "warehouse": "Warehouse"}},
    },
    "Sales Order": {
        "required": ["customer", "delivery_date", "items"],
        "optional": ["company", "taxes_and_charges", "remarks"],
        "defaults": {},
        "labels": {"customer": "Customer", "delivery_date": "Delivery Date", "items": "Items", "company": "Company", "taxes_and_charges": "Tax Template", "remarks": "Remarks"},
        "child_table": {"fieldname": "items", "required": ["item_code", "qty"], "optional": ["rate", "warehouse"], "labels": {"item_code": "Item", "qty": "Quantity", "rate": "Rate"}},
    },
    "Purchase Order": {
        "required": ["supplier", "items"],
        "optional": ["company", "taxes_and_charges", "remarks", "schedule_date"],
        "defaults": {},
        "labels": {"supplier": "Supplier", "items": "Items", "company": "Company", "taxes_and_charges": "Tax Template", "remarks": "Remarks", "schedule_date": "Expected Delivery"},
        "child_table": {"fieldname": "items", "required": ["item_code", "qty", "rate"], "optional": ["warehouse"], "labels": {"item_code": "Item", "qty": "Quantity", "rate": "Rate"}},
    },
    "Delivery Note": {
        "required": ["customer", "items"],
        "optional": ["company", "taxes_and_charges", "remarks", "vehicle_no"],
        "defaults": {},
        "labels": {"customer": "Customer", "items": "Items", "company": "Company", "taxes_and_charges": "Tax Template", "remarks": "Remarks", "vehicle_no": "Vehicle No"},
        "child_table": {"fieldname": "items", "required": ["item_code", "qty", "warehouse"], "optional": ["rate"], "labels": {"item_code": "Item", "qty": "Quantity", "warehouse": "Source Warehouse", "rate": "Rate"}},
    },
    "Purchase Receipt": {
        "required": ["supplier", "items"],
        "optional": ["company", "taxes_and_charges", "remarks", "vehicle_no", "bill_no"],
        "defaults": {},
        "labels": {"supplier": "Supplier", "items": "Items", "company": "Company", "taxes_and_charges": "Tax Template", "remarks": "Remarks", "vehicle_no": "Vehicle No", "bill_no": "Bill No"},
        "child_table": {"fieldname": "items", "required": ["item_code", "qty", "rate", "warehouse"], "optional": [], "labels": {"item_code": "Item", "qty": "Quantity", "rate": "Rate", "warehouse": "Target Warehouse"}},
    },
    "Stock Entry": {
        "required": ["stock_entry_type", "items"],
        "optional": ["company", "remarks", "from_warehouse", "to_warehouse"],
        "defaults": {},
        "labels": {"stock_entry_type": "Type (Receipt/Issue/Transfer/Manufacture)", "items": "Items", "company": "Company", "remarks": "Remarks", "from_warehouse": "Source Warehouse", "to_warehouse": "Target Warehouse"},
        "child_table": {"fieldname": "items", "required": ["item_code", "qty"], "optional": ["basic_rate", "s_warehouse", "t_warehouse"], "labels": {"item_code": "Item", "qty": "Quantity", "basic_rate": "Rate", "s_warehouse": "Source WH", "t_warehouse": "Target WH"}},
    },
    "Payment Entry": {
        "required": ["payment_type", "party_type", "party", "paid_amount"],
        "optional": ["reference_no", "reference_date", "remarks", "company"],
        "defaults": {},
        "labels": {"payment_type": "Type (Receive/Pay)", "party_type": "Party Type (Customer/Supplier)", "party": "Party Name", "paid_amount": "Amount", "reference_no": "Ref / Cheque No", "reference_date": "Ref Date", "remarks": "Remarks", "company": "Company"},
    },
    "Journal Entry": {
        "required": ["accounts"],
        "optional": ["company", "posting_date", "cheque_no", "cheque_date", "remarks"],
        "defaults": {"voucher_type": "Journal Entry"},
        "labels": {"accounts": "Account Entries", "company": "Company", "posting_date": "Posting Date", "cheque_no": "Cheque No", "cheque_date": "Cheque Date", "remarks": "Remarks"},
        "child_table": {"fieldname": "accounts", "required": ["account", "debit_in_account_currency", "credit_in_account_currency"], "optional": ["party_type", "party"], "labels": {"account": "Account", "debit_in_account_currency": "Debit", "credit_in_account_currency": "Credit"}},
    },
    "Material Request": {
        "required": ["material_request_type", "items"],
        "optional": ["company", "remarks"],
        "defaults": {"material_request_type": "Material Transfer"},
        "labels": {"material_request_type": "Type (Purchase/Transfer/Issue)", "items": "Items", "company": "Company", "remarks": "Remarks"},
        "child_table": {"fieldname": "items", "required": ["item_code", "qty"], "optional": ["warehouse"], "labels": {"item_code": "Item", "qty": "Quantity", "warehouse": "Target Warehouse"}},
    },
    "Quotation": {
        "required": ["quotation_to", "party_name", "items"],
        "optional": ["company", "valid_till", "taxes_and_charges"],
        "defaults": {"quotation_to": "Customer"},
        "labels": {"quotation_to": "To (Customer/Lead)", "party_name": "Party Name", "items": "Items", "company": "Company", "valid_till": "Valid Until", "taxes_and_charges": "Tax Template"},
        "child_table": {"fieldname": "items", "required": ["item_code", "qty"], "optional": ["rate"], "labels": {"item_code": "Item", "qty": "Quantity", "rate": "Rate"}},
    },
    "Warehouse": {
        "required": ["warehouse_name"],
        "optional": ["parent_warehouse", "company"],
        "defaults": {},
        "labels": {"warehouse_name": "Warehouse Name", "parent_warehouse": "Parent Warehouse", "company": "Company"},
    },
    "Price List": {
        "required": ["price_list_name"],
        "optional": ["currency", "selling", "buying"],
        "defaults": {"currency": "PKR"},
        "labels": {"price_list_name": "Price List Name", "currency": "Currency", "selling": "Is Selling", "buying": "Is Buying"},
    },
    "Lead": {
        "required": ["lead_name"],
        "optional": ["company_name", "email_id", "mobile_no", "source", "status"],
        "defaults": {"status": "Lead"},
        "labels": {"lead_name": "Lead Name", "company_name": "Company Name", "email_id": "Email", "mobile_no": "Mobile", "source": "Source", "status": "Status"},
    },
    # --- Manufacturing ---
    "BOM": {
        "required": ["item", "items"],
        "optional": ["company", "routing", "with_operations"],
        "defaults": {"with_operations": 1},
        "labels": {"item": "Finished Good Item", "items": "Raw Materials", "company": "Company", "routing": "Routing", "with_operations": "With Operations"},
        "child_table": {"fieldname": "items", "required": ["item_code", "qty"], "optional": ["rate", "uom", "operation"], "labels": {"item_code": "Raw Material", "qty": "Qty per Unit", "rate": "Rate", "uom": "UOM", "operation": "Operation"}},
    },
    "Work Order": {
        "required": ["production_item", "bom_no", "qty"],
        "optional": ["company", "fg_warehouse", "wip_warehouse", "planned_start_date"],
        "defaults": {"wip_warehouse": "Work In Progress - SPI", "fg_warehouse": "Finished Goods - SPI"},
        "labels": {"production_item": "Item to Manufacture", "bom_no": "BOM No", "qty": "Qty to Produce", "company": "Company", "fg_warehouse": "Target Warehouse", "wip_warehouse": "WIP Warehouse", "planned_start_date": "Planned Start"},
    },
    "Job Card": {
        "required": ["work_order", "operation", "for_quantity"],
        "optional": ["employee", "workstation", "time_in_mins", "completed_qty"],
        "defaults": {},
        "labels": {"work_order": "Work Order", "operation": "Operation", "for_quantity": "Qty", "employee": "Employee", "workstation": "Workstation", "time_in_mins": "Time (mins)", "completed_qty": "Completed Qty"},
    },
    "Production Plan": {
        "required": ["company", "po_items"],
        "optional": ["get_items_from", "posting_date", "project", "sales_orders", "material_requests", "for_warehouse", "sub_assembly_warehouse", "status"],
        "defaults": {"get_items_from": "Sales Order"},
        "labels": {"po_items": "Items to Plan", "company": "Company", "get_items_from": "Sales Order/Material Request", "posting_date": "Date", "project": "Project", "for_warehouse": "For Warehouse", "status": "Draft/Submitted"},
        "child_table": {"fieldname": "po_items", "required": ["item_code", "planned_qty"], "optional": ["warehouse", "bom_no", "sales_order"], "labels": {"item_code": "Item", "planned_qty": "Planned Qty", "warehouse": "Warehouse", "bom_no": "BOM", "sales_order": "Sales Order"}},
    },
    # --- Quality ---
    "Quality Inspection": {
        "required": ["inspection_type", "reference_type", "reference_name", "item_code"],
        "optional": ["sample_size", "status", "remarks", "inspected_by"],
        "defaults": {"inspection_type": "Incoming", "status": "Accepted"},
        "labels": {"inspection_type": "Incoming/Outgoing/In Process", "reference_type": "DocType", "reference_name": "Doc Name", "item_code": "Item", "sample_size": "Sample Size", "status": "Result", "remarks": "Remarks", "inspected_by": "Inspected By"},
    },
    # NOTE: a generic "Nonconformance Report" DocType is not part of stock
    # ERPNext v15 — quality teams use Quality Inspection + custom doctypes.
    # Removed from the registry after live-metadata verification (2026-09).
    # --- Maintenance & Assets ---
    "Asset": {
        "required": ["asset_name", "item_code", "asset_category", "location"],
        "optional": ["gross_purchase_amount", "purchase_date", "is_existing_asset"],
        "defaults": {"is_existing_asset": 1},
        "labels": {"asset_name": "Asset Name", "item_code": "Item Code", "asset_category": "Category", "location": "Location", "gross_purchase_amount": "Purchase Amount", "purchase_date": "Purchase Date", "is_existing_asset": "Is Existing"},
    },
    "Asset Maintenance": {
        "required": ["asset_name", "asset_maintenance_tasks"],
        "optional": ["company", "maintenance_team", "maintenance_manager"],
        "defaults": {},
        "labels": {"asset_name": "Asset", "asset_maintenance_tasks": "Tasks", "maintenance_team": "Team", "maintenance_manager": "Manager", "company": "Company"},
        "child_table": {"fieldname": "asset_maintenance_tasks", "required": ["maintenance_task", "maintenance_type", "next_due_date"], "optional": ["periodicity", "assign_to", "start_date", "end_date"], "labels": {"maintenance_task": "Task", "maintenance_type": "Preventive/Corrective", "next_due_date": "Due Date", "periodicity": "Monthly/Quarterly/Yearly", "assign_to": "Technician"}},
    },
    "Asset Repair": {
        "required": ["asset", "failure_date", "repair_status"],
        "optional": ["company", "completion_date", "repair_cost", "capitalize_repair_cost", "stock_consumption", "project", "cost_center"],
        "defaults": {},
        "labels": {"asset": "Asset", "failure_date": "Failure Date", "repair_status": "Completed/Pending", "completion_date": "Completion Date", "repair_cost": "Repair Cost", "capitalize_repair_cost": "Capitalize Cost", "stock_consumption": "Spare Parts Used", "project": "Project", "cost_center": "Cost Center"},
    },
    "Asset Movement": {
        "required": ["purpose", "assets"],
        "optional": ["company", "transaction_date", "reference_doctype"],
        "defaults": {"purpose": "Transfer"},
        "labels": {"purpose": "Issue/Receipt/Transfer", "assets": "Assets", "company": "Company", "transaction_date": "Date", "reference_doctype": "Reference"},
        "child_table": {"fieldname": "assets", "required": ["asset"], "optional": ["source_location", "target_location", "from_employee", "to_employee"], "labels": {"asset": "Asset", "source_location": "From Location", "target_location": "To Location", "from_employee": "From Employee", "to_employee": "To Employee"}},
    },
    # --- HR ---
    "Employee": {
        "required": ["first_name", "date_of_birth", "date_of_joining", "gender", "company"],
        "optional": ["last_name", "employee_number", "department", "designation", "branch", "cell_number"],
        "defaults": {},
        "labels": {"first_name": "First Name", "last_name": "Last Name", "date_of_birth": "Birth Date", "date_of_joining": "Joining Date", "gender": "Gender", "company": "Company", "employee_number": "Employee ID", "department": "Department", "designation": "Designation", "branch": "Branch", "cell_number": "Mobile"},
    },
    "Leave Application": {
        "required": ["employee", "leave_type", "from_date", "to_date"],
        "optional": ["half_day", "reason", "status"],
        "defaults": {"status": "Open"},
        "labels": {"employee": "Employee", "leave_type": "Casual/Sick/Earned", "from_date": "From", "to_date": "To", "half_day": "Half Day", "reason": "Reason", "status": "Open/Approved/Rejected"},
    },
    "Expense Claim": {
        "required": ["employee", "expenses"],
        "optional": ["company", "approval_status"],
        "defaults": {"approval_status": "Draft"},
        "labels": {"employee": "Employee", "expenses": "Expenses", "company": "Company", "approval_status": "Status"},
        "child_table": {"fieldname": "expenses", "required": ["expense_date", "amount", "expense_type"], "optional": ["description", "sanctioned_amount"], "labels": {"expense_date": "Date", "amount": "Amount", "expense_type": "Type", "description": "Description", "sanctioned_amount": "Sanctioned"}},
    },
    "Project": {
        "required": ["project_name"],
        "optional": ["company", "status", "expected_start_date", "expected_end_date"],
        "defaults": {"status": "Open"},
        "labels": {"project_name": "Project Name", "company": "Company", "status": "Open/Completed", "expected_start_date": "Start", "expected_end_date": "End"},
    },
    "Task": {
        "required": ["subject"],
        "optional": ["project", "status", "priority", "description", "expected_start_date", "expected_end_date"],
        "defaults": {"status": "Open", "priority": "Medium"},
        "labels": {"subject": "Subject", "project": "Project", "status": "Open/Completed", "priority": "Low/Medium/High", "description": "Description", "expected_start_date": "Start", "expected_end_date": "End"},
    },
    "Request for Quotation": {
        "required": ["company", "items"],
        "optional": ["suppliers", "message_for_supplier"],
        "defaults": {},
        "labels": {"company": "Company", "items": "Items", "suppliers": "Suppliers", "message_for_supplier": "Message"},
        "child_table": {"fieldname": "items", "required": ["item_code", "qty"], "optional": ["warehouse", "schedule_date"], "labels": {"item_code": "Item", "qty": "Quantity", "warehouse": "Warehouse", "schedule_date": "Schedule Date"}},
    },
    "Supplier Quotation": {
        "required": ["supplier", "items"],
        "optional": ["company"],
        "defaults": {},
        "labels": {"supplier": "Supplier", "items": "Items", "company": "Company"},
        "child_table": {"fieldname": "items", "required": ["item_code", "qty"], "optional": ["rate", "warehouse"], "labels": {"item_code": "Item", "qty": "Quantity", "rate": "Rate", "warehouse": "Warehouse"}},
    },
}


def get_schema(doctype: str) -> Optional[Dict[str, Any]]:
    return DOCTYPE_SCHEMAS.get(doctype)


def get_all_doctypes() -> List[str]:
    return sorted(DOCTYPE_SCHEMAS.keys())


def get_required_fields(doctype: str) -> List[str]:
    s = DOCTYPE_SCHEMAS.get(doctype, {})
    return list(s.get("required", []))


def get_optional_fields(doctype: str) -> List[str]:
    s = DOCTYPE_SCHEMAS.get(doctype, {})
    return list(s.get("optional", []))


def get_defaults(doctype: str) -> Dict[str, Any]:
    s = DOCTYPE_SCHEMAS.get(doctype, {})
    return dict(s.get("defaults", {}))


def get_label(doctype: str, field: str) -> str:
    s = DOCTYPE_SCHEMAS.get(doctype, {})
    return s.get("labels", {}).get(field, field.replace("_", " ").title())


def get_child_table(doctype: str) -> Optional[Dict[str, Any]]:
    s = DOCTYPE_SCHEMAS.get(doctype, {})
    return s.get("child_table")
