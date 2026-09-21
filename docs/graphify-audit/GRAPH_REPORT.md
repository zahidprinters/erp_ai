# Graph Report - erp_ai  (2026-09-21)

## Corpus Check
- 170 files · ~442,726 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2553 nodes · 3638 edges · 290 communities (261 shown, 13 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 47 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `57853d47`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Communities (90 total, 10 thin omitted)
- erp_tools.py
- audit.py
- api.py
- ask_llm
- create_draft
- whitelist
- conversation.py
- test_rbac.py
- rbac/__init__.py
- draft_workflow.py
- test_erp_ai_security.py
- ERP AI Release Notes - LLM Provider Multi-Support & Admin Settings
- voice/__init__.py
- FrappeMCP
- test_core.py
- articles.py
- test_infra.py
- TestPhase4EntityResolution
- test_security.py
- attachments.py
- check_illegal_operation
- Architecture
- install.py
- check_permission
- execute_erp_tool
- _log_tool_error
- test_frappe_integration.py
- KnowledgeSource
- FrappeTestCase
- _ean13_checksum
- ai_user_behavior.py
- ai_widget.js
- _import_llm
- log_error_safely
- confirm_draft
- detect_intent
- TestQueryPermissionScoping
- ._draft
- find_sources_by_doctype
- schema/__init__.py
- TestGenericDepartmentExecution
- ERP AI — Development Phases & Improvement Roadmap
- resolve_barcode
- create_shipment_receipt
- is_voice_enabled
- FeedbackTests
- test_knowledge.py
- Skill: Local LLM runtime (Ollama / Anthropic / Google)
- Contributor Covenant Code of Conduct
- Graph Report - erp_ai  (2026-09-19)
- TestChatRouteSmoke
- Still to do
- AIAssistantAction
- _bind_test_context
- TestFailureInjection
- test_flows_e2e.py
- [Unreleased]
- Contributing to ERP AI
- _validate_query
- get_source
- TestDraftWorkflowSchemas
- 🩻 Troubleshooting
- ERP AI — Local AI Assistant for ERPNext (MIT)
- tasks.py
- parse_number
- TestRouteWhitelistContract
- UPGRADE
- README.md
- _fallback_to_llm
- run_evaluation
- check_freshness
- ai_settings.js
- RecordTests
- TestEndpointGuards
- bug_report.md
- 🔌 API reference (all `@frappe.whitelist`)
- mcp/__init__.py
- ERP AI — versions & milestones
- Skills index
- 2026-09-19/manifest.json
- graphify-audit/manifest.json
- get_missing_fields
- AIHelpArticle
- detect_intent
- ci_seed.py
- DraftHelpTests
- feature_request.md
- 🚀 Quick start
- CODE_OF_CONDUCT.md
- CONTRIBUTING.md
- erp_ai/api.py
- erp_ai/attachments.py
- erp_ai/barcode.py
- erp_ai/conversation.py
- erp_ai/draft_workflow.py
- erp_ai/erp_ai/doctype/ai_assistant_action/ai_assistant_action.json
- erp_ai/erp_ai/doctype/ai_assistant_action/ai_assistant_action.py
- erp_ai/erp_ai/doctype/ai_assistant_action/__init__.py
- erp_ai/erp_ai/doctype/ai_behavior_pattern/ai_behavior_pattern.json
- erp_ai/erp_ai/doctype/ai_behavior_pattern/ai_behavior_pattern.py
- erp_ai/erp_ai/doctype/ai_chat_message/ai_chat_message.json
- erp_ai/erp_ai/doctype/ai_chat_message/ai_chat_message.py
- erp_ai/erp_ai/doctype/ai_chat_message/__init__.py
- erp_ai/erp_ai/doctype/ai_help_article/ai_help_article.json
- erp_ai/erp_ai/doctype/ai_help_article/ai_help_article.py
- erp_ai/erp_ai/doctype/ai_help_article/__init__.py
- erp_ai/erp_ai/doctype/ai_settings/ai_settings.json
- erp_ai/erp_ai/doctype/ai_settings/ai_settings.py
- erp_ai/erp_ai/doctype/ai_user_behavior/ai_user_behavior.json
- erp_ai/erp_ai/doctype/ai_user_behavior/ai_user_behavior.py
- erp_ai/erp_ai/__init__.py
- erp_ai/erp_ai/page/ai_assistant/ai_assistant.js
- erp_ai/erp_ai/page/ai_assistant/ai_assistant.json
- erp_ai/erp_ai/page/ai_assistant/__init__.py
- erp_ai/erp_ai/workspace/ai_assistant_hub/ai_assistant_hub.json
- erp_ai/erp_tools.py
- erp_ai/evaluation.py
- erp_ai/handlers/formatters.py
- erp_ai/handlers/__init__.py
- erp_ai/help/articles.py
- erp_ai/help/__init__.py
- erp_ai/help/seed_articles.py
- erp_ai/hooks.py
- erp_ai/idempotency.py
- erp_ai/__init__.py
- erp_ai/install.py
- erp_ai/intents/__init__.py
- erp_ai/knowledge/erpnext_kb.py
- erp_ai/knowledge/sources.py
- erp_ai/llm/__init__.py
- erp_ai/mcp/__init__.py
- erp_ai/mcp/server.py
- erp_ai/modules.txt
- erp_ai/patches/__init__.py
- erp_ai/patches/normalize_llm_provider.py
- erp_ai/public/js/ai_settings.js
- erp_ai/public/js/ai_widget.js
- erp_ai/questions/__init__.py
- erp_ai/rbac/__init__.py
- erp_ai/safety/__init__.py
- erp_ai/schema/__init__.py
- erp_ai/tasks.py
- erp_ai/templates/__init__.py
- erp_ai/templates/pages/__init__.py
- erp_ai/tests/ci_seed.py
- erp_ai/tests/__init__.py
- erp_ai/tests/test_ai_user_behavior.py
- erp_ai/tests/test_core.py
- erp_ai/tests/test_erp_ai_security.py
- erp_ai/tests/test_frappe_integration.py
- erp_ai/tests/test_infra.py
- erp_ai/tests/test_knowledge.py
- erp_ai/tests/test_rbac.py
- erp_ai/tests/test_security.py
- erp_ai/validators/__init__.py
- erp_ai/voice/__init__.py
- erp_ai/voice/setup_voice.sh
- erp_ai/voice/toggle.py
- erp_ai/workflows/__init__.py
- erp_ai/workflows/shipment.py
- erp_ai/workflows/stock_issue.py
- .github/workflows/ci.yml
- .pre-commit-config.yaml
- pyproject.toml
- README.md
- RELEASE_NOTES.md
- scripts/sync_workspace.py
- SECURITY.md
- CODE_OF_CONDUCT.md
- CONTRIBUTING.md
- erp_ai/api.py
- erp_ai/attachments.py
- erp_ai/barcode.py
- erp_ai/conversation.py
- erp_ai/draft_workflow.py
- erp_ai/erp_ai/doctype/ai_assistant_action/ai_assistant_action.json
- erp_ai/erp_ai/doctype/ai_assistant_action/ai_assistant_action.py
- erp_ai/erp_ai/doctype/ai_assistant_action/__init__.py
- erp_ai/erp_ai/doctype/ai_behavior_pattern/ai_behavior_pattern.json
- erp_ai/erp_ai/doctype/ai_behavior_pattern/ai_behavior_pattern.py
- erp_ai/erp_ai/doctype/ai_chat_message/ai_chat_message.json
- erp_ai/erp_ai/doctype/ai_chat_message/ai_chat_message.py
- erp_ai/erp_ai/doctype/ai_chat_message/__init__.py
- erp_ai/erp_ai/doctype/ai_help_article/ai_help_article.json
- erp_ai/erp_ai/doctype/ai_help_article/ai_help_article.py
- erp_ai/erp_ai/doctype/ai_help_article/__init__.py
- erp_ai/erp_ai/doctype/ai_settings/ai_settings.json
- erp_ai/erp_ai/doctype/ai_settings/ai_settings.py
- erp_ai/erp_ai/doctype/ai_user_behavior/ai_user_behavior.json
- erp_ai/erp_ai/doctype/ai_user_behavior/ai_user_behavior.py
- erp_ai/erp_ai/__init__.py
- erp_ai/erp_ai/page/ai_assistant/ai_assistant.js
- erp_ai/erp_ai/page/ai_assistant/ai_assistant.json
- erp_ai/erp_ai/page/ai_assistant/__init__.py
- erp_ai/erp_ai/workspace/ai_assistant_hub/ai_assistant_hub.json
- erp_ai/erp_tools.py
- erp_ai/evaluation.py
- erp_ai/handlers/formatters.py
- erp_ai/handlers/__init__.py
- erp_ai/help/articles.py
- erp_ai/help/__init__.py
- erp_ai/help/seed_articles.py
- erp_ai/hooks.py
- erp_ai/idempotency.py
- erp_ai/__init__.py
- erp_ai/install.py
- erp_ai/intents/__init__.py
- erp_ai/knowledge/erpnext_kb.py
- erp_ai/knowledge/sources.py
- erp_ai/llm/__init__.py
- erp_ai/mcp/__init__.py
- erp_ai/mcp/server.py
- erp_ai/modules.txt
- erp_ai/patches/__init__.py
- erp_ai/patches/normalize_llm_provider.py
- erp_ai/public/js/ai_settings.js
- erp_ai/public/js/ai_widget.js
- erp_ai/questions/__init__.py
- erp_ai/rbac/__init__.py
- erp_ai/safety/__init__.py
- erp_ai/schema/__init__.py
- erp_ai/tasks.py
- erp_ai/templates/__init__.py
- erp_ai/templates/pages/__init__.py
- erp_ai/tests/ci_seed.py
- erp_ai/tests/__init__.py
- erp_ai/tests/test_ai_user_behavior.py
- erp_ai/tests/test_core.py
- erp_ai/tests/test_erp_ai_security.py
- erp_ai/tests/test_frappe_integration.py
- erp_ai/tests/test_infra.py
- erp_ai/tests/test_knowledge.py
- erp_ai/tests/test_rbac.py
- erp_ai/tests/test_security.py
- erp_ai/validators/__init__.py
- erp_ai/voice/__init__.py
- erp_ai/voice/setup_voice.sh
- erp_ai/voice/toggle.py
- erp_ai/workflows/__init__.py
- erp_ai/workflows/shipment.py
- erp_ai/workflows/stock_issue.py
- .github/workflows/ci.yml
- .pre-commit-config.yaml
- pyproject.toml
- README.md
- RELEASE_NOTES.md
- scripts/sync_workspace.py
- SECURITY.md
- run_evaluation
- AIBehaviorPattern
- AISettings
- check_commit_msg.py
- 🧪 Testing
- LLMProvider
- refresh_behavior_patterns
- ai_assistant.js
- voice_stage_budget
- 💬 Usage
- Phase 1 — Production-relevant robustness
- Current runtime (as of 2026-09-19)
- cleanup_temp_files
- AIChatMessage
- AIUserBehavior
- normalize_llm_provider.py
- .test_mcp_update_document_respects_document_level_scope
- Phase 2 — Voice & latency robustness
- Phase 3 — Flow-level e2e tests in CI
- sync_workspace.py
- test_schema_single_source
- test_doctype_mapping_employee
- test_find_by_tag
- setup_voice.sh
- erp_ai

## God Nodes (most connected - your core abstractions)
1. `Communities (90 total, 10 thin omitted)` - 68 edges
2. `FrappeMCP` - 53 edges
3. `confirm_draft()` - 35 edges
4. `create_draft()` - 32 edges
5. `_fetch()` - 32 edges
6. `TestQueryPermissionScoping` - 29 edges
7. `log_error_safely()` - 27 edges
8. `ask_llm()` - 21 edges
9. `validate_field()` - 21 edges
10. `_SkipIfNoDB` - 19 edges

## Surprising Connections (you probably didn't know these)
- `capabilities()` --uses--> `FrappeMCP`  [INFERRED]
  erp_ai/api.py → erp_ai/mcp/server.py
- `mcp_list_tools()` --uses--> `FrappeMCP`  [INFERRED]
  erp_ai/mcp/__init__.py → erp_ai/mcp/server.py
- `mcp_call_tool()` --uses--> `FrappeMCP`  [INFERRED]
  erp_ai/mcp/__init__.py → erp_ai/mcp/server.py
- `TestQueryPermissionScoping` --uses--> `FrappeMCP`  [INFERRED]
  erp_ai/tests/test_erp_ai_security.py → erp_ai/mcp/server.py
- `TestStockIssueNL` --uses--> `FrappeMCP`  [INFERRED]
  erp_ai/tests/test_erp_ai_security.py → erp_ai/mcp/server.py

## Import Cycles
- None detected.

## Communities (290 total, 13 thin omitted)

### Community 0 - "Communities (90 total, 10 thin omitted)"
Cohesion: 0.03
Nodes (68): Communities (90 total, 10 thin omitted), Community 0 - "AI Action Audit", Community 10 - "Tool Execution Engine", Community 11 - "Draft Persistence", Community 12 - "Row-Level Security", Community 13 - "AI Behavior Tests", Community 14 - "File and Voice Cleanup", Community 15 - "ERP Data Tools" (+60 more)

### Community 1 - "erp_tools.py"
Cohesion: 0.04
Nodes (59): _operator_snapshot(), Live site counts the model can quote without a tool call. Best-effort., _count(), _fetch(), _first(), get_available_tools(), get_companies(), get_company_details() (+51 more)

### Community 2 - "audit.py"
Cohesion: 0.05
Nodes (32): _compute_preview_hash(), create_audit_record(), Any, Mark an action as completed with the full result payload. Stores the actual…, Mark an action as failed with error reason and optional rollback reference., Verify the proposed data hasn't changed since the preview was shown., Compute a stable hash of proposed changes for integrity verification., Create a pending AI Assistant Action record for audit. (+24 more)

### Community 3 - "api.py"
Cohesion: 0.06
Nodes (48): _aggregate(), audit_history(), capabilities(), _count(), _data_answer(), _get_ollama_base_url(), _handle_view_intent(), _list_anthropic_models() (+40 more)

### Community 4 - "ask_llm"
Cohesion: 0.08
Nodes (42): _assistant_reply(), health(), _llm_runtime_available(), _llm_unavailable_reply(), Best-effort probe: can the configured LLM provider be reached? For the local…, Lightweight app health check: configured LLM provider + voice runtime. Phase…, Shared core of the chat endpoints: deterministic data answers first, then the…, Clean, user-facing degraded-state message for an unreachable LLM. (+34 more)

### Community 5 - "create_draft"
Cohesion: 0.06
Nodes (29): create_draft(), generate_preview_hash(), _get_action(), get_draft(), _normalize_draft_data(), Get pending action from AI Assistant Action DocType. Returns a dict for the…, Resolve an AI Assistant Action, or None. Exactly one of ``action_id`` or…, Move a superseded pending action into the terminal ``cancelled`` state.… (+21 more)

### Community 6 - "whitelist"
Cohesion: 0.06
Nodes (38): ask(), ask_v2(), ask_v2_with_voice(), ask_with_doc(), cancel_pending_action(), cancel_workflow_action(), chat(), citation_for() (+30 more)

### Community 7 - "conversation.py"
Cohesion: 0.11
Nodes (34): apply_answer(), _ask_next(), clear_guided(), guided_answer(), guided_ready_again(), guided_start(), _keep(), load_guided() (+26 more)

### Community 8 - "test_rbac.py"
Cohesion: 0.06
Nodes (32): _Doc, _Meta, Administrator has no limit., Stock User has a limit., Auditor has zero limit (read-only)., Verify supervisor requirement data., Verify department restriction data., Admin has no restrictions. (+24 more)

### Community 9 - "rbac/__init__.py"
Cohesion: 0.09
Nodes (34): check_my_permission(), my_permissions(), Return the current user's roles and allowed doctypes., Check if the current user can perform an action on a doctype., _action_to_level(), apply_department_filters(), can(), can_cancel() (+26 more)

### Community 10 - "draft_workflow.py"
Cohesion: 0.09
Nodes (31): convert_uom(), _create_customer_doc(), create_document_from_draft(), _create_generic_doc(), _create_item_doc(), _create_payment_entry_doc(), _create_purchase_invoice_doc(), _create_purchase_receipt_doc() (+23 more)

### Community 11 - "test_erp_ai_security.py"
Cohesion: 0.09
Nodes (20): Return an error message if data is missing live-mandatory fields, else None.…, _validate_required_fields(), _has_real_db(), ERP AI Security & Workflow Tests These tests verify Phase 1-4 improvements: -…, Audit point 7: required-field validation runs against live metadata (so Custom…, Site-agnostic: whatever this site's live meta demands (incl. Custom Fields), a…, Audit point 7: the natural-language issue path was structurally broken — it…, Return True if a real, DB-backed Frappe site context is available. When the… (+12 more)

### Community 12 - "ERP AI Release Notes - LLM Provider Multi-Support & Admin Settings"
Cohesion: 0.06
Nodes (31): 1. Multi-LLM Provider Support, 2. Admin Settings UI, 3. Provider-Specific Settings, Added, Admin Master Toggle (Speaker Enabled), API Layer, Changed, Configuration Examples (+23 more)

### Community 13 - "voice/__init__.py"
Cohesion: 0.09
Nodes (29): A hung decoder must not hang the worker and must not leak the upload., An unprovisioned runtime is reported as a clean, actionable list., With the runtime present and ffmpeg on PATH, availability is ok=True., _stub_frappe(), test_voice_rejects_bad_format_without_touching_disk(), test_voice_rejects_oversized_audio(), test_voice_rejects_oversized_tts(), test_voice_runtime_available_ok_when_provisioned() (+21 more)

### Community 14 - "FrappeMCP"
Cohesion: 0.11
Nodes (13): handle_stock_issue_nl_request(), Parse stock issue natural language request and return structured data. Parsing…, FrappeMCP, Get workspace details including shortcuts, links, and content blocks. Args:…, Test Phase 3 atomicity: single commit point in create_document_from_draft., create_document_from_draft should commit once at the end., Audit point 6: by-name document access must enforce the document-level (User…, doctype-level check True; doc-level check per ``doc_level_allowed``. (+5 more)

### Community 15 - "test_core.py"
Cohesion: 0.12
Nodes (24): auto_confirm_reply(), is_affirmative(), is_negative(), Return True when the reply is a clear negative / cancel / not-now. Used to stop…, Classify a guided-flow reply for the auto-confirm gate. Returns one of: -…, Drop obvious framing punctuation so "yes," / "yeah!" / "yep." still match., Return True when the user's reply is a clear affirmative. The check is…, _strip_yes_no_context() (+16 more)

### Community 16 - "articles.py"
Cohesion: 0.09
Nodes (25): help_get_article(), help_get_categories(), help_get_quick_actions(), help_search(), Return help article categories., Return quick-action cards., Return a single help article., Search help articles by query string. (+17 more)

### Community 17 - "test_infra.py"
Cohesion: 0.12
Nodes (27): Detect MIME type from file magic bytes (first 16 bytes)., Validate file type, size, MIME, and magic-byte signature. Returns error message…, _sniff_mime(), validate_file(), generate_idempotency_key(), Generate a deterministic idempotency key from operation parameters., _load_commit_msg_checker(), Every subprocess call in the voice stack must pass ``timeout=``. (+19 more)

### Community 18 - "TestPhase4EntityResolution"
Cohesion: 0.08
Nodes (20): clarification_needed(), pick_candidate(), Permission-aware read used by entity resolution.…, Resolve an item name/code to ERPNext Item records. Tries exact code match…, Resolve a customer/supplier name to ERPNext party records. doctype: 'Customer'…, Return a human-readable candidate list string for the user to choose from.…, Return a clarification question string if the intent is ambiguous or critical…, resolve_item() (+12 more)

### Community 19 - "test_security.py"
Cohesion: 0.10
Nodes (26): test_validate_empty_string(), test_validate_numeric_field(), test_validate_numeric_invalid(), test_validate_numeric_with_commas(), test_validate_string_field(), SQL-like injection in prompts should not crash validators., Script tags in input should be treated as invalid data., Extremely long input should not crash the system. (+18 more)

### Community 20 - "attachments.py"
Cohesion: 0.12
Nodes (24): ocr_extract_text(), Extract text from an uploaded File (image/PDF) using OCR. Accepts the URL of a…, _ensure_base_dir(), extract_text_from_file(), extract_text_from_image(), extract_text_from_pdf(), _is_within(), parse_invoice_from_text() (+16 more)

### Community 21 - "check_illegal_operation"
Cohesion: 0.08
Nodes (24): check_illegal_operation(), get_duplication_fields(), Return fields to check for duplicates before creating., Return error message if the prompt describes an illegal operation, else None., test_duplication_fields(), test_illegal_operation_blocked(), test_illegal_operation_modify_submitted(), test_legal_operation_passes() (+16 more)

### Community 22 - "Architecture"
Cohesion: 0.08
Nodes (23): 1. User-facing surfaces, 2. The API layer (the loaded core), 3.1 LLM integration, 3.2 Voice, 3.3 Audit and draft persistence, 3.4 Knowledge and citations, 3.5 Guided conversation, 3.6 Tool execution engine (+15 more)

### Community 23 - "install.py"
Cohesion: 0.13
Nodes (22): _available_workspace_links(), Create the AI Assistant Hub workspace from the bundled JSON spec. Requires…, Keep fixture links that exist on this site's installed apps. ERPNext…, Public entry point for install-time hook and manual refresh. Reads the bundled…, setup_workspace(), sync_workspace_from_json(), Seed all help articles into the database., seed_all() (+14 more)

### Community 24 - "check_permission"
Cohesion: 0.13
Nodes (23): _extract_amount(), _extract_fields_for(), _handle_create_intent(), Extract the first plausible currency amount from free text., extract_invoice_fields(), extract_item_fields(), extract_party_fields(), Extract item fields from natural language with UOM support. (+15 more)

### Community 25 - "execute_erp_tool"
Cohesion: 0.12
Nodes (11): call_erp_tool(), execute_erp_tool(), Execute an ERP tool by name with given parameters. Args: tool_name: Name of the…, Execute an ERP tool and return result., P0 #4/#6/#8: the operator tool registry is not an authorization bypass.…, A create tool returns None when the draft is rejected (no permission,…, A read tool answering "no data" is not a failure, so the new check must stay…, A model-invented name must not resolve to a privileged helper. (+3 more)

### Community 26 - "_log_tool_error"
Cohesion: 0.15
Nodes (15): create_customer(), create_draft_for_review(), create_item(), create_sales_order(), create_supplier(), _log_tool_error(), Create a new item. Args: item_code: Unique item code item_name: Item name…, Create a new customer. Args: customer_name: Customer name customer_group:… (+7 more)

### Community 27 - "test_frappe_integration.py"
Cohesion: 0.16
Nodes (12): check_idempotency(), claim_idempotency(), Any, Check if an operation with this key was already completed or is in progress.…, Claim an idempotency key for an operation about to be performed. Race-safe: the…, Frappe-backed integration tests: idempotency, audit confirmation security,…, A pending action must prevent a fresh claim on the same key., A completed action must still block a fresh claim on the same key. (+4 more)

### Community 28 - "KnowledgeSource"
Cohesion: 0.12
Nodes (16): KnowledgeSource, Any, A single knowledge source with metadata., Check if the source is fresh (updated within max_days)., Return a human-readable citation., Machine-verifiable citation metadata. Every field a reviewer needs to confirm…, A stale source's human citation must carry the stale warning., Excerpts in verifiable citations are capped at 200 chars. (+8 more)

### Community 29 - "FrappeTestCase"
Cohesion: 0.12
Nodes (10): _FakeMCP, FrappeTestCase, Shipment draft -> confirm flow via the public API, plus cancel semantics. These…, Master data created mid-workflow must roll back when the receipt fails., Returns success for supplier/item creation, failure for receipts., Every schema doctype must exist in live metadata with its required fields.…, NCR is not a stock v15 doctype; the registry must not reference it., TestLiveDocTypeMetadata (+2 more)

### Community 30 - "_ean13_checksum"
Cohesion: 0.12
Nodes (17): _ean13_checksum(), generate_item_barcode_data(), Validate EAN-13 checksum digit., Validate UPC-A checksum digit., Validate a barcode format with checksum verification., Generate barcode data for an item (for label printing)., _upc_checksum(), validate_barcode_format() (+9 more)

### Community 31 - "ai_user_behavior.py"
Cohesion: 0.14
Nodes (16): apply_feedback(), get_org_patterns(), _group(), _live_block(), on_update(), _pattern_block(), prompt_block(), Render the prompt block from a live aggregate of the event log. (+8 more)

### Community 32 - "ai_widget.js"
Cohesion: 0.22
Nodes (16): addMsg(), addTyping(), bubble(), buildWidget(), doSend(), buildWorkspaceChat(), add(), askDirect() (+8 more)

### Community 33 - "_import_llm"
Cohesion: 0.16
Nodes (15): _fake_response(), _import_llm(), Minimal AI Settings stand-in: attribute access plus ``.get()``. Numeric knobs…, Import erp_ai.llm without frappe, with a throw that actually raises. The CI…, Shipped defaults stay valid: the doctype default is the Select's label form…, The settings form's api_key/llm_model must reach the wire. The runtime used to…, _Settings, test_ask_llm_sends_form_configured_key_and_model() (+7 more)

### Community 34 - "log_error_safely"
Cohesion: 0.15
Nodes (10): _classify_retryable(), log_error_safely(), Heuristic retryable-vs-fatal classification for AI action failures. Transient…, Log an error without letting the logging call mask the original failure.…, Regression: ``frappe.log_error`` takes the TITLE first and Error Log caps the…, Phase 1.3: context + retryable flag land in the log entry as machine-readable…, Passing the exception as ``retryable`` classifies by type: timeout/connection…, TestErrorLoggingNeverMasksFailures (+2 more)

### Community 35 - "confirm_draft"
Cohesion: 0.20
Nodes (8): _claim_action(), confirm_draft(), Atomically transition a pending AI Assistant Action to ``processing``. The…, Confirm (create) a pending operation using the AI Assistant Action store. The…, confirm_draft must verify ownership, nonce, expiry, status, preview hash., Item has no site-custom mandatory fields, so confirmations succeed…, Fields made mandatory by another app (e.g. tax NTN/CNIC) get a clear listable…, TestAuditConfirmationSecurity

### Community 36 - "detect_intent"
Cohesion: 0.16
Nodes (10): detect_intent(), Test intent detection and DOCTYPE mapping., Should detect item creation intent., Should detect sales invoice intent., Should detect purchase invoice intent., Should detect customer creation intent., Should detect supplier creation intent., Should detect payment entry intent. (+2 more)

### Community 38 - "._draft"
Cohesion: 0.17
Nodes (7): Phase 4.2: the action row is evidence — identity fields are write-once and a…, Re-pointing a confirmable draft at another nonce/session/expiry must be…, A finished action is an immutable audit record: no field may change after the…, The row carries which model produced the draft and the user's raw request text…, Phase 4.2: an admin can list stuck drafts and retire them., TestAdminActionInbox, TestAuditImmutability

### Community 39 - "find_sources_by_doctype"
Cohesion: 0.16
Nodes (14): find_sources_by_doctype(), find_sources_by_tag(), get_citation_for_doctype(), get_citation_metadata_for_doctype(), Find all sources matching a tag., Map a doctype to relevant knowledge sources., Get a citation string for a doctype., Machine-verifiable citation metadata for a doctype's primary source. Returns… (+6 more)

### Community 40 - "schema/__init__.py"
Cohesion: 0.16
Nodes (13): get_question(), Return the natural language question for a field., get_child_table(), get_label(), get_optional_fields(), get_required_fields(), get_schema(), Any (+5 more)

### Community 41 - "TestGenericDepartmentExecution"
Cohesion: 0.16
Nodes (6): Registry doctypes beyond the six bespoke builders must be executable through…, Common affirmative phrasings all auto-confirm the ready draft., A clear negative while in ready state does NOT confirm; the flow is stopped and…, An expired ready action must not be auto-confirmed; the user gets a clear…, If MCP raises mid-execution, no document is persisted and the action is marked…, TestGenericDepartmentExecution

### Community 42 - "ERP AI — Development Phases & Improvement Roadmap"
Cohesion: 0.13
Nodes (15): 4.1 Multi-model routing with capability tags + fallback, 4.2 Idempotency + draft nonce hardening (finish the last 20%), 4.3 Row-level / operator scoping resilience tests, 5.1 One maintained internal knowledge graph, 5.2 Remove doc drift, Current status (as of this writing), ERP AI — Development Phases & Improvement Roadmap, How to propose a change to this roadmap (+7 more)

### Community 43 - "resolve_barcode"
Cohesion: 0.15
Nodes (8): barcode_lookup(), Resolve a scanned barcode/QR to an ERP document (permission-checked)., Any, Resolve a scanned barcode/QR to an ERPNext document. Order: 1. Item Barcode…, resolve_barcode(), The new whitelisted infrastructure endpoints behave correctly., The citation must be verifiable: source id resolves in the registry, url…, TestInfrastructureEndpoints

### Community 44 - "create_shipment_receipt"
Cohesion: 0.18
Nodes (13): handle_shipment_nl_request(), Record an incoming shipment via preview -> confirm flow. This endpoint no…, Parse shipment natural language request and return structured data. Parsing is…, Save a shipment draft for later confirmation. Persisted only through the…, save_shipment_draft(), workflow_shipment_receipt(), Resolve a warehouse for a workflow: explicit hint, then site defaults. Order: a…, resolve_warehouse() (+5 more)

### Community 45 - "is_voice_enabled"
Cohesion: 0.18
Nodes (12): Get current voice on/off status for the user., Toggle voice on/off. Returns new state., Explicitly set voice on/off., voice_set(), voice_status(), voice_toggle(), is_voice_enabled(), Return True if voice output is enabled for the user. Checks (in order): 1.… (+4 more)

### Community 46 - "FeedbackTests"
Cohesion: 0.15
Nodes (4): FeedbackTests, PatternTests, Self-checks for the AI User Behavior learning log (mocked, no site needed). Run…, apply_feedback: thumbs-down marks the last turn corrected; up is a no-op.

### Community 47 - "test_knowledge.py"
Cohesion: 0.15
Nodes (12): Work Order should map to manufacturing sources., Unknown doctypes get no citation — never an invented one., Sources registry should have entries., Should find quality sources for Quality Inspection., Should find maintenance sources for Asset., Unknown doctype should return generic citation., test_citation_metadata_unknown_doctype_is_none(), test_citation_unknown_doctype() (+4 more)

### Community 48 - "Skill: Local LLM runtime (Ollama / Anthropic / Google)"
Cohesion: 0.15
Nodes (13): Auto-confirm on affirmative reply (ROADMAP Phase 1), Completed robustness work (ROADMAP Phase 1.1), External references, External references, How to test LLM robustness, Keep this skill current, Keep this skill current, Multi-model routing (ROADMAP Phase 4.1 — deferred) (+5 more)

### Community 49 - "Contributor Covenant Code of Conduct"
Cohesion: 0.17
Nodes (12): 1. Correction, 2. Warning, 3. Temporary ban, 4. Permanent ban, Attribution, Contributor Covenant Code of Conduct, Enforcement, Enforcement guidelines (+4 more)

### Community 50 - "Graph Report - erp_ai  (2026-09-19)"
Cohesion: 0.17
Nodes (11): Community Hubs (Navigation), Corpus Check, God Nodes (most connected - your core abstractions), Graph Freshness, Graph Report - erp_ai  (2026-09-19), Hyperedges (group relationships), Import Cycles, Knowledge Gaps (+3 more)

### Community 51 - "TestChatRouteSmoke"
Cohesion: 0.17
Nodes (4): P0 regression (fresh release audit): after the chat-dispatch refactor the chat…, Phase 2.1: a broken TTS stage must never fail the turn — the text answer…, A failed filtered count must answer nothing, not leak the unfiltered total…, TestChatRouteSmoke

### Community 52 - "Still to do"
Cohesion: 0.17
Nodes (11): Done today (commit pending), ERP AI — In-progress work tracker, Phase 1 — Production-relevant robustness — ✅ DONE, Phase 2 — Voice & latency robustness — ✅ DONE, Phase 3 — Flow-level e2e tests in CI — ✅ DONE, Phase 3 — Flow-level e2e tests in CI (not started), Phase 4 — Scale / multi-model / multi-user (deferred), Phase 4 — Scale / multi-model / multi-user (deferred) (+3 more)

### Community 53 - "AIAssistantAction"
Cohesion: 0.20
Nodes (4): AIAssistantAction, Document, Enforce the one-way lifecycle and the immutable audit identity. Reviving a…, Field names whose value differs from the stored document.

### Community 55 - "TestFailureInjection"
Cohesion: 0.18
Nodes (6): Phase 4.3: degraded states must be visible and clean — never fabricated, never…, Ollama down must answer with a clear service message, not a 500., A hung LLM is retryable: clean message + retryable class in the log., A broken query path must produce NO answer rather than a made-up total: the…, Stale knowledge is flagged for reindex, not silently served as fresh — the…, TestFailureInjection

### Community 56 - "test_flows_e2e.py"
Cohesion: 0.27
Nodes (7): FrappeTestCase, Flow-level end-to-end tests (Phase 3.1). These assert the *user-visible*…, The guided flow end to end: ask -> answer -> ready -> create., Draft -> confirm end to end, including idempotent re-confirm., TestDraftConfirmFlow, TestGuidedConversationFlow, _uniq()

### Community 57 - "[Unreleased]"
Cohesion: 0.20
Nodes (9): [0.1.0] - 2025-09-23, Added, Added, Changed, Changed, CHANGELOG, Fixed, Removed (+1 more)

### Community 58 - "Contributing to ERP AI"
Cohesion: 0.20
Nodes (10): Branch strategy, Code of conduct, Coding standards, Contributing to ERP AI, How to get the code, Pull requests, Release process, Security and sensitive data (+2 more)

### Community 59 - "_validate_query"
Cohesion: 0.20
Nodes (8): _column_of(), Return an error message if the query names something invalid, else None.…, Return the underlying column name: 'count(name) as total' -> 'name'., Reject an unknown filter field or an unsupported operator, else None., _validate_filter_dict(), _validate_query(), ``count(name) as total`` must pass validation (the audit helpers rely on it)…, A site without ERPNext has no metadata for business DocTypes; the tools must…

### Community 60 - "get_source"
Cohesion: 0.20
Nodes (10): get_source(), Return a knowledge source by ID., A citation returned for a doctype must point at a source that actually exists…, Should retrieve a known source., Should return None for unknown source., Source freshness check should work., test_citation_metadata_is_verifiable(), test_get_source_exists() (+2 more)

### Community 61 - "TestDraftWorkflowSchemas"
Cohesion: 0.20
Nodes (6): Test DOCTYPE schemas and preview generation., Item schema should exist., Sales Invoice schema should exist., Should generate item preview., Should generate sales invoice preview., TestDraftWorkflowSchemas

### Community 62 - "🩻 Troubleshooting"
Cohesion: 0.20
Nodes (10): AI answers wrong/old data, Assets / build issues, Chat / widget not appearing on the workspace, Common error references, Degraded states (what the assistant does when a dependency is down), Drafts not confirming, Python errors in the app, 🩻 Troubleshooting (+2 more)

### Community 63 - "ERP AI — Local AI Assistant for ERPNext (MIT)"
Cohesion: 0.20
Nodes (10): 🤝 Compatibility, ⚙️ Configuration, 📚 Docs / collaboration, ERP AI — Local AI Assistant for ERPNext (MIT), 📄 License, 🧹 Maintenance, 📦 Project structure, 🖥 Reference deployment (example — this server) (+2 more)

### Community 64 - "tasks.py"
Cohesion: 0.25
Nodes (8): cleanup_expired_actions(), _close_action(), draft_help_for_repeated_failures(), expire_stale_actions(), Hourly: expire unconfirmed drafts and reclaim abandoned claims. Two stale…, Daily: turn repeatedly-failing intents into INACTIVE help-article drafts.…, Move one action into a terminal state; returns False if it was skipped. Per-row…, Daily: delete closed actions older than ``days``. Only terminal, already-…

### Community 65 - "parse_number"
Cohesion: 0.22
Nodes (8): test_is_numeric(), test_parse_number_with_currency(), Unicode digits should not crash parser., test_parse_number_unicode(), is_numeric(), parse_number(), True if the field must be a number., Parse a number from user text. Handles '1,200', 'rs 500', '500pk', etc.

### Community 66 - "TestRouteWhitelistContract"
Cohesion: 0.28
Nodes (4): P0 #2/#86: every public route must really be a public route. A dropped…, Routes are dispatched as ``frappe.call(fn, **frappe.form_dict)``…, Every endpoint the audit listed must exist and be importable., TestRouteWhitelistContract

### Community 67 - "UPGRADE"
Cohesion: 0.22
Nodes (9): After upgrading, Before you upgrade, Breaking changes, Questions, Rolling back, Seeding and default data, UPGRADE, Upgrading the app (+1 more)

### Community 68 - "README.md"
Cohesion: 0.29
Nodes (3): Hardened defaults, Reporting a vulnerability, Security model — what you should already know

### Community 69 - "_fallback_to_llm"
Cohesion: 0.25
Nodes (8): _fallback_to_llm(), _iter_json_objects(), _operator_system_prompt(), _parse_tool_call(), System prompt: operator role, callable tools, and live ERP state. Only read…, Yield each balanced-brace JSON object found in `text`. Tool-call parameters are…, Return (tool_name, parameters) if the reply is a valid tool call, else None., Answer via the LLM with live ERP data, executing read tool calls on request.…

### Community 70 - "run_evaluation"
Cohesion: 0.29
Nodes (7): EvalCase, EvalResult, Any, A single evaluation test case., Result of running an evaluation case., Run evaluation cases against a prompt-answering function., run_evaluation()

### Community 71 - "check_freshness"
Cohesion: 0.25
Nodes (8): check_freshness(), Check all sources for freshness. Returns a stale list, a fresh list, and the…, Freshness check should return all sources., check_freshness must expose a machine-readable reindex trigger., A custom max_days threshold must change what counts as stale., test_check_freshness_all(), test_check_freshness_reports_reindex_trigger(), test_check_freshness_threshold_respected()

### Community 72 - "ai_settings.js"
Cohesion: 0.46
Nodes (7): api_key(), custom_api_base_url(), llm_provider(), refresh(), toggle_api_key_field(), toggle_base_url_field(), update_model_dropdown()

### Community 74 - "TestEndpointGuards"
Cohesion: 0.29
Nodes (4): Audit point 5: privileged endpoints must not leak another user's data.…, A non-owner must not be able to OCR someone else's private upload., An unregistered file_url must be rejected, not read from disk., TestEndpointGuards

### Community 76 - "bug_report.md"
Cohesion: 0.25
Nodes (7): Actual behavior, Additional context, Describe the bug, Environment, Expected behavior, Logs, To Reproduce

### Community 77 - "🔌 API reference (all `@frappe.whitelist`)"
Cohesion: 0.25
Nodes (8): 🔌 API reference (all `@frappe.whitelist`), Chat / answers, Feedback / permissions / audit, Help & knowledge, Infrastructure / creation helpers, MCP tools (permission-checked document access), Voice, Workflow handlers

### Community 78 - "mcp/__init__.py"
Cohesion: 0.43
Nodes (6): mcp_call_tool(), mcp_list_tools(), whitelist, Return an error message if the RPC call is not allowed, else None., List available MCP tools., _rpc_denied()

### Community 79 - "ERP AI — versions & milestones"
Cohesion: 0.29
Nodes (7): Capabilities, Current version, ERP AI — versions & milestones, Future milestones, Notes, Post-release work (2026-09-19), v0.1.0 — initial release (2025-09-23)

### Community 80 - "Skills index"
Cohesion: 0.29
Nodes (6): How to add a new skill, How to use these files, Skill files, Skills index, What a skill.md file is, Why skills exist

### Community 81 - "2026-09-19/manifest.json"
Cohesion: 0.33
Nodes (5): erp_ai/audit.py, ast_hash, mtime, seen, semantic_hash

### Community 82 - "graphify-audit/manifest.json"
Cohesion: 0.33
Nodes (5): erp_ai/audit.py, ast_hash, mtime, seen, semantic_hash

### Community 83 - "get_missing_fields"
Cohesion: 0.33
Nodes (6): next_missing(), _pending_question(), Required fields still missing, in schema order., Next question to ask: a required field first, then a useful optional. Returns…, get_missing_fields(), Check which required fields are still missing/empty. A field is treated as…

### Community 84 - "AIHelpArticle"
Cohesion: 0.33
Nodes (3): AIHelpArticle, Document, Return example queries as a list.

### Community 85 - "detect_intent"
Cohesion: 0.33
Nodes (5): detect_intent(), Return (doctype, action) from natural language, or None if unclear., test_intent_detection_item(), test_intent_detection_none(), test_intent_detection_urdu()

### Community 86 - "ci_seed.py"
Cohesion: 0.53
Nodes (5): _insert_if_missing(), Seed the minimal ERPNext masters the Frappe-backed test suite assumes. A bare…, Insert when absent; return the existing/created document name., _root_group(), seed()

### Community 89 - "feature_request.md"
Cohesion: 0.33
Nodes (5): Additional context, Describe alternatives you've considered, Describe the solution you'd like, Is your feature request related to a problem?, Related

### Community 90 - "🚀 Quick start"
Cohesion: 0.33
Nodes (6): 1. Add the app to your bench, 2. Set up the workspace (embeds chat + help on the dashboard), 3. (Optional) Provision the voice stack, 4. Add LLM models in Ollama, 5. Rebuild assets & restart, 🚀 Quick start

### Community 91 - "CODE_OF_CONDUCT.md"
Cohesion: 0.40
Nodes (5): CODE_OF_CONDUCT.md, ast_hash, mtime, seen, semantic_hash

### Community 92 - "CONTRIBUTING.md"
Cohesion: 0.40
Nodes (5): CONTRIBUTING.md, ast_hash, mtime, seen, semantic_hash

### Community 93 - "erp_ai/api.py"
Cohesion: 0.40
Nodes (5): erp_ai/api.py, ast_hash, mtime, seen, semantic_hash

### Community 94 - "erp_ai/attachments.py"
Cohesion: 0.40
Nodes (5): erp_ai/attachments.py, ast_hash, mtime, seen, semantic_hash

### Community 95 - "erp_ai/barcode.py"
Cohesion: 0.40
Nodes (5): erp_ai/barcode.py, ast_hash, mtime, seen, semantic_hash

### Community 96 - "erp_ai/conversation.py"
Cohesion: 0.40
Nodes (5): erp_ai/conversation.py, ast_hash, mtime, seen, semantic_hash

### Community 97 - "erp_ai/draft_workflow.py"
Cohesion: 0.40
Nodes (5): erp_ai/draft_workflow.py, ast_hash, mtime, seen, semantic_hash

### Community 98 - "erp_ai/erp_ai/doctype/ai_assistant_action/ai_assistant_action.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_assistant_action/ai_assistant_action.json, ast_hash, mtime, seen, semantic_hash

### Community 99 - "erp_ai/erp_ai/doctype/ai_assistant_action/ai_assistant_action.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_assistant_action/ai_assistant_action.py, ast_hash, mtime, seen, semantic_hash

### Community 100 - "erp_ai/erp_ai/doctype/ai_assistant_action/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_assistant_action/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 101 - "erp_ai/erp_ai/doctype/ai_behavior_pattern/ai_behavior_pattern.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_behavior_pattern/ai_behavior_pattern.json, ast_hash, mtime, seen, semantic_hash

### Community 102 - "erp_ai/erp_ai/doctype/ai_behavior_pattern/ai_behavior_pattern.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_behavior_pattern/ai_behavior_pattern.py, ast_hash, mtime, seen, semantic_hash

### Community 103 - "erp_ai/erp_ai/doctype/ai_chat_message/ai_chat_message.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_chat_message/ai_chat_message.json, ast_hash, mtime, seen, semantic_hash

### Community 104 - "erp_ai/erp_ai/doctype/ai_chat_message/ai_chat_message.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_chat_message/ai_chat_message.py, ast_hash, mtime, seen, semantic_hash

### Community 105 - "erp_ai/erp_ai/doctype/ai_chat_message/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_chat_message/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 106 - "erp_ai/erp_ai/doctype/ai_help_article/ai_help_article.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_help_article/ai_help_article.json, ast_hash, mtime, seen, semantic_hash

### Community 107 - "erp_ai/erp_ai/doctype/ai_help_article/ai_help_article.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_help_article/ai_help_article.py, ast_hash, mtime, seen, semantic_hash

### Community 108 - "erp_ai/erp_ai/doctype/ai_help_article/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_help_article/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 109 - "erp_ai/erp_ai/doctype/ai_settings/ai_settings.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_settings/ai_settings.json, ast_hash, mtime, seen, semantic_hash

### Community 110 - "erp_ai/erp_ai/doctype/ai_settings/ai_settings.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_settings/ai_settings.py, ast_hash, mtime, seen, semantic_hash

### Community 111 - "erp_ai/erp_ai/doctype/ai_user_behavior/ai_user_behavior.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_user_behavior/ai_user_behavior.json, ast_hash, mtime, seen, semantic_hash

### Community 112 - "erp_ai/erp_ai/doctype/ai_user_behavior/ai_user_behavior.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_user_behavior/ai_user_behavior.py, ast_hash, mtime, seen, semantic_hash

### Community 113 - "erp_ai/erp_ai/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 114 - "erp_ai/erp_ai/page/ai_assistant/ai_assistant.js"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/page/ai_assistant/ai_assistant.js, ast_hash, mtime, seen, semantic_hash

### Community 115 - "erp_ai/erp_ai/page/ai_assistant/ai_assistant.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/page/ai_assistant/ai_assistant.json, ast_hash, mtime, seen, semantic_hash

### Community 116 - "erp_ai/erp_ai/page/ai_assistant/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/page/ai_assistant/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 117 - "erp_ai/erp_ai/workspace/ai_assistant_hub/ai_assistant_hub.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/workspace/ai_assistant_hub/ai_assistant_hub.json, ast_hash, mtime, seen, semantic_hash

### Community 118 - "erp_ai/erp_tools.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_tools.py, ast_hash, mtime, seen, semantic_hash

### Community 119 - "erp_ai/evaluation.py"
Cohesion: 0.40
Nodes (5): erp_ai/evaluation.py, ast_hash, mtime, seen, semantic_hash

### Community 120 - "erp_ai/handlers/formatters.py"
Cohesion: 0.40
Nodes (5): erp_ai/handlers/formatters.py, ast_hash, mtime, seen, semantic_hash

### Community 121 - "erp_ai/handlers/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/handlers/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 122 - "erp_ai/help/articles.py"
Cohesion: 0.40
Nodes (5): erp_ai/help/articles.py, ast_hash, mtime, seen, semantic_hash

### Community 123 - "erp_ai/help/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/help/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 124 - "erp_ai/help/seed_articles.py"
Cohesion: 0.40
Nodes (5): erp_ai/help/seed_articles.py, ast_hash, mtime, seen, semantic_hash

### Community 125 - "erp_ai/hooks.py"
Cohesion: 0.40
Nodes (5): erp_ai/hooks.py, ast_hash, mtime, seen, semantic_hash

### Community 126 - "erp_ai/idempotency.py"
Cohesion: 0.40
Nodes (5): erp_ai/idempotency.py, ast_hash, mtime, seen, semantic_hash

### Community 127 - "erp_ai/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 128 - "erp_ai/install.py"
Cohesion: 0.40
Nodes (5): erp_ai/install.py, ast_hash, mtime, seen, semantic_hash

### Community 129 - "erp_ai/intents/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/intents/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 130 - "erp_ai/knowledge/erpnext_kb.py"
Cohesion: 0.40
Nodes (5): erp_ai/knowledge/erpnext_kb.py, ast_hash, mtime, seen, semantic_hash

### Community 131 - "erp_ai/knowledge/sources.py"
Cohesion: 0.40
Nodes (5): erp_ai/knowledge/sources.py, ast_hash, mtime, seen, semantic_hash

### Community 132 - "erp_ai/llm/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/llm/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 133 - "erp_ai/mcp/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/mcp/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 134 - "erp_ai/mcp/server.py"
Cohesion: 0.40
Nodes (5): erp_ai/mcp/server.py, ast_hash, mtime, seen, semantic_hash

### Community 135 - "erp_ai/modules.txt"
Cohesion: 0.40
Nodes (5): erp_ai/modules.txt, ast_hash, mtime, seen, semantic_hash

### Community 136 - "erp_ai/patches/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/patches/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 137 - "erp_ai/patches/normalize_llm_provider.py"
Cohesion: 0.40
Nodes (5): erp_ai/patches/normalize_llm_provider.py, ast_hash, mtime, seen, semantic_hash

### Community 138 - "erp_ai/public/js/ai_settings.js"
Cohesion: 0.40
Nodes (5): erp_ai/public/js/ai_settings.js, ast_hash, mtime, seen, semantic_hash

### Community 139 - "erp_ai/public/js/ai_widget.js"
Cohesion: 0.40
Nodes (5): erp_ai/public/js/ai_widget.js, ast_hash, mtime, seen, semantic_hash

### Community 140 - "erp_ai/questions/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/questions/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 141 - "erp_ai/rbac/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/rbac/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 142 - "erp_ai/safety/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/safety/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 143 - "erp_ai/schema/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/schema/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 144 - "erp_ai/tasks.py"
Cohesion: 0.40
Nodes (5): erp_ai/tasks.py, ast_hash, mtime, seen, semantic_hash

### Community 145 - "erp_ai/templates/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/templates/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 146 - "erp_ai/templates/pages/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/templates/pages/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 147 - "erp_ai/tests/ci_seed.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/ci_seed.py, ast_hash, mtime, seen, semantic_hash

### Community 148 - "erp_ai/tests/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 149 - "erp_ai/tests/test_ai_user_behavior.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_ai_user_behavior.py, ast_hash, mtime, seen, semantic_hash

### Community 150 - "erp_ai/tests/test_core.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_core.py, ast_hash, mtime, seen, semantic_hash

### Community 151 - "erp_ai/tests/test_erp_ai_security.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_erp_ai_security.py, ast_hash, mtime, seen, semantic_hash

### Community 152 - "erp_ai/tests/test_frappe_integration.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_frappe_integration.py, ast_hash, mtime, seen, semantic_hash

### Community 153 - "erp_ai/tests/test_infra.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_infra.py, ast_hash, mtime, seen, semantic_hash

### Community 154 - "erp_ai/tests/test_knowledge.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_knowledge.py, ast_hash, mtime, seen, semantic_hash

### Community 155 - "erp_ai/tests/test_rbac.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_rbac.py, ast_hash, mtime, seen, semantic_hash

### Community 156 - "erp_ai/tests/test_security.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_security.py, ast_hash, mtime, seen, semantic_hash

### Community 157 - "erp_ai/validators/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/validators/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 158 - "erp_ai/voice/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/voice/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 159 - "erp_ai/voice/setup_voice.sh"
Cohesion: 0.40
Nodes (5): erp_ai/voice/setup_voice.sh, ast_hash, mtime, seen, semantic_hash

### Community 160 - "erp_ai/voice/toggle.py"
Cohesion: 0.40
Nodes (5): erp_ai/voice/toggle.py, ast_hash, mtime, seen, semantic_hash

### Community 161 - "erp_ai/workflows/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/workflows/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 162 - "erp_ai/workflows/shipment.py"
Cohesion: 0.40
Nodes (5): erp_ai/workflows/shipment.py, ast_hash, mtime, seen, semantic_hash

### Community 163 - "erp_ai/workflows/stock_issue.py"
Cohesion: 0.40
Nodes (5): erp_ai/workflows/stock_issue.py, ast_hash, mtime, seen, semantic_hash

### Community 164 - ".github/workflows/ci.yml"
Cohesion: 0.40
Nodes (5): .github/workflows/ci.yml, ast_hash, mtime, seen, semantic_hash

### Community 165 - ".pre-commit-config.yaml"
Cohesion: 0.40
Nodes (5): .pre-commit-config.yaml, ast_hash, mtime, seen, semantic_hash

### Community 166 - "pyproject.toml"
Cohesion: 0.40
Nodes (5): pyproject.toml, ast_hash, mtime, seen, semantic_hash

### Community 167 - "README.md"
Cohesion: 0.40
Nodes (5): README.md, ast_hash, mtime, seen, semantic_hash

### Community 168 - "RELEASE_NOTES.md"
Cohesion: 0.40
Nodes (5): RELEASE_NOTES.md, ast_hash, mtime, seen, semantic_hash

### Community 169 - "scripts/sync_workspace.py"
Cohesion: 0.40
Nodes (5): scripts/sync_workspace.py, ast_hash, mtime, seen, semantic_hash

### Community 170 - "SECURITY.md"
Cohesion: 0.40
Nodes (5): SECURITY.md, ast_hash, mtime, seen, semantic_hash

### Community 171 - "CODE_OF_CONDUCT.md"
Cohesion: 0.40
Nodes (5): CODE_OF_CONDUCT.md, ast_hash, mtime, seen, semantic_hash

### Community 172 - "CONTRIBUTING.md"
Cohesion: 0.40
Nodes (5): CONTRIBUTING.md, ast_hash, mtime, seen, semantic_hash

### Community 173 - "erp_ai/api.py"
Cohesion: 0.40
Nodes (5): erp_ai/api.py, ast_hash, mtime, seen, semantic_hash

### Community 174 - "erp_ai/attachments.py"
Cohesion: 0.40
Nodes (5): erp_ai/attachments.py, ast_hash, mtime, seen, semantic_hash

### Community 175 - "erp_ai/barcode.py"
Cohesion: 0.40
Nodes (5): erp_ai/barcode.py, ast_hash, mtime, seen, semantic_hash

### Community 176 - "erp_ai/conversation.py"
Cohesion: 0.40
Nodes (5): erp_ai/conversation.py, ast_hash, mtime, seen, semantic_hash

### Community 177 - "erp_ai/draft_workflow.py"
Cohesion: 0.40
Nodes (5): erp_ai/draft_workflow.py, ast_hash, mtime, seen, semantic_hash

### Community 178 - "erp_ai/erp_ai/doctype/ai_assistant_action/ai_assistant_action.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_assistant_action/ai_assistant_action.json, ast_hash, mtime, seen, semantic_hash

### Community 179 - "erp_ai/erp_ai/doctype/ai_assistant_action/ai_assistant_action.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_assistant_action/ai_assistant_action.py, ast_hash, mtime, seen, semantic_hash

### Community 180 - "erp_ai/erp_ai/doctype/ai_assistant_action/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_assistant_action/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 181 - "erp_ai/erp_ai/doctype/ai_behavior_pattern/ai_behavior_pattern.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_behavior_pattern/ai_behavior_pattern.json, ast_hash, mtime, seen, semantic_hash

### Community 182 - "erp_ai/erp_ai/doctype/ai_behavior_pattern/ai_behavior_pattern.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_behavior_pattern/ai_behavior_pattern.py, ast_hash, mtime, seen, semantic_hash

### Community 183 - "erp_ai/erp_ai/doctype/ai_chat_message/ai_chat_message.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_chat_message/ai_chat_message.json, ast_hash, mtime, seen, semantic_hash

### Community 184 - "erp_ai/erp_ai/doctype/ai_chat_message/ai_chat_message.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_chat_message/ai_chat_message.py, ast_hash, mtime, seen, semantic_hash

### Community 185 - "erp_ai/erp_ai/doctype/ai_chat_message/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_chat_message/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 186 - "erp_ai/erp_ai/doctype/ai_help_article/ai_help_article.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_help_article/ai_help_article.json, ast_hash, mtime, seen, semantic_hash

### Community 187 - "erp_ai/erp_ai/doctype/ai_help_article/ai_help_article.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_help_article/ai_help_article.py, ast_hash, mtime, seen, semantic_hash

### Community 188 - "erp_ai/erp_ai/doctype/ai_help_article/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_help_article/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 189 - "erp_ai/erp_ai/doctype/ai_settings/ai_settings.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_settings/ai_settings.json, ast_hash, mtime, seen, semantic_hash

### Community 190 - "erp_ai/erp_ai/doctype/ai_settings/ai_settings.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_settings/ai_settings.py, ast_hash, mtime, seen, semantic_hash

### Community 191 - "erp_ai/erp_ai/doctype/ai_user_behavior/ai_user_behavior.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_user_behavior/ai_user_behavior.json, ast_hash, mtime, seen, semantic_hash

### Community 192 - "erp_ai/erp_ai/doctype/ai_user_behavior/ai_user_behavior.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/doctype/ai_user_behavior/ai_user_behavior.py, ast_hash, mtime, seen, semantic_hash

### Community 193 - "erp_ai/erp_ai/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 194 - "erp_ai/erp_ai/page/ai_assistant/ai_assistant.js"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/page/ai_assistant/ai_assistant.js, ast_hash, mtime, seen, semantic_hash

### Community 195 - "erp_ai/erp_ai/page/ai_assistant/ai_assistant.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/page/ai_assistant/ai_assistant.json, ast_hash, mtime, seen, semantic_hash

### Community 196 - "erp_ai/erp_ai/page/ai_assistant/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/page/ai_assistant/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 197 - "erp_ai/erp_ai/workspace/ai_assistant_hub/ai_assistant_hub.json"
Cohesion: 0.40
Nodes (5): erp_ai/erp_ai/workspace/ai_assistant_hub/ai_assistant_hub.json, ast_hash, mtime, seen, semantic_hash

### Community 198 - "erp_ai/erp_tools.py"
Cohesion: 0.40
Nodes (5): erp_ai/erp_tools.py, ast_hash, mtime, seen, semantic_hash

### Community 199 - "erp_ai/evaluation.py"
Cohesion: 0.40
Nodes (5): erp_ai/evaluation.py, ast_hash, mtime, seen, semantic_hash

### Community 200 - "erp_ai/handlers/formatters.py"
Cohesion: 0.40
Nodes (5): erp_ai/handlers/formatters.py, ast_hash, mtime, seen, semantic_hash

### Community 201 - "erp_ai/handlers/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/handlers/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 202 - "erp_ai/help/articles.py"
Cohesion: 0.40
Nodes (5): erp_ai/help/articles.py, ast_hash, mtime, seen, semantic_hash

### Community 203 - "erp_ai/help/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/help/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 204 - "erp_ai/help/seed_articles.py"
Cohesion: 0.40
Nodes (5): erp_ai/help/seed_articles.py, ast_hash, mtime, seen, semantic_hash

### Community 205 - "erp_ai/hooks.py"
Cohesion: 0.40
Nodes (5): erp_ai/hooks.py, ast_hash, mtime, seen, semantic_hash

### Community 206 - "erp_ai/idempotency.py"
Cohesion: 0.40
Nodes (5): erp_ai/idempotency.py, ast_hash, mtime, seen, semantic_hash

### Community 207 - "erp_ai/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 208 - "erp_ai/install.py"
Cohesion: 0.40
Nodes (5): erp_ai/install.py, ast_hash, mtime, seen, semantic_hash

### Community 209 - "erp_ai/intents/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/intents/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 210 - "erp_ai/knowledge/erpnext_kb.py"
Cohesion: 0.40
Nodes (5): erp_ai/knowledge/erpnext_kb.py, ast_hash, mtime, seen, semantic_hash

### Community 211 - "erp_ai/knowledge/sources.py"
Cohesion: 0.40
Nodes (5): erp_ai/knowledge/sources.py, ast_hash, mtime, seen, semantic_hash

### Community 212 - "erp_ai/llm/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/llm/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 213 - "erp_ai/mcp/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/mcp/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 214 - "erp_ai/mcp/server.py"
Cohesion: 0.40
Nodes (5): erp_ai/mcp/server.py, ast_hash, mtime, seen, semantic_hash

### Community 215 - "erp_ai/modules.txt"
Cohesion: 0.40
Nodes (5): erp_ai/modules.txt, ast_hash, mtime, seen, semantic_hash

### Community 216 - "erp_ai/patches/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/patches/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 217 - "erp_ai/patches/normalize_llm_provider.py"
Cohesion: 0.40
Nodes (5): erp_ai/patches/normalize_llm_provider.py, ast_hash, mtime, seen, semantic_hash

### Community 218 - "erp_ai/public/js/ai_settings.js"
Cohesion: 0.40
Nodes (5): erp_ai/public/js/ai_settings.js, ast_hash, mtime, seen, semantic_hash

### Community 219 - "erp_ai/public/js/ai_widget.js"
Cohesion: 0.40
Nodes (5): erp_ai/public/js/ai_widget.js, ast_hash, mtime, seen, semantic_hash

### Community 220 - "erp_ai/questions/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/questions/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 221 - "erp_ai/rbac/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/rbac/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 222 - "erp_ai/safety/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/safety/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 223 - "erp_ai/schema/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/schema/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 224 - "erp_ai/tasks.py"
Cohesion: 0.40
Nodes (5): erp_ai/tasks.py, ast_hash, mtime, seen, semantic_hash

### Community 225 - "erp_ai/templates/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/templates/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 226 - "erp_ai/templates/pages/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/templates/pages/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 227 - "erp_ai/tests/ci_seed.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/ci_seed.py, ast_hash, mtime, seen, semantic_hash

### Community 228 - "erp_ai/tests/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 229 - "erp_ai/tests/test_ai_user_behavior.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_ai_user_behavior.py, ast_hash, mtime, seen, semantic_hash

### Community 230 - "erp_ai/tests/test_core.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_core.py, ast_hash, mtime, seen, semantic_hash

### Community 231 - "erp_ai/tests/test_erp_ai_security.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_erp_ai_security.py, ast_hash, mtime, seen, semantic_hash

### Community 232 - "erp_ai/tests/test_frappe_integration.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_frappe_integration.py, ast_hash, mtime, seen, semantic_hash

### Community 233 - "erp_ai/tests/test_infra.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_infra.py, ast_hash, mtime, seen, semantic_hash

### Community 234 - "erp_ai/tests/test_knowledge.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_knowledge.py, ast_hash, mtime, seen, semantic_hash

### Community 235 - "erp_ai/tests/test_rbac.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_rbac.py, ast_hash, mtime, seen, semantic_hash

### Community 236 - "erp_ai/tests/test_security.py"
Cohesion: 0.40
Nodes (5): erp_ai/tests/test_security.py, ast_hash, mtime, seen, semantic_hash

### Community 237 - "erp_ai/validators/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/validators/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 238 - "erp_ai/voice/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/voice/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 239 - "erp_ai/voice/setup_voice.sh"
Cohesion: 0.40
Nodes (5): erp_ai/voice/setup_voice.sh, ast_hash, mtime, seen, semantic_hash

### Community 240 - "erp_ai/voice/toggle.py"
Cohesion: 0.40
Nodes (5): erp_ai/voice/toggle.py, ast_hash, mtime, seen, semantic_hash

### Community 241 - "erp_ai/workflows/__init__.py"
Cohesion: 0.40
Nodes (5): erp_ai/workflows/__init__.py, ast_hash, mtime, seen, semantic_hash

### Community 242 - "erp_ai/workflows/shipment.py"
Cohesion: 0.40
Nodes (5): erp_ai/workflows/shipment.py, ast_hash, mtime, seen, semantic_hash

### Community 243 - "erp_ai/workflows/stock_issue.py"
Cohesion: 0.40
Nodes (5): erp_ai/workflows/stock_issue.py, ast_hash, mtime, seen, semantic_hash

### Community 244 - ".github/workflows/ci.yml"
Cohesion: 0.40
Nodes (5): .github/workflows/ci.yml, ast_hash, mtime, seen, semantic_hash

### Community 245 - ".pre-commit-config.yaml"
Cohesion: 0.40
Nodes (5): .pre-commit-config.yaml, ast_hash, mtime, seen, semantic_hash

### Community 246 - "pyproject.toml"
Cohesion: 0.40
Nodes (5): pyproject.toml, ast_hash, mtime, seen, semantic_hash

### Community 247 - "README.md"
Cohesion: 0.40
Nodes (5): README.md, ast_hash, mtime, seen, semantic_hash

### Community 248 - "RELEASE_NOTES.md"
Cohesion: 0.40
Nodes (5): RELEASE_NOTES.md, ast_hash, mtime, seen, semantic_hash

### Community 249 - "scripts/sync_workspace.py"
Cohesion: 0.40
Nodes (5): scripts/sync_workspace.py, ast_hash, mtime, seen, semantic_hash

### Community 250 - "SECURITY.md"
Cohesion: 0.40
Nodes (5): SECURITY.md, ast_hash, mtime, seen, semantic_hash

### Community 251 - "run_evaluation"
Cohesion: 0.50
Nodes (5): _process_with_mcp(), Run the model evaluation suite. Requires System Manager., Evaluation hook: answer through the real assistant core (read paths).…, run_evaluation(), _ask()

### Community 252 - "AIBehaviorPattern"
Cohesion: 0.40
Nodes (4): AIBehaviorPattern, Document, Controller: rows are owned by the nightly task, not by users., AI Behavior Pattern — the nightly materialized view of the behavior log. Rows…

### Community 253 - "AISettings"
Cohesion: 0.40
Nodes (3): AISettings, Document, Refuse to store a configuration the assistant cannot run with. The LLM backend…

### Community 254 - "check_commit_msg.py"
Cohesion: 0.50
Nodes (4): check(), main(), Commit-message check: conventional subject line. Used as a pre-commit ``commit-…, Return a list of problem strings (empty when the message is fine).

### Community 255 - "🧪 Testing"
Cohesion: 0.40
Nodes (5): CI, Database-free tests (no Frappe / no site required), Frappe-backed tests (needs a real bench site), Pre-commit hooks, 🧪 Testing

### Community 256 - "LLMProvider"
Cohesion: 0.50
Nodes (4): Enum, LLMProvider, Available LLM providers., str

### Community 257 - "refresh_behavior_patterns"
Cohesion: 0.50
Nodes (4): Drop the cached prompt block; the nightly refresh calls this., reset_patterns_cache(), Daily: materialize org-level behavior aggregates into AI Behavior Pattern.…, refresh_behavior_patterns()

### Community 258 - "ai_assistant.js"
Cohesion: 0.83
Nodes (3): add(), msgEl(), send()

### Community 259 - "voice_stage_budget"
Cohesion: 0.50
Nodes (4): Each bounded voice stage has an entry in the budget, all positive, and the…, test_voice_stage_budget_covers_every_subprocess_stage(), Return the per-stage timeout budget (seconds) for the voice path., voice_stage_budget()

### Community 261 - "💬 Usage"
Cohesion: 0.50
Nodes (4): Chat locations, Example prompts, Quick question chips (workspace), 💬 Usage

### Community 262 - "Phase 1 — Production-relevant robustness"
Cohesion: 0.50
Nodes (4): 1.1 Ollama request timeouts, retry, and healthy-report, 1.2 Knowledge base: real freshness + verifiable citations, 1.3 Error observability — structured logging for AI actions, Phase 1 — Production-relevant robustness

### Community 263 - "Current runtime (as of 2026-09-19)"
Cohesion: 0.50
Nodes (4): Current runtime (as of 2026-09-19), Providers, Settings live in AI Settings, What `ask_llm()` does (the god node)

### Community 264 - "cleanup_temp_files"
Cohesion: 0.67
Nodes (3): cleanup_temp_files(), Delete uploaded temp files older than max_age_seconds. Returns count removed., test_cleanup_temp_files_safe()

### Community 266 - "AIUserBehavior"
Cohesion: 0.67
Nodes (3): AIUserBehavior, Document, Controller: no field logic — the value of this doctype is the log itself.

### Community 269 - "Phase 2 — Voice & latency robustness"
Cohesion: 0.67
Nodes (3): 2.1 Voice timeout budget across STT → LLM → TTS, 2.2 Pre-commit + formatting consistency, Phase 2 — Voice & latency robustness

### Community 270 - "Phase 3 — Flow-level e2e tests in CI"
Cohesion: 0.67
Nodes (3): 3.1 Guided conversation + draft-confirm e2e tests, 3.2 Pre-commit Config and workflow hygiene, Phase 3 — Flow-level e2e tests in CI

## Knowledge Gaps
- **906 isolated node(s):** `mtime`, `seen`, `ast_hash`, `semantic_hash`, `mtime` (+901 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1515 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `FrappeMCP` connect `FrappeMCP` to `erp_tools.py`, `log_error_safely`, `confirm_draft`, `api.py`, `audit.py`, `TestQueryPermissionScoping`, `rbac/__init__.py`, `draft_workflow.py`, `test_erp_ai_security.py`, `create_shipment_receipt`, `._as_user`, `mcp/__init__.py`, `.test_mcp_update_document_respects_document_level_scope`, `TestPhase4EntityResolution`, `_log_tool_error`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Why does `log_error_safely()` connect `log_error_safely` to `erp_tools.py`, `audit.py`, `api.py`, `ask_llm`, `confirm_draft`, `whitelist`, `rbac/__init__.py`, `draft_workflow.py`, `test_erp_ai_security.py`, `install.py`, `_log_tool_error`, `test_frappe_integration.py`, `ai_user_behavior.py`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **Why does `TestMCPRpcAuthorization` connect `audit.py` to `test_erp_ai_security.py`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `FrappeMCP` (e.g. with `capabilities()` and `mcp_call_tool()`) actually correct?**
  _`FrappeMCP` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `mtime`, `seen`, `ast_hash` to the rest of the system?**
  _906 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Communities (90 total, 10 thin omitted)` be split into smaller, more focused modules?**
  _Cohesion score 0.029411764705882353 - nodes in this community are weakly interconnected._
- **Should `erp_tools.py` be split into smaller, more focused modules?**
  _Cohesion score 0.04214223002633889 - nodes in this community are weakly interconnected._