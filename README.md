# ERP AI — Local AI Assistant for ERPNext (MIT)

**ERP AI** is a [Frappe Framework](https://frappe.io) v15 / [ERPNext](https://erpnext.com) v15
app that adds a local-first AI assistant to the Desk: chat, guided ERP workflows,
permission-checked document access, and an optional voice stack (Whisper.cpp
speech-to-text + Piper text-to-speech) — all running **fully offline** on your
own server via Ollama (or any configured LLM provider in `AI Settings`).

> This is **not** a SaaS product and **not** a model-training pipeline. The
> assistant is prompt/tool-driven: it queries real ERP data, follows the bundled
> ERPNext knowledge base, and routes document writes through an audited
> **draft → confirm** workflow. Any "learning" happens at the LLM provider level
> or through knowledge-base articles, not via weight training inside this repo.
>
> Voice input is **alone on recordings**: each byte of audio goes to a private,
> per-call temp file that is removed after transcription — no recording is
> kept, stored, or attached to the conversation.

---

## 📚 Docs / collaboration

| Resource | Where |
|---|---|
| Project tracking / issues | [Issues](https://github.com/zahidprinters/erp_ai/issues) |
| Contributing guide | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Code of Conduct | [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) |
| Security policy | [`SECURITY.md`](SECURITY.md) |
| Release notes / changelog | [`RELEASE_NOTES.md`](RELEASE_NOTES.md) |

## Table of contents

- [Quick start](#quick-start)
- [Usage](#usage)
- [LLM providers](#llm-providers)
- [Capabilities](#capabilities)
- [Production hardening](#production-hardening)
- [API reference](#api-reference)
- [Configuration](#configuration)
- [Project structure](#project-structure)
- [Installation](#installation)
- [Testing](#testing)
- [CI](#ci)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)
- [Compatibility](#compatibility)
- [License](#license)

---

## 🚀 Quick start

### 1. Add the app to your bench

```bash
# from the bench root
bench get-app erp_ai /path/to/erp_ai
bench --site <site> install-app erp_ai
bench --site <site> migrate
```

The app is managed by bench, not pip. Python packaging metadata lives in
`pyproject.toml`; the required runtime (Frappe Framework v15 + ERPNext v15)
is provided by the bench environment.

### 2. Set up the workspace (embeds chat + help on the dashboard)

```bash
bench --site <site> execute erp_ai.api.setup_workspace
bench --site <site> clear-cache
```

### 3. (Optional) Provision the voice stack

```bash
sudo bash apps/erp_ai/erp_ai/voice/setup_voice.sh
```

Runtime files expected by `erp_ai.voice._ai_home()`:

- Whisper: `$HOME/ai/whisper.cpp/build/bin/whisper-cli`, model `$HOME/ai/models/ggml-tiny.bin`
- Piper: `$HOME/ai/piper/piper`, voices `$HOME/ai/models/en_US-lessac-medium.onnx` +
  `ur_PK-fasih-medium.onnx`
- `ffmpeg` on `PATH`

See [Voice input (mic) not working](#voice-input-mic-not-working) for verification.

### 4. Add LLM models in Ollama

```bash
ollama pull qwen2.5:1.5b
# optional, for higher quality on stronger hardware:
# ollama pull qwen2.5:7b
```

Model defaults and the allowlist live in `erp_ai/llm/__init__`.

### 5. Rebuild assets & restart

```bash
bench build --app erp_ai
bench --site <site> clear-cache
# restart web (bench setup production or supervisor)
supervisorctl restart frappe-bench-web:
```

---

## 💬 Usage

### Chat locations
1. **Floating 🤖 widget** — bottom-right of every Desk page.
2. **Workspace** — `/app/ai-assistant-hub` (AI Assistant Hub) has an embedded live
   chat + help section.
3. **Full page** — `/app/ai-assistant` (Page: AI Assistant).
4. **Form button** — "🤖 Ask AI" button appears on form toolbars (Customer, Sales
   Invoice, Stock Entry …) — asks about the open document.

### Quick question chips (workspace)
`How many items?` `Total stock?` `Unpaid invoices` `Customer count?`

### Example prompts

**Data queries**
- `How many items do we have?`
- `How many customers / suppliers?`
- `Total stock across all warehouses?`
- `List unpaid invoices` / `Show me all items`
- `Search for pump springs`

**Guided workflows — draft then confirm**

Every document-creating prompt goes through a two-step flow: the assistant parses
the request, saves a **draft** in `AI Assistant Action`, shows a **preview**,
and only creates the real document after you say **"yes"** to confirm. Master
data (supplier, item, customer) is never created without that explicit step.

- Shipment: `Spring shipment arrived from ABC Traders, vehicle LEA-4521, 500 pcs
  pump springs` → parses supplier/items/quantities, returns a preview for
  confirmation, then creates a Stock Entry (Material Receipt).
- Stock issue: `Issue 10 pump springs from Stores to Engr Ali Production` →
  Stock Entry Material Issue/Transfer with issued-to tracking.
- Invoice: `Make invoice for ABC Traders, 2 pump springs @ 500` → Sales Invoice
  DRAFT (approval-limit enforced) + print URL.
- Create master data: `Create item named Steel Rod price 100` / `Create customer
  named XYZ Corp` / `Create supplier named ABC Traders` → guided draft + confirm.
- Print: `Print invoice SINV-00001` → PDF print URL.

**Guidance / setup**
- `What do I need to make a sales invoice?`
- `How do I set up a new warehouse?`
- `How does the manufacturing BOM work?`
- `Help me set up a new ERP system`
- `What taxes apply in Pakistan?`

**Voice**
- Click 🎤 in chat → allow mic → speak → stop → words appear in the input.
- Answers auto-play with 🔊 (toggle 🔇 to disable). English by default; Urdu via
  `lang=ur` in the model param.

---

## 🔌 API reference (all `@frappe.whitelist`)

Serve endpoints are reachable as `/api/method/erp_ai.api.<name>`. Document-creating
and voice endpoints are the only ones that can write documents or run subprocesses;
everything else is read-only and permission-checked.

each whitelisted method is called by Frappe's `frappe.call()` from the Desk widget
and from the API tools below.

### Chat / answers
| Endpoint | Params | Returns |
|---|---|---|
| `erp_ai.api.chat` | `prompt, model` | `{response}` |
| `erp_ai.api.ask` | `prompt, session, model` | string reply (basic) |
| `erp_ai.api.ask_v2_with_voice` | `prompt, session, model, voice` | `{response, session, audio_url}` |
| `erp_ai.api.ask_with_doc` | `doctype, name, prompt, session, model` | `{response, session, doctype, docname}` |
| `erp_ai.api.data_answer` | `prompt` | `{ok, answer, intent, target_doctype, failure_reason}` |
| `erp_ai.api.summarize_doc` | `doctype, name, session, prompt` | `{summary}` |
| `erp_ai.api.citation_for` | `doctype, session` | citation string |

### Voice
| Endpoint | Params | Returns |
|---|---|---|
| `erp_ai.api.voice_to_text` | `audio` (base64), `fmt` (`webm`/etc.) | `{text}` |
| `erp_ai.api.voice_toggle` | `enabled` | `{ok}` |
| `erp_ai.api.voice_set` | `enabled` | `{ok}` |

`voice_to_text` is Whisper.cpp STT — audio must be a base64 payload (the widget
sends the data-URI body via `frappe.call`). `wer` formats also accepted.

### MCP tools (permission-checked document access)

| Endpoint | Params | Returns |
|---|---|---|
| `erp_ai.mcp.mcp_list_tools` | — | `{tools:[...]}` |
| `erp_ai.mcp.mcp_call_tool` | `name, args` (JSON string) | tool result |

Available tools: `query_doctype`, `get_document`, `create_document`,
`update_document`, `print_document`, `search_documents`, `get_doctype_meta`,
`submit_document`, `get_workspace`.

`create_document` / `update_document` enforce `frappe.has_permission()`;
the allowlist only contains business DocTypes — system, security, and HR/
personnel DocTypes are denied by default.

### Workflow handlers

| Endpoint | Params | Returns |
|---|---|---|
| `erp_ai.api.workflow_shipment_receipt` | `data` (JSON: `supplier, vehicle_no, items:[{item_code,qty,rate}], warehouse, remarks`) | `{ok, draft_id, message, preview}` |
| `erp_ai.api.workflow_stock_issue` | `data` (`item_code, qty, from_warehouse, to_warehouse, issue_type, issued_to, department`) | `{ok, draft_id, message, preview}` |

Both save a draft and return a **preview**. Confirmation happens through
`erp_ai.api.confirm_workflow_action(action_id, user)` — the same user/session
that created the draft must confirm it.

### Help & knowledge
| Endpoint | Params | Returns |
|---|---|---|
| `erp_ai.api.get_articles` | `session` (optional) | curated help articles |
| `erp_ai.api.search_articles` | `query, session` (optional) | filtered articles |
| `erp_ai.api.get_article` | `article_id, session` (optional) | one article |
| `erp_ai.api.get_help_categories` | `session` (optional) | help categories |
| `erp_ai.api.get_knowledge_base` | `session` (optional) | ERPNext workflow KB |
| `erp_ai.api.get_quick_actions` | `session` (optional) | categorized quick actions |
| `erp_ai.api.knowledge_freshness` | — | sources with freshness + citations |

### Feedback / permissions / audit
| Endpoint | Params | Returns |
|---|---|---|
| `erp_ai.api.record_feedback` | `session, helpful` (0/1) | recorded turn |
| `erp_ai.api.my_permissions` | — | `{roles, allowed_doctypes, allowed_methods per doctype}` |
| `erp_ai.api.check_my_permission` | `doctype, action` | `{allowed, required_role, reason if denied}` |
| `erp_ai.api.audit_history` | `session` (optional), `limit` | caller's AI action audit trail |

### Infrastructure / creation helpers
| Endpoint | Params | Returns |
|---|---|---|
| `erp_ai.api.barcode_lookup` | `code` | `{doctype, name}` (permission-checked, checksum-validated formats) |
| `erp_ai.api.ocr_extract_text` | `file_url` (`/files/...` URL) | `{text}` from image/PDF (Frappe-managed uploads only) |
| `erp_ai.api.setup_workspace` | — | workspace page + shortcut created |
| `erp_ai.api.sync_workspace_from_json` | (internal, published via setup) | workspace synced from JSON |
| `erp_ai.api.capabilities` | — | `{doctypes, actions, tools, features}` |

`list_available_models` is an internal API-tool delegate — enumerate exporters via
`erp_ai.mcp.mcp_list_tools` instead.

---

## ⚙️ Configuration

| Setting | Where | Notes |
|---|---|---|
| Default model | `frappe.conf.ai_model` or `DEFAULT_MODELS` in `erp_ai/llm/__init__` | `qwen2.5:1.5b` |
| Allowed models | `AI_ALLOWED_MODELS` in `erp_ai/llm/__init__` | `qwen2.5:1.5b`, `qwen2.5:3b`, `qwen2.5:7b` |
| Ollama URL | `OLLAMA_URL` in `erp_ai/llm/__init__` | `http://localhost:11434/api/generate` |
| LLM provider selection | `AI Settings` DocType (`/app/ai-settings`) | Provider + API key + base URL + model + timeout + temperature |
| Voice model paths | `erp_ai.voice._ai_home()` | env `AI_HOME` or `~/ai` or `/home/erpnext/ai` |
| TTS files | `sites/<site>/public/files/tts/*.wav` | served at `/files/tts/...` |
| Hook | `app_include_js = "/assets/erp_ai/js/ai_widget.js?v=4"` in `hooks.py` | loads widget on every desk page |
| Conversation store | Doctype `AI Chat Message` (user, session_id, role, content) | per-user, last 8 turns in context |
| Draft actions | Doctype `AI Assistant Action` (nonce, expires_on, idempotency_key, rollback_reference) | confirmation lifecycle |

---

## 📦 Project structure

```
erp_ai/
├── erp_ai/                          # App package (Frappe app root)
│   ├── __init__.py                  # App version + metadata
│   ├── hooks.py                     # Frappe hooks: asset injection, doc event dispatch,
│   │                                #   scheduled tasks (hourly/daily)
│   ├── api.py                       # Public whitelisted API facade (chat, workflows, voice,
│   │                                #   MCP, settings, health, audit, feedback)
│   ├── draft_workflow.py            # Draft → confirm engine: create_draft,
│   │                                #   confirm_draft, create_document_from_draft,
│   │                                #   DOCTYPE_SCHEMAS, create_document_from_draft doc
│   │                                #   handlers (PR, SE, SI, Customer, Supplier,…)
│   ├── erp_tools.py                 # LLM-side tools: read/query the ERP (items,
│   │                                #   customers, suppliers, companies, warehouses,
│   │                                #   stock levels, SO/PO/SI/PI, low-stock, prices,
│   │                                #   transaction summaries) + create-entity + execute
│   ├── invoice_helpers.py            # (moved to erp_tools)
│   ├── safety.py                    # Illegal-operation guard + duplication-field list
│   ├── conversation.py              # Guided field-collection conversation
│   ├── schema/                      # DOCTYPE_SCHEMAS — single source of truth for
│   │                                # registry doctypes (required/optional/child fields)
│   ├── intents/                     # NL → doctype + action (intent detection)
│   ├── validators/                  # Field input validation + number parsing
│   ├── questions/                   # Field questions + hints
│   ├── handlers/                    # Document handler dispatch + formatters (doc view)
│   ├── workfl\n                                                                                                                                  
│   ├── voice/                       # Whisper.cpp STT + Piper TTS pipeline +
│   │                                # toggle + emergency voice stop
│   ├── mcp/                         # MCP tool RPC endpoints + FrappeMCP
│   │                                # permission-safe tool layer
│   ├── knowledge/                   # ERPNext workflow knowledge base +
│   │                                # source citations / freshness
│   ├── attachments.py               # Upload validation + OCR text extraction
│   │                                # (Frappe-managed files only)
│   ├── barcode.py                   # Barcode/QR resolution + checksum validation
│   ├── evaluation.py                # Model quality evaluation helper
│   ├── tasks.py                     # Scheduled jobs (hourly: expire stale actions,
│   │                                # summary refresh; daily: refresh behavior
│   │                                # patterns)
│   ├── config/                       # Empty package — removed during cleanup
│   ├── erp_ai/                       # Nested package: DocTypes, Page, Workspace
││   ├── doctype/
││   │   ├── ai_assistant_action/     # Auditable draft/confirm store
││   │   ├── ai_behavior_pattern/      # Logged behavior patterns
││   │   ├── ai_chat_message/          # Conversation history storage
││   │   ├── ai_help_article/          # Curated help/knowledge articles
││   │   ├── ai_settings/              # Provider, API keys, feature toggles
││   │   └── ai_user_behavior/          # Logged user behavior (refinement signal)
││   ├── page/
││   │   └── ai_assistant/            # Full-page chat (JS + Page JSON)
││   └── workspace/
││       └── ai_assistant_hub/       # Embedded workspace chat + help
│   └── tests/
│       ├── test_core.py             # schema, intents, safety, validators, questions
│       ├── test_security.py         # prompt injection, input validation,
│       │                             #   draft/confirm/rollback contracts
│       ├── test_rbac.py             # approval limits, supervisor, restrictions
│       ├── test_knowledge.py        # citations, freshness, doctype mapping
│       ├── test_infra.py           # barcode checksums, attachments, idempotency
│       │                             # (no DB)
│       ├── test_ai_user_behavior.py # logged behavior (open-ended interaction)
│       ├── test_erp_ai_security.py # live Frappe-backed: permissions, draft/conf,
│       │                             #   approval limits, ERN integration
│       └── test_frappe_integration.py# live DB: idempotency, audit, shipment
│                                     # confirm, rollback, permissions
├── .github/workflows/ci.yml        # CI: lint + syntax + db-free tests (job 1),
│                                    #    frappe-backed tests with MariaDB+Redis
│                                    #    + seed (job 2)
├── .github/ISSUE_TEMPLATE/         # bug_report.md, feature_request.md
├── scripts/
│   ├── sync_workspace.py           # CLI helper to publish a JSON workspace
├── templates/                       # freeze to app package convention (empty inits)
│   └── pages/__init__.py
├── public/
│   ├── js/
│   │   ├── ai_widget.js           # desktop floating chat widget (uploads mic
│   │                                #   audio, calls ask/chat/workflows/buttons)
│   │   └── ai_settings.js          # AI Settings UI scaffolding (admin only)
│   └── css/
│       └── (none — styles in Editor.js pages / JS-injected)
├── pyproject.toml                  # Python packaging metadata + runtime reqs
└── README.md
```

## 🧪 Testing

### Database-free tests (no Frappe / no site required)

```bash
cd apps/erp_ai
python -m pytest erp_ai/tests/test_core.py erp_ai/tests/test_security.py \
  erp_ai/tests/test_rbac.py erp_ai/tests/test_knowledge.py erp_ai/tests/test_infra.py \
  -q -p no:cacheprovider
```

Covers: schema integrity, NL intent detection, safety rules, field validators,
questions, role/RBAC policies, knowledge-base citations & freshness, barcode
checksums, attachment validation (MIME spoofing, sizes, traversal), idempotency
keys, and the voice-to-text wrapper.

Run all with current coverage:

```bash
python -m pytest erp_ai/tests/ -q -p no:cacheprovider --tb=short
```

### Frappe-backed tests (needs a real bench site)

```bash
bench --site <site> run-tests --app erp_ai
```

These touch a real Frappe/ERPNext site and cover: permissions, draft→confirm
pipelines, rollback references, approval limits, supplier/item creation, the
shipment & stock-issue confirm flows, RBAC enforcement, and live metadata.

Each test that needs fresh ERPNext masters (UOM "Nos", Customer Group
"Individual", Company, Warehouse Types) seeds them itself via
`erp_ai.tests.ci_seed` if absent.

### CI

`.github/workflows/ci.yml` defines **two jobs** on push to `develop` (and on any
direct push):

| Job | What it does |
|---|---|
| `lint-and-unit` | `ruff check erp_ai/`, `python -c "import yaml …"` + `ast.parse` every `.py`, then the 114 db-free tests above. |
| `frappe-tests` | sets up Docker MariaDB 10.11 + Redis 7, installs Frappe bench v5.31 + Frappe v15 + ERPNext v15.100.0, creates `test_site`, seeds ERPNext masters via `erp_ai.tests.ci_seed`, installs pytest, then runs the full Frappe-backed suite with `bench --site test_site run-tests --app erp_ai`. On failure it annotates the failure. |

Both jobs fail if they don't pass. Run Frappe-backed tests inside your bench for
manual verification:

```bash
bench --site <site> run-tests --app erp_ai
```

---

## 🔒 Security

- Document creation goes through the permission-checked MCP tool layer
  (`erp_ai/mcp/server.py`), not raw `frappe.get_doc(...).insert()` from
  untrusted input.
- Public workflow endpoints are **not** direct create/submit endpoints: they
  return a preview and wait for explicit user confirmation.
- `ocr_extract_text` accepts only Frappe-managed file URLs and validates both
  filename and content before any processing.
- Temporary files created for OCR/voice processing are removed after use; there
  is no long-lived user-controlled file retention path in the assistant itself.
- Voice input requires HTTPS (except `localhost`).
- No LLM API keys are stored in code or in git; they live in the `AI Settings`
  DocType or in Frappe site config.

See [`SECURITY.md`](SECURITY.md) for the full model and how to report
vulnerabilities.

---

## 🩻 Troubleshooting

### Chat / widget not appearing on the workspace
1. Hard refresh (`Ctrl+Shift+R`) — assets are cached (hence `?v=4`).
2. Open DevTools Console; look for `[AI Widget]` logs:
   - `Script loaded …` → script executing
   - `Checking workspace … isWs=true` → route detected
   - `Target found: desk-page page-main-content` → container found
   - `Chat panel injected into workspace` → success
3. If no logs: the file is cached/old → `bench build --app erp_ai` + restart web.
4. Confirm the script tag: `grep ai_widget <page html>` →
   `src="/assets/erp_ai/js/ai_widget.js?v=4"`.
5. Check the served asset has the functions:
   `curl -s http://localhost/assets/erp_ai/js/ai_widget.js | grep -c mountWorkspaceChat`
   (expect ≥3).

### Voice input (mic) not working
- **`erp_ai.api.voice_to_text` must be whitelisted.** The widget calls it via
  `frappe.call()`; without the decorator the call returns `Not permitted`.
  The endpoint accepts a base64 audio payload (`fmt=webm`/`wav`/`mp3`/`ogg`).
- HTTPS is required except `localhost`. Use `https://<site>.`
- Console message `Mic permission denied: …` → grant mic permission (lock icon
  in address bar).
- `Microphone needs HTTPS (or localhost)` → you're on plain http.
- transcribing error / `(no speech detected)` → check whisper-cli exists at
  `$HOME/ai/whisper.cpp/build/bin/whisper-cli` + model
  `$HOME/ai/models/ggml-tiny.bin`; test: `echo hi | ~/ai/whisper.../whisper-cli -m
  ~/ai/models/ggml-tiny.bin -`.
- `ffmpeg: command not found` → `ffmpeg` must be on `PATH`.

### TTS (voice output) not playing
- `ask_v2_with_voice` returns an `audio_url` only when `is_voice_enabled()` is
  true (admin master toggle in `AI Settings.speaker_enabled`).
- File served? `curl -s -o /dev/null -w '%{http_code}'
  http://<site>/files/tts/<file>.wav` (expect 200).
- Piper model missing → rerun `voice/setup_voice.sh` or place
  `en_US-lessac-medium.onnx` / `ur_PK-fasih-medium.onnx` in `~/ai/models/`.

### AI answers wrong/old data
- Docs are created as **DRAFT** — submit them so stock/accounts update.
- Check `AI Chat Message` records for the session.
- Verify Ollama is running: `curl http://localhost:11434/api/generate -d
  '{"model":"qwen2.5:1.5b","prompt":"hi"}'`.

### Drafts not confirming
- `confirm_workflow_action(action_id, user)` is HTTP-exposed and bound to the
  user/session that created the draft.
- In a bench: `bench --site <site> execute erp_ai.api.confirm_workflow_action '<id>' '<user>'`.
- Make sure `lip` erpnext masters were seeded via `erp_ai.tests.ci_seed` if
  you created a fresh site — a bare bench new-site only installs app fixtures,
  not the ERPNext setup-wizard masters (UOM, Customer Group, Company, Warehouse
  Types, default company).

### Assets / build issues
```bash
# force full rebuild
bench build --app erp_ai
bench --site <site> clear-cache
# restart web
supervisorctl restart frappe-bench-web:
```

### Python errors in the app
```bash
find apps/erp_ai -type d -name '__pycache__' -exec rm -rf {} +
find apps/erp_ai -name '*.pyc' -delete
python3 -m py_compile apps/erp_ai/erp_ai/api.py
python3 -m py_compile apps/erp_ai/erp_ai/draft_workflow.py
python3 -m py_compile apps/erp_ai/erp_ai/workflows/shipment.py
```

### Common error references
| Error | Cause | Fix |
|---|---|---|
| `Not permitted` on `voice_to_text` | endpoint not whitelisted/decorator missing | add `@frappe.whitelist()` to the `voice_to_text` def in `erp_ai/api.py` |
| `Invalid audio payload (expected base64)` | non-base64 payload sent to `voice_to_text` | ensure the caller sends pure base64 (data-URI body) |
| `Failed to create Purchase Receipt: Warehouse is mandatory` | shipment draft had no warehouse (parser didn't match, or it was stripped by draft sanitization) | ensure `erp_ai/workflows/shipment.py` inserts `warehouse` on each item row and on the draft data so the confirm path keeps it |
| `TabError` / `IndentationError` | mixed tabs/spaces after edits | `python3 -m py_compile …` and fix indentation |
| `NameError: _json is not defined` / similar | missing local import in a function | add the import locally |
| `Quantity for Item cannot be zero` | qty not parsed | provide qty, or missing item data — AI will ask |
| `item_code required in every item` | item name not resolved to an existing item | ensure item exists or is created |
| `Failed to get method …` | stale code / not migrated | `bench --site <site> migrate` + restart |
| `observeWorkspace: undefined` | old cached file | hard refresh; rebuild with `?v=` bump |

---

## 🧹 Maintenance

```bash
# clean caches & logs
bench --site <site> clear-cache
find sites/<site>/logs -name "*.log" -mtime +3 -delete

# clean python caches
find apps/erp_ai -type d -name '__pycache__' -exec rm -rf {} + | true

# git housekeeping
cd apps/erp_ai && git add -A && git commit -m 'chore: tidy' && git gc --auto
```

---

## 🖥 Reference deployment (example — this server)

| Resource | Measured |
|---|---|
| CPU | 8 cores |
| RAM | 7.1 GB total (5+ GB available) |
| Disk | 23 GB (7.7 GB free) |
| LLM | Ollama 0.33.3, model `qwen2.5:1.5b` |
| STT | whisper.cpp tiny (~75 MB RAM) |
| TTS | Piper onnxruntime (offline) |
| OS | Debian 12 (bookworm), Python 3.11.2, Node 22 |

For 7b models you'd want 16 GB+ RAM; 1.5b runs fine here.

---

## 🤝 Compatibility

- Frappe Framework **v15**, ERPNext **v15**.
- Coexists with other apps (fbr_pos_integration, etc.) — the only hook is
  `app_include_js`; there are no core overrides.
- All endpoints are `@frappe.whitelist` (auth is applied). Document operations
  enforce `frappe.has_permission()` — no `ignore_permissions=True` in the MCP
  tool layer. Workspace setup requires System Manager role.
- API tokens: each authenticated user carries a unique `api_key` / `api_secret`
  pair (regenerated with `erp_ai.api.make_token`).

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE).

This is a local Frappe app — MIT covers the code in this repository only and does
**not** apply to your ERP data, your ERPNext instance, or any models running
behind a provider (e.g. Ollama, OpenRouter, OpenAI). Your ERPNext data remains
governed by your own environment and data policies.
