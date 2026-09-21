# ---------------------------------------------------------------------------
# Seed script for AI Help Articles.
# Run: bench --site spi.local execute erp_ai.help.seed_articles.seed_all
# ---------------------------------------------------------------------------

import frappe

ARTICLES = [
	{
		"title": "Getting Started with AI Assistant",
		"category": "Getting Started",
		"icon": "rocket",
		"description": "Learn how to use the AI Assistant for the first time",
		"keywords": "start,begin,intro,help,guide,first time",
		"content": "# Getting Started with AI Assistant\n\nWelcome to the ERP AI Assistant!\n\n## Quick Start\n1. **Open AI Chat**: Click 'Open AI Chat' from the workspace\n2. **Ask a Question**: Type in natural language\n3. **Get Results**: AI queries your ERP data\n\n## What You Can Do\n- **Data Queries**: 'How many items?'\n- **Create Documents**: 'Create item Steel Rod price 100'\n- **Voice Input**: Click mic to speak\n\n## Tips\n- Be specific with numbers and names\n- Documents created as Draft first\n- Ask follow-up questions in same chat",
		"example_queries": "How do I start?\nWhat can the AI do?\nHelp me get started",
	},
	{
		"title": "Creating Items via Chat",
		"category": "Data Entry",
		"icon": "plus-circle",
		"description": "Create new item masters using natural language",
		"keywords": "item,create,new,product,inventory,stock",
		"content": "# Creating Items via Chat\n\nCreate item masters by describing them.\n\n## Commands\n- 'Create item named Steel Rod price 100'\n- 'Add item Spring Steel Wire, price 50/kg, group Raw Material'\n\n## Required Fields\n- item_name\n- item_group (default: Products)\n- stock_uom (default: Nos)\n\n## Optional Fields\n- standard_rate (selling price)\n- purchase_rate\n- opening_stock\n\n## Examples\n- 'Create item Steel Rod price 100'\n- 'New product Pump Assembly price 5000'\n- 'Service item Repair Service rate 1000'",
		"example_queries": "Create item\nAdd new product\nHow to make an item",
	},
	{
		"title": "Recording a Purchase Receipt",
		"category": "Buying",
		"icon": "truck",
		"description": "Record incoming shipments and goods receipts",
		"keywords": "purchase,receipt,goods,received,shipment,incoming,supplier",
		"content": "# Recording a Purchase Receipt\n\nRecord incoming goods from suppliers.\n\n## Commands\n- 'Received 500 pump springs from ABC Traders'\n- 'Shipment from ABC Traders, vehicle LEA-4521, 500 springs @ 50, warehouse Raw Materials'\n\n## Required Info\n- Supplier name\n- Item name/code\n- Quantity\n- Destination warehouse\n\n## Optional Details\n- Rate/price\n- Vehicle number\n- Bill number\n- Remarks\n\n## After Creation\n- Review Purchase Receipt in Draft\n- Submit to update stock",
		"example_queries": "Record purchase\nGoods received\nIncoming shipment\nRecord receipt",
	},
	{
		"title": "Creating a Sales Invoice",
		"category": "Selling",
		"icon": "file-text",
		"description": "Create sales invoices via natural language chat",
		"keywords": "sales,invoice,bill,customer,selling,create",
		"content": "# Creating a Sales Invoice\n\nGenerate sales invoices by describing the sale.\n\n## Commands\n- 'Make invoice for ABC Traders, 2 pump springs @ 500'\n- 'Bill XYZ Corp: 5 steel rods @ 200, 3 springs @ 150'\n\n## Required Fields\n- Customer\n- Items (code, qty, rate)\n- Company (auto-detected)\n\n## Examples\n- 'Invoice ABC Traders for 10 springs @ 500'\n- 'Sales invoice for Customer A, 3 items @ 1000 with tax'\n\n## After Creation\n- Review draft invoice\n- Submit for accounting entries\n- Send PDF to customer",
		"example_queries": "Create invoice\nBill customer\nSales invoice\nMake bill",
	},
	{
		"title": "Stock Entry Operations",
		"category": "Stock",
		"icon": "arrow-up-right",
		"description": "Issue, transfer, and reconcile stock via chat",
		"keywords": "stock,issue,transfer,move,receipt,material",
		"content": "# Stock Entry Operations\n\nManage stock movements.\n\n## Types\n- **Issue**: 'Issue 10 springs to Production'\n- **Receipt**: 'Receive 200 springs into Stores'\n- **Transfer**: 'Move 50 rods from Stores to Production'\n- **Manufacture**: 'Make 5 assemblies from BOM PUMP-001'\n\n## Required Fields\n- item_code\n- qty\n- source/target warehouse\n\n## Examples\n- 'Issue 10 springs to Engr Ali'\n- 'Receive 500 rods into Raw Materials'\n- 'Transfer 20 springs from Stores to FG'",
		"example_queries": "Issue stock\nTransfer material\nMove stock\nStock entry",
	},
	{
		"title": "Accounting Basics",
		"category": "Accounting",
		"icon": "dollar",
		"description": "Understand accounting entries created by the AI",
		"keywords": "accounting,journal,gl,debit,credit,payment",
		"content": "# Accounting Basics\n\nThe AI creates proper accounting entries.\n\n## Double-Entry System\n- **Debit (Dr)**: What comes in\n- **Credit (Cr)**: What goes out\n\n## Sales Invoice Entry\n- Dr Accounts Receivable\n- Cr Income/Sales\n- Cr Sales Tax Payable\n\n## Payment Entry\n- Dr Bank/Cash\n- Cr Accounts Receivable\n\n## Purchase Invoice\n- Dr Expense/Stock\n- Cr Accounts Payable\n- Dr Input Tax",
		"example_queries": "Accounting entries\nDebit credit\nJournal entry\nGL entry",
	},
	{
		"title": "Voice Input Guide",
		"category": "Getting Started",
		"icon": "mic",
		"description": "Use voice commands to interact with the AI",
		"keywords": "voice,speak,mic,urdu,roman,language,audio",
		"content": "# Voice Input Guide\n\nSpeak your questions to the AI.\n\n## How to Use\n1. Click microphone\n2. Speak in English or Urdu\n3. Review transcription\n4. Send query\n\n## Supported Languages\n- English (full)\n- Roman Urdu\n- Urdu script (experimental)\n\n## Tips\n- Speak at normal pace\n- Minimize background noise\n- Be specific with numbers\n\n## Troubleshooting\n- Check browser permissions\n- Use Chrome/Edge\n- Check system microphone",
		"example_queries": "Voice input\nHow to speak\nMic not working\nVoice commands",
	},
	{
		"title": "AI Settings Configuration",
		"category": "Setup",
		"icon": "settings",
		"description": "Configure AI behavior and LLM settings",
		"keywords": "settings,config,setup,llm,api,model,knowledge",
		"content": "# AI Settings Configuration\n\nConfigure via /app/ai-settings\n\n## LLM Configuration\n- Model (gpt-4, claude)\n- API Key\n- Temperature (0.0-1.0)\n- Max Tokens\n\n## Knowledge Base\n- Inject KB in prompts\n- KB Max Chars\n- Citation Mode\n\n## Safety\n- Require Confirmation\n- Allow Submit\n- Max Results\n\n## Recommended\n- Temperature: 0.1-0.3\n- Require Confirmation: Yes\n- Allow Submit: No",
		"example_queries": "Settings\nConfiguration\nHow to configure\nAPI key setup",
	},
	{
		"title": "Troubleshooting Common Issues",
		"category": "Troubleshooting",
		"icon": "help-circle",
		"description": "Solutions to common problems",
		"keywords": "error,problem,fix,issue,not working,debug,troubleshoot",
		"content": "# Troubleshooting\n\n## AI Not Responding\n- Check LLM API key\n- Verify network\n- Check AI Settings\n- Review Error Log\n\n## Permission Errors\n- Verify user roles\n- Check DocType permissions\n- Ensure read/write access\n\n## Document Creation Fails\n- Check required fields\n- Verify item/customer exists\n- Review Error Log\n\n## Voice Not Working\n- Grant mic permission\n- Use Chrome/Edge\n- Check system settings\n\n## Getting Help\n- Check this help system\n- Contact System Manager\n- Review Error Log",
		"example_queries": "Not working\nError\nProblem\nFix\nIssue\nHelp",
	},
	{
		"title": "Manufacturing Workflow",
		"category": "Manufacturing",
		"icon": "gear",
		"description": "Create BOMs, Work Orders, and track production",
		"keywords": "manufacturing,bom,work order,job card,production,assembly",
		"content": "# Manufacturing Workflow\n\n## BOM Creation\n- 'Create BOM for Pump Assembly, components: 2 springs @ 50, 1 housing @ 500'\n\n## Work Order\n- 'Create work order for 10 Pump Assemblies'\n\n## Stock Entry Manufacture\n- 'Manufacture 5 pump assemblies from BOM PUMP-001'\n\n## Flow\n1. Create BOM\n2. Create Work Order\n3. Complete Job Cards\n4. Manufacture Entry\n\n## Examples\n- 'BOM for Spring Assembly, needs 2 springs and 1 rod'\n- 'Start production of 20 pump assemblies'",
		"example_queries": "BOM\nWork order\nManufacturing\nProduction\nAssembly\nJob card",
	},
]


def seed_all():
	"""Seed all help articles into the database."""
	created = 0
	for article_data in ARTICLES:
		if frappe.db.exists("AI Help Article", {"title": article_data["title"]}):
			continue
		doc = frappe.new_doc("AI Help Article")
		doc.update(article_data)
		doc.insert(ignore_permissions=True)
		created += 1
	frappe.db.commit()
	print(f"Seeded {created} help articles (skipped {len(ARTICLES) - created} existing)")


if __name__ == "__main__":
	seed_all()
