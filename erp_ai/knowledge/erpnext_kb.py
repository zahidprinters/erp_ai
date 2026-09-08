"""ERPNext Knowledge Base for AI Assistant.

Feeds the LLM detailed ERPNext workflow knowledge so it can guide users
through any business process, create documents correctly, and answer
micro-level questions about the ERP system.
"""

KB = """
ERPNext KNOWLEDGE BASE (SPI ERP System - Frappe Framework v15 / ERPNext v15)

=== CORE CONCEPTS ===
- DocType: The data model in Frappe. Every entity (Item, Customer, Invoice) is a DocType.
- Document States: Draft (docstatus=0) -> Submitted (docstatus=1) -> Cancelled (docstatus=2).
  Submitted documents create accounting/stock entries. Only Draft can be edited.
- Named masters: Customer, Supplier, Item, Employee, Warehouse, Company, Account, etc.
- Transaction documents: Sales Order, Sales Invoice, Delivery Note, Purchase Order,
  Purchase Invoice, Purchase Receipt, Stock Entry, Payment Entry, Journal Entry.
- Naming: documents usually auto-named with series (SINV-0001, ACC-SINV-2026-0001).
- Permissions: Role-based. Common roles: Administrator, System Manager, Accounts Manager,
  Accounts User, Sales Manager, Sales User, Purchase Manager, Stock Manager, Stock User,
  Manufacturing Manager, HR Manager.

=== MODULES ===
1. ACCOUNTING - Chart of Accounts, Journal Entry, GL Entry, Payment Entry, Fiscal Year,
   Cost Center, Budget, Taxes (Sales/Purchase Taxes Templates), Bank Reconciliation.
2. SELLING - Lead, Opportunity, Quotation, Sales Order, Delivery Note, Sales Invoice,
   Customer, Sales Partner, Sales Person, Pricing Rule.
3. BUYING - Material Request, Request for Quotation, Supplier Quotation, Purchase Order,
   Purchase Receipt, Purchase Invoice, Supplier, Subcontracting.
4. STOCK/INVENTORY - Item, Warehouse, Stock Entry, Stock Ledger Entry, Bin, Batch,
   Serial No, Stock Reconciliation, Material Request, Delivery Note, Purchase Receipt.
5. MANUFACTURING - BOM (Bill of Materials), Work Order, Job Card, Production Plan,
   Operations, Workstations, Scrap.
6. HR/Payroll - Employee, Leave Application, Attendance, Salary Structure, Payroll Entry.
7. CRM - Lead, Opportunity, Campaign, Contact, Address.
8. PROJECTS - Project, Task, Timesheet, Project Updates.
9. ASSETS - Asset, Asset Category, Asset Movement, Depreciation.

=== SELLING WORKFLOW (complete cycle) ===
Lead (prospect) -> Opportunity -> Quotation -> Sales Order -> Delivery Note -> Sales Invoice -> Payment Entry

1. LEAD: Fields: lead_name, lead_owner, status (Open/Converted/Interested), source,
   mobile_no, email_id. Converted to Customer when deal is ready.
2. QUOTATION: Fields: party (lead/customer), items (item_code, qty, rate, amount),
   taxes, valid_till. Can convert to Sales Order. Status: Draft/Open/Lost/Ordered.
3. SALES ORDER (SO): REQUIRED: customer, delivery_date, company, items[] with:
   item_code (REQUIRED), qty (REQUIRED), rate, warehouse, income_account.
   Status: Draft -> To Deliver and Bill -> Completed. Tracks % delivered, % billed.
   One SO can have multiple Delivery Notes and Invoices (partial delivery allowed).
4. DELIVERY NOTE (DN): REQUIRED: customer, items[] with item_code, qty, s_warehouse
   (source warehouse). Updates stock (reduces). Created from Sales Order usually.
5. SALES INVOICE (SI): REQUIRED: customer, company, items[] with item_code, qty, rate;
   taxes_and_charges template optional, payment_terms_template optional.
   - update_stock checkbox: if TRUE, invoice also reduces stock (skip Delivery Note).
   - When submitted: creates GL Entry (Debit: Accounts Receivable / Debtors;
     Credit: Income/Sales, Credit: Taxes) + Stock Ledger if update_stock=1.
   - Status flow: Draft -> Unpaid -> Partly Paid -> Paid / Overdue / Return / Credit Note Issued.
   - print_format: Standard, POS Invoice, etc. PDF: /api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Invoice&name=SINV-0001&format=Standard
6. PAYMENT ENTRY: Records money received/paid. Links to invoices via 'references' child
   table. Debit: Bank/Cash account; Credit: Debtors (for receipt). Use Payment
   Reconciliation to match advances.

Shortcuts allowed: Retail = only Sales Invoice (update_stock=1). Services = SO -> SI (no DN).

=== BUYING WORKFLOW ===
Material Request -> RFQ -> Supplier Quotation -> Purchase Order -> Purchase Receipt -> Purchase Invoice -> Payment Entry

1. MATERIAL REQUEST (MR): type: Purchase / Transfer / Manufacture / Customer Provided.
   REQUIRED: items[] with item_code, qty, warehouse (schedule_date). Auto-created when
   stock falls below Reorder Level (Item > Auto Reorder section).
2. PURCHASE ORDER (PO): REQUIRED: supplier, company, schedule_date, items[] with
   item_code, qty, rate, warehouse. Status: To Receive and Bill -> Completed.
3. PURCHASE RECEIPT (PR): Records goods physically received. REQUIRED: supplier,
   items[] with item_code, qty, t_warehouse (target warehouse = where stock goes).
   Updates stock (increases). Valuation rate from PO rate.
4. PURCHASE INVOICE: Like SI but for buying. Debit: Stock/Expense account;
   Credit: Accounts Payable / Creditors. update_stock=1 also increases stock.

=== INVENTORY / STOCK WORKFLOW ===

WAREHOUSE TYPES: Use hierarchical warehouses:
- Stores (raw material store) - RM STORE
- Technical Store / Spare Parts Store
- Finished Goods Store (FG STORE)
- Transit warehouse (type Transit) for transfers between locations
- Rejected / Quarantine warehouse
Each warehouse has: warehouse_name, company, is_group (parent), account (for perpetual inventory).

ITEM MASTER (required fields to create an Item):
- item_code (ID), item_name, item_group (REQUIRED - grouping like Products, Raw Material,
  Services, Spare Parts), stock_uom (REQUIRED - Unit of Measure: Nos, Kg, Litre, Box, Set).
- is_stock_item (1 = tracked in stock; 0 = service/consumable without stock tracking).
- maintain_stock, has_batch_no, has_serial_no (for tracking batches/serials).
- standard_rate (default selling price), valuation_method (FIFO default / Moving Average).
- item_defaults: default_warehouse, expense_account, income_account, buying_cost_center.
- Item Price doctype: separate price per Price List (Standard Selling / Standard Buying).
- Opening stock: set during creation (opening_stock + opening_warehouse) or via
  Stock Reconciliation / Stock Entry (Material Receipt).

STOCK ENTRY PURPOSES:
1. Material Receipt - ADD stock into a warehouse (t_warehouse only). Used for:
   opening stock, new shipment arrival, customer return.
2. Material Transfer - MOVE stock between warehouses (s_warehouse -> t_warehouse).
   Used: Raw Material Store -> Technical Store, Stores -> Production, etc.
   Optional 'Add to Transit' checkbox for two-step transfers.
3. Material Issue - REMOVE/consume stock (s_warehouse only). Used for:
   damage, expiry, sample issue, consumption without production order.
4. Manufacture - Produce FG from raw materials per BOM.
5. Repack - Split/combine items into new item bundles.
6. Send to Subcontractor - Material to supplier for processing.

REQUIRED fields in Stock Entry: purpose, company, items[] with:
- item_code, qty
- s_warehouse (source, for Transfer/Issue) 
- t_warehouse (target, for Receipt/Transfer/Manufacture)
- basic_rate (valuation)

SHIPMENT ARRIVAL WORKFLOW (goods received from supplier):
1. Create/verify Supplier and Purchase Order (optional but best practice).
2. Record goods: EITHER Purchase Receipt (if PO exists, links & updates stock into
   t_warehouse) OR Stock Entry with purpose 'Material Receipt' (direct, no PO).
3. Items go to the correct store: raw materials -> RM STORE, spares -> Technical Store.
4. Submit -> stock increases in that warehouse; valuation from rate.
5. Supplier invoice later -> Purchase Invoice (links PO/PR, posts liability).
6. Payment Entry pays the supplier.

ISSUE TO DEPARTMENT WORKFLOW:
1. Stock Entry purpose 'Material Issue' OR 'Material Transfer' to department warehouse.
2. Track issued-to person via 'issued_to' pattern: use Stock Entry custom field or
   tag Employee in description; alternatively create a Material Request from the
   department and issue against it.
3. For consumption accounting, set expense account in item defaults.

STOCK RECONCILIATION: Periodic physical count correction. Items[] with item_code,
warehouse, qty (counted). Adjusts Bin to actual. Used for opening stock in bulk too.

=== MANUFACTURING WORKFLOW ===
1. BOM (Bill of Materials): parent item + items[] (raw materials + qty per FG unit) +
   operations (optional: machine, time). REQUIRED: item (finished good), items[], qty.
2. Work Order: REQUIRED: production_item, bom_no, qty, fg_warehouse (finished goods
   warehouse), wip_warehouse (work in progress), company.
   Status: Draft -> Not Started -> In Process -> Completed. Creates Stock Entries:
   'Send to WIP' (transfer RM), 'Manufacture' (consumes RM, produces FG).
3. Job Card: tracks each operation on a workstation with time logs.
4. Production Plan: consolidates SO/MR into manufacturing plan.

=== ACCOUNTING ESSENTIALS ===
- Chart of Accounts: hierarchy - Assets (Current/Fixed), Liabilities, Equity, Income,
  Expense. Company mandatory field on all accounting docs.
- Double entry: every transaction creates GL Entries (Debit = Credit).
- Sales Invoice submit: Dr Debtors (AR), Cr Income, Cr Taxes. Payment: Dr Bank, Cr Debtors.
- Purchase Invoice submit: Dr Stock/Expense, Cr Creditors (AP). Payment: Dr Creditors, Cr Bank.
- Stock Entry: Dr/Cr warehouse accounts based on movement (perpetual inventory).
- Taxes: Sales Taxes and Charges Template (e.g., Sales Tax 17%); Item Tax Template for
  per-item tax. Pakistan: Sales Tax 17%/18%, FBR integration via fbr_pos_integration app.
- Modes of Payment: Cash, Bank Transfer, Cheque, Card - mapped to accounts.
- Payment Terms Template: e.g., 'Net 30'. Credit Limit on Customer warns/blocks.
- Reports: General Ledger, Accounts Receivable/Payable, Profit & Loss, Balance Sheet,
  Trial Balance, Stock Balance, Stock Ledger, Sales Register, Purchase Register.

=== SETUP A NEW ERP SYSTEM (guided by AI) ===
1. Company setup: company_name, default_currency (PKR), country (Pakistan), fiscal year start.
2. Chart of Accounts: import standard or customize. Cost Centers.
3. Users & Roles: add users, assign roles (Sales, Purchase, Stock, Accounts...).
4. Warehouses: create hierarchy (Stores, Technical Store, FG Store, Transit).
5. Item Groups: Products, Raw Material, Spare Parts, Services.
6. Items: create masters with UOM, prices, tax templates.
7. Customers & Suppliers: with groups, territories, credit limits, payment terms.
8. Taxes: Sales/Purchase Tax Templates (Sales Tax 17%/18% Pakistan).
9. Price Lists: Standard Selling, Standard Buying.
10. Opening balances: Stock Reconciliation, Opening Invoice Creation Tool, Journal Entry.
11. Settings: Stock Settings (allow negative stock off), Selling/Buying settings.

=== PRINTING & REPORTS ===
- Print format per DocType (Standard default). PDF download API:
  /api/method/frappe.utils.print_format.download_pdf?doctype=<DT>&name=<NAME>&format=Standard
- Letterheads: company logo + address in print.
- Reports: query reports, script reports; print any report; export CSV/Excel.
- SPI custom: FBR POS integration for tax invoices (fbr_pos_integration app).

=== SPI BUSINESS CONTEXT (pump spring / engineering company) ===
Typical flow when a shipment of pump springs arrives:
1. 'Spring shipment arrived from supplier X, vehicle ABC-123, 500 pcs' ->
   AI should: verify/create supplier, create Purchase Receipt or Stock Entry (Material
   Receipt) with item=pump spring, qty=500, t_warehouse=RM STORE (or Technical Store),
   rate if given, reference vehicle in remarks. Ask user for missing data: supplier,
   item, qty, rate, destination store, vehicle/GRN no.
2. Issue to production/department: Stock Entry Material Transfer RM STORE -> WIP or
   Material Issue with department/person recorded in remarks.
3. Sale: Sales Order -> Delivery Note from FG STORE -> Sales Invoice (or direct SI with
   update_stock) -> Payment Entry -> FBR tax invoice print if POS sale.

RULES FOR THE AI ASSISTANT:
- ALWAYS ask for missing required fields before creating a document (list them clearly).
- Confirm before submitting financial/stock documents; create as Draft and tell user.
- Give exact numbers from the database (use MCP tools), never invent data.
- Answer in the user's language (English or Urdu/Roman Urdu).
- For admins: technical detail; for operators: short step-by-step guidance.
"""


def get_knowledge_base():
    return KB


def get_knowledge_excerpt(max_chars=12000):
    """Return knowledge base (optionally trimmed) for prompt injection."""
    return KB[:max_chars]
