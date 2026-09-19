# Graph Report - erp_ai  (2026-09-19)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1319 nodes · 2285 edges · 90 communities (67 shown, 10 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 56 edges (avg confidence: 0.85)
- Token cost: 5,965 input · 3,073 output

## Graph Freshness
- Built from commit: `907b160c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- AI Action Audit
- Knowledge Sources
- Guided Conversation
- RBAC Seed Data
- Assistant Core Chat
- Voice Chat API
- Permission and Field Extraction
- LLM Integration
- ERP Workflow Tools
- Help Knowledge Base
- Tool Execution Engine
- Draft Persistence
- Row-Level Security
- AI Behavior Tests
- File and Voice Cleanup
- ERP Data Tools
- Assistant API Surface
- OCR Document Parsing
- Document Tool Definitions
- MCP Permission Guards
- Voice Worker Resilience
- Workspace Setup and Install
- LLM Model Listing
- Entity Resolution
- Intent Detection
- Permission-Aware Queries
- Idempotency Control
- Safety Injection Guards
- AI Settings Config
- Security Validation Tests
- Stock Issue Workflow
- Security Resolution Tests
- Barcode Processing
- Voice Assistant API
- Intent Testing
- Shipment Workflow
- Draft Confirmation Security
- Schema and Questions
- Security Guardrail Tests
- Barcode Lookup
- Shipment Flow Tests
- Operator Create Tools
- Test Cache Utilities
- Query Validation
- Chat Smoke Tests
- Payload Contract Tests
- AI Action DocType
- Route Whitelist Tests
- Execution Rollback Tests
- System Prompt Tools
- Evaluation Framework
- RPC Authorization
- Endpoint Security Guards
- System Overview Stats
- MCP Core Module
- Rollback Idempotency Contracts
- Stock Issue Workflow
- Help Article DocType
- CI Seeding
- Schema Metadata Validation
- Evaluation Runner
- AI Behavior Patterns
- Number Parsing
- Audit Trail API
- Chat UI Frontend
- Item Pricing
- Low Stock Alerts
- Duplication Safety
- Chat Message DocType
- Provider Normalization
- Doc-Level Write Guard
- Workspace Sync
- Schema Validation
- Chat Message DocType
- MCP Call Tool
- MCP List Tools
- ERP AI Root

## God Nodes (most connected - your core abstractions)
1. `FrappeMCP` - 53 edges
2. `_fetch()` - 32 edges
3. `TestQueryPermissionScoping` - 29 edges
4. `confirm_draft()` - 27 edges
5. `create_draft()` - 26 edges
6. `validate_field()` - 21 edges
7. `ask_llm()` - 20 edges
8. `log_error_safely()` - 19 edges
9. `_SkipIfNoDB` - 18 edges
10. `check_illegal_operation()` - 17 edges

## Surprising Connections (you probably didn't know these)
- `CI Workflow` --references--> `Frappe Framework v15`  [INFERRED]
  .github/workflows/ci.yml → README.md
- `ci_seed` --references--> `ERP AI App`  [EXTRACTED]
  README.md → erp_ai/modules.txt
- `ERP AI App` --implements--> `Frappe Framework v15`  [EXTRACTED]
  erp_ai/modules.txt → README.md
- `Pre-commit Config` --references--> `ERP AI App`  [EXTRACTED]
  .pre-commit-config.yaml → erp_ai/modules.txt
- `CI Workflow` --references--> `ERPNext v15`  [INFERRED]
  .github/workflows/ci.yml → README.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **LLM Provider Stack** — erp_ai_llm, ollama, erp_ai_ask_llm, erp_ai_ai_settings [EXTRACTED 0.90]
- **Voice Processing Pipeline** — erp_ai_voice, whisper_cpp, piper, api_voice_to_text, api_ask_v2_with_voice [EXTRACTED 0.90]
- **Database-Free Test Suite** — erp_ai_tests_test_core, erp_ai_tests_test_security, erp_ai_tests_test_rbac, erp_ai_tests_test_knowledge, erp_ai_tests_test_infra [EXTRACTED 0.95]

## Communities (90 total, 10 thin omitted)

### Community 0 - "AI Action Audit"
Cohesion: 0.05
Nodes (49): _compute_preview_hash(), create_audit_record(), Any, Mark an action as failed with error reason and optional rollback reference., Verify the proposed data hasn't changed since the preview was shown., Compute a stable hash of proposed changes for integrity verification., Create a pending AI Assistant Action record for audit., Mark an action as confirmed by the user. Validates: ownership, nonce, expiry,… (+41 more)

### Community 1 - "Knowledge Sources"
Cohesion: 0.06
Nodes (48): check_freshness(), find_sources_by_doctype(), find_sources_by_tag(), get_citation_for_doctype(), get_source(), KnowledgeSource, Return a knowledge source by ID., Find all sources matching a tag. (+40 more)

### Community 2 - "Guided Conversation"
Cohesion: 0.07
Nodes (45): apply_answer(), _ask_next(), clear_guided(), guided_answer(), guided_ready_again(), _keep(), load_guided(), next_missing() (+37 more)

### Community 3 - "RBAC Seed Data"
Cohesion: 0.05
Nodes (40): ci_seed, ERP AI App, _Doc, _Meta, Administrator has no limit., Stock User has a limit., Auditor has zero limit (read-only)., Verify supervisor requirement data. (+32 more)

### Community 4 - "Assistant Core Chat"
Cohesion: 0.06
Nodes (40): AI Assistant Action DocType, _assistant_reply(), Shared core of the chat endpoints: deterministic data answers first, then the…, log_error_safely(), Log an error without letting the logging call mask the original failure.…, Parse JSON safely without crashing the workflow on bad model output., safe_parse_json(), AIUserBehavior (+32 more)

### Community 5 - "Voice Chat API"
Cohesion: 0.08
Nodes (36): erp_ai.api.ask_v2_with_voice, erp_ai.api.chat, erp_ai.api.voice_to_text, AI Assistant Page, AI Assistant Hub Workspace, AI Settings DocType, is_voice_enabled(), erp_ai.llm (+28 more)

### Community 6 - "Permission and Field Extraction"
Cohesion: 0.08
Nodes (41): check_my_permission(), _extract_fields_for(), _handle_create_intent(), my_permissions(), Return the current user's roles and allowed doctypes., Check if the current user can perform an action on a doctype., extract_invoice_fields(), extract_item_fields() (+33 more)

### Community 7 - "LLM Integration"
Cohesion: 0.08
Nodes (38): Enum, chat(), AISettings, Document, Refuse to store a configuration the assistant cannot run with. The LLM backend…, _ask_anthropic(), _ask_chat_completions(), _ask_google() (+30 more)

### Community 8 - "ERP Workflow Tools"
Cohesion: 0.08
Nodes (31): erp_ai.api.confirm_workflow_action, erp_ai.api.workflow_shipment_receipt, erp_ai.api.workflow_stock_issue, _aggregate(), capabilities(), _count(), _data_answer(), _extract_amount() (+23 more)

### Community 9 - "Help Knowledge Base"
Cohesion: 0.08
Nodes (28): help_get_article(), help_get_articles(), help_get_categories(), help_get_knowledge_base(), help_get_quick_actions(), help_search(), Return help article categories., Return quick-action cards. (+20 more)

### Community 10 - "Tool Execution Engine"
Cohesion: 0.09
Nodes (17): _fallback_to_llm(), _iter_json_objects(), _parse_tool_call(), Yield each balanced-brace JSON object found in `text`. Tool-call parameters are…, Return (tool_name, parameters) if the reply is a valid tool call, else None., Answer via the LLM with live ERP data, executing read tool calls on request.…, call_erp_tool(), execute_erp_tool() (+9 more)

### Community 11 - "Draft Persistence"
Cohesion: 0.10
Nodes (19): create_draft(), generate_preview_hash(), _get_action(), get_draft(), Get pending action from AI Assistant Action DocType. Returns a dict for the…, Resolve an AI Assistant Action, or None. Exactly one of ``action_id`` or…, Persist a pending operation to the AI Assistant Action DocType. Parameters…, Stable hash for the proposed action preview. This is used to detect drift… (+11 more)

### Community 12 - "Row-Level Security"
Cohesion: 0.14
Nodes (4): get_department_restrictions(), Return warehouse/company restrictions for a user., Audit point 6: queries must obey the caller's row-level read scope.…, TestQueryPermissionScoping

### Community 13 - "AI Behavior Tests"
Cohesion: 0.08
Nodes (8): DraftHelpTests, FeedbackTests, PatternTests, Self-checks for the AI User Behavior learning log (mocked, no site needed). Run…, draft_help_for_repeated_failures: inactive, keyworded, idempotent., Bind the session on frappe.local (the repo's bare-test mechanism) — patching…, apply_feedback: thumbs-down marks the last turn corrected; up is a no-op., RecordTests

### Community 14 - "File and Voice Cleanup"
Cohesion: 0.12
Nodes (25): cleanup_temp_files(), Delete uploaded temp files older than max_age_seconds. Returns count removed., Detect MIME type from file magic bytes (first 16 bytes)., Validate file type, size, MIME, and magic-byte signature. Returns error message…, _sniff_mime(), validate_file(), generate_idempotency_key(), Any (+17 more)

### Community 15 - "ERP Data Tools"
Cohesion: 0.08
Nodes (25): get_companies(), get_company_details(), get_customer_details(), get_customers(), get_item_details(), get_items(), get_open_purchase_orders(), get_open_sales_orders() (+17 more)

### Community 16 - "Assistant API Surface"
Cohesion: 0.08
Nodes (25): ask(), ask_with_doc(), cancel_workflow_action(), citation_for(), confirm_workflow_action(), draft_email(), health(), knowledge_freshness() (+17 more)

### Community 17 - "OCR Document Parsing"
Cohesion: 0.12
Nodes (24): ocr_extract_text(), Extract text from an uploaded File (image/PDF) using OCR. Accepts the URL of a…, _ensure_base_dir(), extract_text_from_file(), extract_text_from_image(), extract_text_from_pdf(), _is_within(), parse_invoice_from_text() (+16 more)

### Community 18 - "Document Tool Definitions"
Cohesion: 0.12
Nodes (16): Return a copy of ``data`` containing only safe, writable field values. Payloads…, Return an error message if data is missing live-mandatory fields, else None.…, Return an error message if doctype is not permitted, else None., Return an error message if the current user lacks <action>, else None., Gate by-name document access: doctype-level AND document-level check. The…, _require_doc_permission(), _require_permission(), _sanitize_write_payload() (+8 more)

### Community 19 - "MCP Permission Guards"
Cohesion: 0.13
Nodes (8): FrappeMCP, Get workspace details including shortcuts, links, and content blocks. Args:…, Audit point 6: by-name document access must enforce the document-level (User…, doctype-level check True; doc-level check per ``doc_level_allowed``., Point 6 residual: printing is a by-name read — same gate., Audit point 8: one shared sanitizer must strip every framework-managed field…, TestDocLevelPermissionGuard, TestWritePayloadSanitizer

### Community 20 - "Voice Worker Resilience"
Cohesion: 0.11
Nodes (23): A hung decoder must not hang the worker and must not leak the upload., _stub_frappe(), test_voice_rejects_bad_format_without_touching_disk(), test_voice_rejects_oversized_audio(), test_voice_rejects_oversized_tts(), test_voice_temp_dir_is_private(), test_voice_timeout_cleans_up_temp_files(), _ai_home() (+15 more)

### Community 21 - "Workspace Setup and Install"
Cohesion: 0.13
Nodes (22): _available_workspace_links(), Create the AI Assistant Hub workspace from the bundled JSON spec. Requires…, Keep fixture links that exist on this site's installed apps. ERPNext…, Public entry point for install-time hook and manual refresh. Reads the bundled…, setup_workspace(), sync_workspace_from_json(), Seed all help articles into the database., seed_all() (+14 more)

### Community 22 - "LLM Model Listing"
Cohesion: 0.09
Nodes (22): _get_ollama_base_url(), _list_anthropic_models(), list_available_models(), _list_gemini_models(), _list_groq_models(), _list_mistral_models(), _list_ollama_models(), _list_openai_compat_models() (+14 more)

### Community 23 - "Entity Resolution"
Cohesion: 0.10
Nodes (14): clarification_needed(), pick_candidate(), Return a human-readable candidate list string for the user to choose from.…, Return a clarification question string if the intent is ambiguous or critical…, Test Phase 4 entity resolution and clarification., Should resolve item by exact code., Should resolve item by fuzzy name match., Should resolve customer by exact name. (+6 more)

### Community 24 - "Intent Detection"
Cohesion: 0.14
Nodes (19): detect_intent(), Return (doctype, action) from natural language, or None if unclear., DOCTYPE_SCHEMAS must have entries for all core doctypes., test_get_defaults_item(), test_intent_detection_item(), test_intent_detection_none(), test_intent_detection_urdu(), test_is_numeric() (+11 more)

### Community 25 - "Permission-Aware Queries"
Cohesion: 0.13
Nodes (13): _fetch(), get_sales_invoices(), get_warehouses(), Permission-aware, validated list read. ``frappe.get_all`` forces…, Search items by name, code, or description. Args: query: Search term limit: Max…, Get all warehouses or filter by group. Args: filters: Optional filters (e.g.,…, Get sales invoices. Args: filters: Optional filters limit: Max invoices to…, search_items() (+5 more)

### Community 26 - "Idempotency Control"
Cohesion: 0.17
Nodes (11): check_idempotency(), claim_idempotency(), Check if an operation with this key was already completed or is in progress.…, Claim an idempotency key for an operation about to be performed. Race-safe: the…, Frappe-backed integration tests: idempotency, audit confirmation security,…, A completed action must still block a fresh claim on the same key., Idempotency keys: DB unique constraint + pending/processing blocking., Two in-memory inserts for the same idempotency_key must not both succeed - the… (+3 more)

### Community 27 - "Safety Injection Guards"
Cohesion: 0.10
Nodes (21): check_illegal_operation(), Return error message if the prompt describes an illegal operation, else None., test_illegal_operation_blocked(), test_illegal_operation_modify_submitted(), test_legal_operation_passes(), Normal create operations should pass safety check., Normal queries should pass safety check., Report requests should pass safety check. (+13 more)

### Community 28 - "AI Settings Config"
Cohesion: 0.13
Nodes (17): _fake_response(), _import_llm(), Minimal AI Settings stand-in: attribute access plus ``.get()``. Numeric knobs…, Import erp_ai.llm without frappe, with a throw that actually raises. The CI…, Shipped defaults stay valid: the doctype default is the Select's label form…, The settings form's api_key/llm_model must reach the wire. The runtime used to…, _Settings, test_ask_llm_sends_form_configured_key_and_model() (+9 more)

### Community 29 - "Security Validation Tests"
Cohesion: 0.10
Nodes (19): erp_ai.safety, SQL-like injection in prompts should not crash validators., Script tags in input should be treated as invalid data., Extremely long input should not crash the system., Null bytes in input should be handled., SQL DROP TABLE should be blocked by validator., SQL UNION SELECT should not be treated as a number., Negative numbers should parse correctly. (+11 more)

### Community 30 - "Stock Issue Workflow"
Cohesion: 0.13
Nodes (7): Audit point 7: the natural-language issue path was structurally broken — it…, TestStockIssueNL, create_stock_issue(), handle_issue_nl(), Any, Create a Stock Entry for material issue., Parse natural language stock issue text.

### Community 31 - "Security Resolution Tests"
Cohesion: 0.12
Nodes (15): Resolve an item name/code to ERPNext Item records. Tries exact code match…, resolve_item(), _has_real_db(), ERP AI Security & Workflow Tests These tests verify Phase 1-4 improvements: -…, Audit point 7: required-field validation runs against live metadata (so Custom…, Site-agnostic: whatever this site's live meta demands (incl. Custom Fields), a…, Return True if a real, DB-backed Frappe site context is available. When the…, Mixin that skips DB-requiring test methods when no real site DB is present.… (+7 more)

### Community 32 - "Barcode Processing"
Cohesion: 0.12
Nodes (17): _ean13_checksum(), generate_item_barcode_data(), Validate EAN-13 checksum digit., Validate UPC-A checksum digit., Validate a barcode format with checksum verification., Generate barcode data for an item (for label printing)., _upc_checksum(), validate_barcode_format() (+9 more)

### Community 33 - "Voice Assistant API"
Cohesion: 0.13
Nodes (16): ask_v2(), ask_v2_with_voice(), Get current voice on/off status for the user., Toggle voice on/off. Returns new state., Explicitly set voice on/off., Dict-returning chat variant ({response, session}) consumed by…, Enhanced AI assistant with optional voice output., voice_set() (+8 more)

### Community 34 - "Intent Testing"
Cohesion: 0.16
Nodes (10): detect_intent(), Test intent detection and DOCTYPE mapping., Should detect item creation intent., Should detect sales invoice intent., Should detect purchase invoice intent., Should detect customer creation intent., Should detect supplier creation intent., Should detect payment entry intent. (+2 more)

### Community 35 - "Shipment Workflow"
Cohesion: 0.16
Nodes (13): handle_shipment_nl_request(), Record an incoming shipment via preview -> confirm flow. This endpoint no…, Parse shipment natural language request and return structured data. Parsing is…, Save a shipment draft for later confirmation. Persisted only through the…, save_shipment_draft(), workflow_shipment_receipt(), Resolve a warehouse for a workflow: explicit hint, then site defaults. Order: a…, resolve_warehouse() (+5 more)

### Community 36 - "Draft Confirmation Security"
Cohesion: 0.24
Nodes (6): confirm_draft(), Confirm (create) a pending operation using the AI Assistant Action store. The…, confirm_draft must verify ownership, nonce, expiry, status, preview hash., Item has no site-custom mandatory fields, so confirmations succeed…, Fields made mandatory by another app (e.g. tax NTN/CNIC) get a clear listable…, TestAuditConfirmationSecurity

### Community 37 - "Schema and Questions"
Cohesion: 0.16
Nodes (13): get_question(), Return the natural language question for a field., get_child_table(), get_label(), get_optional_fields(), get_required_fields(), get_schema(), Any (+5 more)

### Community 38 - "Security Guardrail Tests"
Cohesion: 0.14
Nodes (8): Test Phase 1 security guardrails., Ensure core business DocTypes are in the allowlist., Ensure security/system DocTypes are blocked., Empty doctype should be rejected., Blocked DocTypes should be rejected., Allowed DocTypes should pass validation., DocTypes not in allowlist should be rejected., TestPhase1Security

### Community 39 - "Barcode Lookup"
Cohesion: 0.17
Nodes (7): barcode_lookup(), Resolve a scanned barcode/QR to an ERP document (permission-checked)., Any, Resolve a scanned barcode/QR to an ERPNext document. Order: 1. Item Barcode…, resolve_barcode(), The new whitelisted infrastructure endpoints behave correctly., TestInfrastructureEndpoints

### Community 40 - "Shipment Flow Tests"
Cohesion: 0.17
Nodes (7): _FakeMCP, Shipment draft -> confirm flow via the public API, plus cancel semantics. These…, Master data created mid-workflow must roll back when the receipt fails., Returns success for supplier/item creation, failure for receipts., TestPartialFailureRollback, TestShipmentPreviewConfirmCancel, FrappeTestCase

### Community 41 - "Operator Create Tools"
Cohesion: 0.21
Nodes (12): create_customer(), create_draft_for_review(), create_item(), create_sales_order(), create_supplier(), _log_tool_error(), Create a new supplier. Args: supplier_name: Supplier name supplier_group:…, Log a tool failure without letting logging mask the original error.… (+4 more)

### Community 43 - "Query Validation"
Cohesion: 0.20
Nodes (8): _column_of(), Return the underlying column name: 'count(name) as total' -> 'name'., Reject an unknown filter field or an unsupported operator, else None., Return an error message if the query names something invalid, else None.…, _validate_filter_dict(), _validate_query(), ``count(name) as total`` must pass validation (the audit helpers rely on it)…, A site without ERPNext has no metadata for business DocTypes; the tools must…

### Community 44 - "Chat Smoke Tests"
Cohesion: 0.20
Nodes (3): P0 regression (fresh release audit): after the chat-dispatch refactor the chat…, A failed filtered count must answer nothing, not leak the unfiltered total…, TestChatRouteSmoke

### Community 45 - "Payload Contract Tests"
Cohesion: 0.38
Nodes (3): Every key an operator create tool sends must exist in that DocType's schema…, Run a create tool with the write boundary stubbed, return its payload., TestOperatorCreatePayloadContract

### Community 46 - "AI Action DocType"
Cohesion: 0.22
Nodes (3): AIAssistantAction, Document, Enforce the one-way action lifecycle. Reviving a terminal action would let a…

### Community 47 - "Route Whitelist Tests"
Cohesion: 0.28
Nodes (4): P0 #2/#86: every public route must really be a public route. A dropped…, Routes are dispatched as ``frappe.call(fn, **frappe.form_dict)``…, Every endpoint the audit listed must exist and be importable., TestRouteWhitelistContract

### Community 48 - "Execution Rollback Tests"
Cohesion: 0.31
Nodes (3): Registry doctypes beyond the six bespoke builders must be executable through…, If MCP raises mid-execution, no document is persisted and the action is marked…, TestGenericDepartmentExecution

### Community 49 - "System Prompt Tools"
Cohesion: 0.25
Nodes (8): _operator_snapshot(), _operator_system_prompt(), Live site counts the model can quote without a tool call. Best-effort., System prompt: operator role, callable tools, and live ERP state. Only read…, get_available_tools(), get_erp_tools_list(), Get list of all available ERP tools with descriptions. Returns: List of tool…, Return list of available ERP tools.

### Community 50 - "Evaluation Framework"
Cohesion: 0.29
Nodes (7): EvalCase, EvalResult, Any, A single evaluation test case., Result of running an evaluation case., Run evaluation cases against a prompt-answering function., run_evaluation()

### Community 51 - "RPC Authorization"
Cohesion: 0.25
Nodes (3): Audit point 9: the whitelisted RPC wrapper must be reachable only by intended…, The gate lets a manager through; deeper tool checks still apply (here: the…, TestMCPRpcAuthorization

### Community 52 - "Endpoint Security Guards"
Cohesion: 0.29
Nodes (4): Audit point 5: privileged endpoints must not leak another user's data.…, A non-owner must not be able to OCR someone else's private upload., An unregistered file_url must be rejected, not read from disk., TestEndpointGuards

### Community 53 - "System Overview Stats"
Cohesion: 0.29
Nodes (7): _count(), get_system_overview(), get_transaction_summary(), Any, Permission-aware COUNT (``frappe.db.count`` applies no permissions)., Get comprehensive overview of the entire ERP system. Returns counts and key…, Get transaction summary for recent period. Args: days: Number of days to look…

### Community 54 - "MCP Core Module"
Cohesion: 0.43
Nodes (6): mcp_call_tool(), mcp_list_tools(), whitelist, Return an error message if the RPC call is not allowed, else None., List available MCP tools., _rpc_denied()

### Community 55 - "Rollback Idempotency Contracts"
Cohesion: 0.38
Nodes (4): Production-hardening contracts for rollback references and concurrent…, A failed confirmation must leave a navigable rollback_reference on the action,…, Two concurrent confirmations of the same pending action must not both create a…, TestRollbackAndIdempotencyContracts

### Community 56 - "Stock Issue Workflow"
Cohesion: 0.33
Nodes (6): handle_stock_issue_nl_request(), Issue/transfer stock via preview -> confirm flow. This endpoint no longer…, Parse stock issue natural language request and return structured data. Parsing…, Save a stock issue draft for later confirmation. Persisted only through the…, save_stock_issue_draft(), workflow_stock_issue()

### Community 57 - "Help Article DocType"
Cohesion: 0.33
Nodes (3): AIHelpArticle, Document, Return example queries as a list.

### Community 58 - "CI Seeding"
Cohesion: 0.53
Nodes (5): _insert_if_missing(), Seed the minimal ERPNext masters the Frappe-backed test suite assumes. A bare…, Insert when absent; return the existing/created document name., _root_group(), seed()

### Community 59 - "Schema Metadata Validation"
Cohesion: 0.40
Nodes (3): Every schema doctype must exist in live metadata with its required fields.…, NCR is not a stock v15 doctype; the registry must not reference it., TestLiveDocTypeMetadata

### Community 60 - "Evaluation Runner"
Cohesion: 0.40
Nodes (5): _process_with_mcp(), Run the model evaluation suite. Requires System Manager., Evaluation hook: answer through the real assistant core (read paths).…, run_evaluation(), _ask()

### Community 61 - "AI Behavior Patterns"
Cohesion: 0.40
Nodes (4): AIBehaviorPattern, Document, Controller: rows are owned by the nightly task, not by users., AI Behavior Pattern — the nightly materialized view of the behavior log. Rows…

### Community 62 - "Number Parsing"
Cohesion: 0.40
Nodes (5): test_parse_number_with_currency(), Unicode digits should not crash parser., test_parse_number_unicode(), parse_number(), Parse a number from user text. Handles '1,200', 'rs 500', '500pk', etc.

### Community 63 - "Audit Trail API"
Cohesion: 0.50
Nodes (4): audit_history(), Return the current user's AI action audit trail., get_audit_trail(), Return all audit records for a session.

### Community 64 - "Chat UI Frontend"
Cohesion: 0.83
Nodes (3): add(), msgEl(), send()

### Community 65 - "Item Pricing"
Cohesion: 0.50
Nodes (4): _first(), get_item_price(), Permission-aware single-row read (``frappe.db.get_value`` ignores perms)., Get price list entry for an item. Args: item_code: The item code price_list:…

### Community 66 - "Low Stock Alerts"
Cohesion: 0.50
Nodes (4): get_low_stock_items(), Permission-aware SUM (``frappe.db.get_sum`` ignores permissions)., Get items with stock below threshold. Args: threshold: Minimum quantity to…, _sum()

### Community 67 - "Duplication Safety"
Cohesion: 0.50
Nodes (3): get_duplication_fields(), Return fields to check for duplicates before creating., test_duplication_fields()

## Knowledge Gaps
- **13 isolated node(s):** `setup_voice.sh script`, `erp_ai`, `Pre-commit Config`, `MariaDB 10.11`, `Redis 7` (+8 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 562 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `FrappeMCP` connect `MCP Permission Guards` to `AI Action Audit`, `Guided Conversation`, `Shipment Workflow`, `Draft Confirmation Security`, `Doc-Level Write Guard`, `ERP Workflow Tools`, `Operator Create Tools`, `Row-Level Security`, `ERP Data Tools`, `Document Tool Definitions`, `MCP Core Module`, `Stock Issue Workflow`, `Stock Issue Workflow`, `Security Resolution Tests`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Why does `ask_llm()` connect `LLM Integration` to `ERP Workflow Tools`, `Assistant API Surface`, `Tool Execution Engine`, `Assistant Core Chat`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Why does `get_citation_for_doctype()` connect `Knowledge Sources` to `ERP Workflow Tools`, `Assistant API Surface`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `FrappeMCP` (e.g. with `capabilities()` and `mcp_call_tool()`) actually correct?**
  _`FrappeMCP` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `setup_voice.sh script`, `erp_ai`, `Pre-commit Config` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `AI Action Audit` be split into smaller, more focused modules?**
  _Cohesion score 0.05297532656023222 - nodes in this community are weakly interconnected._
- **Should `Knowledge Sources` be split into smaller, more focused modules?**
  _Cohesion score 0.058823529411764705 - nodes in this community are weakly interconnected._