# ERP AI — Local AI Assistant for ERPNext (production hardening)

An AI assistant (chat + voice) baked into **Frappe Framework v15 / ERPNext v15**.
It answers questions from real ERP data, guides users through business workflows,
creates and updates documents through an explicit **preview → confirm** flow,
and speaks answers aloud in English and Urdu — all running **fully offline** on
your own server.

This app is intended for a controlled, on-prem environment with a local Ollama
instance and an optional local voice stack (Whisper.cpp + Piper). The assistant
never auto-creates or submits financial/stock documents without an explicit
user confirmation step, and every operation is recorded in an audit trail with a
rollback reference.

---

## ✨ Capabilities

| Capability | Notes |
|---|---|
| 💬 **Chat** | Floating widget on Desk pages + workspace chat + full-page chat |
| 🎤 **Voice input** | Speak in chat (Whisper.cpp STT); words appear in the input box. **HTTPS required** except on `localhost` |
| 🔊 **Voice output** | Piper TTS (English `en_US-lessac-medium`, Urdu `ur_PK-fasih-medium`); 🔊/🔇 toggle |
| 📊 **Real data answers** | “How many items?”, “Total stock?”, “Unpaid invoices?” → exact numbers from the DB |
| 🛠 **MCP tool access** | Query/list/search docs, get doc details, create/update/submit documents through a permission-checked tool layer |
| 📦 **Workflow NLP** | Shipment receipt, stock issue, invoice creation, item/customer/supplier creation via draft → confirm |
| 🧠 **Knowledge base** | ERPNext workflow KB injected into answers (selling, buying, stock, manufacturing, accounting, setup) |
| 👤 **Per-user memory** | Private conversation history per user in `AI Chat Message` |
| 🎭 **Role-aware** | Admins get technical detail; operators get short step-by-step guidance |
| 📄 **Print links** | PDF print URLs for created/submitted documents |
| 🛡 **Audit + rollback** | Every AI action recorded in `AI Assistant Action` with nonce, expiry, idempotency key, and rollback reference |
| 🔁 **Idempotent writes** | Retry-safe creation via `idempotency_key` on `AI Assistant Action` |

---

## Production hardening

- **Draft → confirm for document creation.** Workflow endpoints no longer create documents
  directly. They parse the request, save a draft in `AI Assistant Action`, and require
  explicit confirmation before any document is materialized.
- **One auditable creation path.** Public flows create documents through the centralized
  `erp_ai.draft_workflow` engine (`create_draft` → `confirm_draft` → `create_document_from_draft`),
  which delegates to the permission-checked MCP `create_document` tool.
- **Rollback references on every terminal action.** Completed and failed actions store a
  `rollback_reference` so operators can trace an outcome back to the originating action.
- **Idempotency.** `AI Assistant Action.idempotency_key` has a unique constraint, so retries
  of the same operation do not create duplicate actions or duplicate documents.
- **Malicious-file boundaries.** OCR and attachment helpers only operate on Frappe-managed
  uploads (`/files/...`, `/private/files/...`), validate filenames/contents, and delete temp
  copies after processing.
- **Voice subprocess hardening.** Voice helpers use timeouts and robust error handling so a
  slow or failing local voice runtime does not hang a request indefinitely.
- **Emergency voice stop.** `erp_ai.voice.interrupt_voice()` is the public surface for asking
  running voice operations to abort; voice helpers can poll `_voice_kill_requested()` and bail.

---

## ⚠️ Runtime requirements (before enabling voice / production use)

- **Frappe Framework v15 + ERPNext v15** bench (app managed via bench, not pip).
- **Ollama** running locally and reachable from the bench host (default `http://localhost:11434`).
- **Selected model** pulled in Ollama (the app’s defaults live in `erp_ai/llm/__init__.py`).
- **Voice stack (optional):**
  - `whisper.cpp/build/bin/whisper-cli` + a model (default `ggml-tiny.bin`)
  - `piper/piper` + voice model(s)
  - `ffmpeg` on `PATH` for audio conversion
  - `~/ai` or `$AI_HOME` pointing at the runtime root (see `erp_ai.voice._ai_home()`)
  - **HTTPS** for microphone access (except on `localhost`)
- **Python ≥ 3.10** (see `pyproject.toml`).

---

## Security boundaries

- The assistant works within ERPNext roles/permissions. Document creation goes through the
  permission-checked MCP tool layer, not raw `frappe.get_doc(...).insert()` from untrusted input.
- Public workflow endpoints are **not** direct create/submit endpoints. They return a preview and
  wait for user confirmation.
- `ocr_extract_text` accepts only Frappe-managed file URLs and validates both filename and content
  before any processing.
- Temporary files created for OCR/voice processing are removed after use; there is no long-lived
  user-controlled file retention path in the assistant itself.

## 📦 Structure

```
erp_ai/
├── erp_ai/
│   ├── api.py                  # Public whitelisted API facade (thin routing layer)
│   ├── audit.py                # AI action audit trail (requests, confirmation, results, rollback)
│   ├── idempotency.py          # Retry-safe writes via AI Assistant Action idempotency_key
│   ├── draft_workflow.py       # Draft → confirm workflow engine + field extraction
│   ├── conversation.py         # Guided field-collection conversation
│   ├── schema/                 # DOCTYPE_SCHEMAS (single source of truth for registry doctypes)
│   ├── intents/                # Natural-language intent detection (NL → doctype + action)
│   ├── safety/                 # Safety rules (illegal operations, duplication checks)
│   ├── questions/              # Field questions & hints
│   ├── validators/             # Field input validation
│   ├── reports/                # Report pattern detection
│   ├── handlers/               # Document handlers (create/view/print/query) + formatters
│   ├── workflows/              # Shipment receipt + stock issue workflow helpers
│   ├── duplication/            # Duplication detection
│   ├── rbac/                   # Role-based access control helpers
│   ├── voice/                  # Whisper.cpp STT + Piper TTS pipeline + toggle + emergency stop
│   ├── mcp/                    # MCP tool RPC endpoints + FrappeMCP permission-safe tool layer
│   ├── knowledge/              # ERPNext workflow knowledge base + source citations/freshness
│   ├── diagnostics/            # App health check
│   ├── attachments.py          # Upload validation + OCR text extraction (Frappe-managed files only)
│   ├── barcode.py              # Barcode/QR resolution + checksum validation
│   ├── evaluation.py           # Model quality evaluation helper
│   ├── llm/                    # Ollama interface + model allowlist/defaults
│   ├── doctype/
│   │   ├── ai_chat_message/    # Conversation history storage
│   │   └── ai_assistant_action/# Draft action lifecycle (pending → confirm/expire/failed/audit)
│   └── tests/                  # pytest suites (database-free + Frappe-backed integration)
│       ├── test_core.py        # schema, intents, safety, validators, questions
│       ├── test_security.py    # prompt injection, input validation, draft/confirm/rollback contracts
│       ├── test_rbac.py        # approval limits, supervisor, restrictions
│       ├── test_knowledge.py   # citations, freshness, doctype mapping
│       ├── test_infra.py       # barcode checksums, attachments, idempotency keys (no DB)
│       └── test_frappe_integration.py  # DB-backed: idempotency, audit, shipment confirm, rollback
├── .github/workflows/ci.yml    # CI: database-free suite + syntax + ruff
├── pyproject.toml              # Python packaging metadata + runtime requirements
└── README.md
```

---

## 🚀 Installation

### 1. Add the app to your bench

```bash
# from the bench root
bench get-app erp_ai /path/to/erp_ai
bench --site <site> install-app erp_ai
bench --site <site> migrate
```

The app is managed by bench, not pip. Python packaging metadata lives in
`pyproject.toml`, and the required runtime (Frappe Framework v15 + ERPNext v15)
is provided by the bench environment.

### 2. Set up the workspace (embeds chat + help on the dashboard)

```bash
bench --site <site> execute erp_ai.api.setup_workspace
bench --site <site> clear-cache
```

### 3. (Optional) Provision the voice stack

Voice input/output needs a local runtime:

```bash
sudo bash apps/erp_ai/erp_ai/voice/setup_voice.sh
```

Runtime files expected by `erp_ai.voice._ai_home()`:

- Whisper: `$HOME/ai/whisper.cpp/build/bin/whisper-cli`, model `$HOME/ai/models/ggml-tiny.bin`
- Piper: `$HOME/ai/piper/piper`, voices `$HOME/ai/models/en_US-lessac-medium.onnx` + `ur_PK-fasih-medium.onnx`
- `ffmpeg` on `PATH`

Voice input requires **HTTPS** except on `localhost`.

### 4. Add LLM models in Ollama

```bash
ollama pull qwen2.5:1.5b
# optional, for higher quality on stronger hardware:
# ollama pull qwen2.5:7b
```

Model defaults and the allowlist live in `erp_ai.llm.__init__`.

### 5. Rebuild assets & restart

```bash
bench build --app erp_ai
bench --site <site> clear-cache
# restart web (bench setup production or supervisor)
supervisorctl restart frappe-bench-web:
```


## 💬 Usage

### Chat locations
1. **Floating 🤖 widget** — bottom-right of every Desk page.
2. **Workspace** — `/app/ai-assistant-hub` (AI Assistant Hub) has an embedded live chat + help section.
3. **Full page** — `/app/ai-assistant` (Page: AI Assistant).
4. **Form button** — "🤖 Ask AI" button appears on form toolbars (Customer, Sales Invoice, Stock Entry…) — asks about the open document.

### Quick question chips (workspace)
`How many items?` `Total stock?` `Unpaid invoices` `Customer count?`

### Example prompts

**Data queries**
- `How many items do we have?`
- `How many customers / suppliers?`
- `Total stock across all warehouses?`
- `List unpaid invoices` / `Show me all items`
- `Search for pump springs`

**Workflows**
- `Spring shipment arrived from ABC Traders, vehicle LEA-4521, 500 pcs pump springs`
  → parses the shipment, shows a **preview** (supplier / items / quantities), then requires **"yes"** to create a Supplier + Stock Entry (Material Receipt) as DRAFT. Master data (supplier, items) is never auto-created without that explicit confirmation.
- `Issue 10 pump springs from Stores to Engr Ali Production` → Stock Entry Material Issue/Transfer with issued-to tracking
- `Make invoice for ABC Traders, 2 pump springs @ 500` → Sales Invoice DRAFT + print URL (approval-limit enforced)
- `Create item named Steel Rod price 100` / `Create customer named XYZ Corp` / `Create supplier named ABC Traders`
- `Print invoice SINV-00001` → PDF print URL

**Guidance / setup**
- `What do I need to make a sales invoice?`
- `How do I set up a new warehouse?`
- `How does the manufacturing BOM work?`
- `Help me set up a new ERP system`
- `What taxes apply in Pakistan?`

**Voice**
- Click 🎤 in chat → allow mic → speak → stop → words appear in the input.
- Answers auto-play with 🔊 (toggle 🔇 to disable). English by default, Urdu available via API `lang=ur`.

---

## 🔌 API Reference (all whitelisted)

### Chat / answers
| Endpoint | Params | Returns |
|---|---|---|
| `erp_ai.api.chat` | `prompt` | `{response}` |
| `erp_ai.api.ask` | `prompt, session` | `{response, session}` (basic) |
| `erp_ai.api.ask_v2` | `prompt, session, model` | `{response, session}` (MCP + KB + workflows) |
| `erp_ai.api.ask_v2_with_voice` | `prompt, session, model, voice` | `{response, session, audio_url}` |
| `erp_ai.api.ask_with_doc` | `doctype, name, prompt, session` | `{response, session}` (doc context) |

### Voice
| Endpoint | Params | Returns |
|---|---|---|
| `erp_ai.api.voice_to_text` | `audio` (base64), `fmt` | `{text}` |
| `erp_ai.api.text_to_speech` | `text`, `lang` (en/ur) | `{url}` (WAV under /files/tts/) |

### MCP tools
| Endpoint | Params | Returns |
|---|---|---|
| `erp_ai.mcp.mcp_list_tools` | — | `{tools:[...]}` |
| `erp_ai.mcp.mcp_call_tool` | `name, args(JSON string)` | tool result |

Tools: `query_doctype`, `get_document`, `create_document`, `update_document`, `print_document`, `search_documents`, `get_doctype_meta`, `submit_document`.
`create_document` accepts an optional `idempotency_key` for retry-safe creation.

### Infrastructure endpoints
| Endpoint | Params | Returns |
|---|---|---|
| `erp_ai.api.barcode_lookup` | `code` | resolved doctype + name (permission-checked, checksum-validated formats) |
| `erp_ai.api.ocr_extract_text` | `file_url` (a `/files/...` URL) | `{text}` from image/PDF (Frappe-managed uploads only) |
| `erp_ai.api.audit_history` | `session` (optional), `limit` | the caller's AI action audit trail |
| `erp_ai.api.knowledge_freshness` | — | knowledge sources with freshness + citations |
| `erp_ai.api.citation_for` | `doctype` | citation string for a doctype's knowledge source |
| `erp_ai.api.run_evaluation` | `category`, `limit` | model evaluation results (System Manager only) |

### Workflow handlers
| Endpoint | Params | Returns |
|---|---|---|
| `erp_ai.api.workflow_shipment_receipt` | `data` (JSON string: supplier, vehicle_no, items:[{item_code,qty,rate}], warehouse, remarks) | steps + entry |
| `erp_ai.api.workflow_stock_issue` | `data` (item_code, qty, from_warehouse, to_warehouse, issue_type, issued_to, department) | entry + next |
| `erp_ai.api.workflow_sales_invoice` | `data` (customer, items:[{item_code,qty,rate}], update_stock, taxes_template) | draft + print_url |

---

## ⚙️ Configuration

| Setting | Where | Notes |
|---|---|---|
| Default model | `frappe.conf.ai_model` or `DEFAULT_MODEL` in `erp_ai/llm/__init__.py` | `qwen2.5:1.5b` |
| Allowed models | `AI_ALLOWED_MODELS` in `erp_ai/llm/__init__.py` | `qwen2.5:1.5b`, `qwen2.5:3b`, `qwen2.5:7b` |
| Ollama URL | `OLLAMA_URL` in `erp_ai/llm/__init__.py` | `http://localhost:11434/api/generate` |
| Voice model paths | `erp_ai.voice._ai_home()` | env `AI_HOME` or `~/ai` or `/home/erpnext/ai` |
| Hook | `app_include_js = "/assets/erp_ai/js/ai_widget.js?v=4"` | loads widget on every desk page |
| TTS files | `sites/<site>/public/files/tts/*.wav` | served at `/files/tts/...` |
| Conversation store | Doctype `AI Chat Message` (fields: user, session_id, role, content) | per-user, last 8 used in context |
| Draft actions | Doctype `AI Assistant Action` (nonce, expires_on, idempotency_key) | confirmation lifecycle |


---

## 🤖 LLM Provider Configuration

ERP AI now supports **multiple LLM providers** beyond local Ollama. Configure in **AI Settings** (`/app/ai-settings` or via `bench --site <site> execute erp_ai.api.setup_ai_settings`).

### Supported Providers

| Provider | Type | Base URL | Default Model | Pricing |
|----------|------|----------|---------------|---------|
| **Ollama (Local)** | Local | `http://localhost:11434/api/generate` | `qwen2.5:1.5b` | Free (self-hosted) |
| **OpenRouter** | Cloud API | `https://openrouter.ai/api/v1/chat/completions` | `~openai/gpt-4o-mini` | Pay-per-token (aggregates 100+ models from OpenAI, Anthropic, Google, Mistral, etc.) |
| **Together AI** | Cloud API | `https://api.together.ai/v1/chat/completions` | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | Pay-per-token (open-source models) |
| **Groq** | Cloud API | `https://api.groq.com/openai/v1/chat/completions` | `llama-3.1-8b-instant` | Free tier + pay-per-token (fast Llama inference) |
| **Anthropic** | Cloud API | `https://api.anthropic.com/v1/messages` | `claude-3-5-haiku-20241022` | Pay-per-token (Claude models) |
| **OpenAI** | Cloud API | `https://api.openai.com/v1/chat/completions` | `gpt-4o-mini` | Pay-per-token (GPT models) |
| **Google Gemini** | Cloud API | `https://generativelanguage.googleapis.com/v1beta/models` | `gemini-2.0-flash` | Free tier + pay-per-token |
| **Mistral** | Cloud API | `https://api.mistral.ai/v1/chat/completions` | `mistral-small-latest` | Pay-per-token |
| **Custom API** | Any | Your URL | Your choice | Depends on provider |
| **LM Studio** | Local | `http://localhost:1234/v1/chat/completions` | `lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF` | Free (self-hosted) |

### Configuration Fields (AI Settings DocType)

**General Settings:**
- **Enable Speaker Output** — Admin toggle: enable/disable TTS speaker for AI responses
- **Voice Enabled By Default** — New chats start with voice on/off
- **Default Voice Model** — Piper voice: `en_US-lessac-medium`, `ur_PK-fasih-medium`

**LLM Provider Configuration:**
- **LLM Provider** — Dropdown: select your provider (Ollama, OpenRouter, Together AI, Groq, Anthropic, OpenAI, Google Gemini, Mistral, Custom API, LM Studio)
- **API Key** — API key for cloud providers (required for OpenRouter, Together AI, Groq, Anthropic, OpenAI, Google, Mistral)
- **Custom API Base URL** — Override endpoint for Custom API or LM Studio

**Model Selection:**
- **Default Model** — Model name for the selected provider (e.g., `qwen2.5:1.5b`, `gpt-4`, `claude-3-opus`, `llama-3.1-8b-instant`)
- **Available Models (JSON)** — Optional JSON list to populate model dropdown: [{"name": "qwen2.5:1.5b", "provider": "ollama"}, ...]

**Advanced Settings:**
- **Default Temperature** — 0.0 (deterministic) to 1.0 (creative), default 0.7
- **Max Tokens** — Response length limit, default 2048
- **Request Timeout (seconds)** — API timeout, default 120s

**Feature Toggles:**
- **Enable Chat History** — Store conversation history per user
- **Enable Voice Input (STT)** — Allow microphone input
- **Enable MCP Tools** — Allow document queries/creations via MCP
- **Enable Document Creation Workflows** — Allow draft → confirm workflows

**Provider-Specific Settings:**
- **OpenAI Organization ID** — For OpenAI organization billing
- **Anthropic API Version** — API version header (default: `2023-06-01`)
- **Google API Key** — Alternative key field for Gemini
- **Mistral API Key** — Alternative key field for Mistral

### Quick Setup Examples

#### Option 1: Keep using local Ollama (default)
No configuration needed. Ensure Ollama is running:
```bash
ollama serve
ollama pull qwen2.5:1.5b
```

#### Option 2: Use OpenRouter (access 100+ models via one API)
1. Get API key: https://openrouter.ai/api-keys
2. Go to AI Settings, select **OpenRouter** as provider
3. Enter your API key
4. Set model to e.g., `~openai/gpt-4o-mini` or `~anthropic/claude-3-haiku`

#### Option 3: Use Together AI (open-source models)
1. Get API key: https://api.together.ai/settings
2. Go to AI Settings, select **Together AI** as provider
3. Enter your API key
4. Set model to e.g., `meta-llama/Llama-3.3-70B-Instruct-Turbo`

#### Option 4: Use Groq (super-fast Llama inference)
1. Get API key: https://console.groq.com/keys
2. Go to AI Settings, select **Groq** as provider
3. Enter your API key
4. Set model to e.g., `llama-3.1-8b-instant`

#### Option 5: Use LM Studio (local GUI for open models)
1. Install LM Studio: https://lmstudio.ai
2. Download a model in LM Studio
3. Start local server in LM Studio (default port 1234)
4. Go to AI Settings, select **LM Studio** as provider
5. Optionally set Custom API Base URL to `http://localhost:1234/v1/chat/completions`

### Model Recommendations

**For speed + low cost:**
- Ollama: `qwen2.5:1.5b` or `llama3.2:3b`
- OpenRouter: `~openai/gpt-4o-mini` or `~google/gemini-flash-1.5`
- Groq: `llama-3.1-8b-instant`

**For quality (complex tasks):**
- Ollama: `qwen2.5:7b` or `llama3.1:8b`
- OpenRouter: `~openai/gpt-4o` or `~anthropic/claude-3-opus`
- Together AI: `meta-llama/Llama-3.3-70B-Instruct-Turbo`

**For coding tasks:**
- OpenRouter: `~openai/gpt-4o` or `~deepseek/codestral-latest`
- Together AI: `gpt-oss-120B` or `deepseek-coder`

### Admin Speaker Toggle (Voice On/Off)

The **"Enable Speaker Output"** checkbox in AI Settings is an **admin-only master toggle** that controls whether any text-to-speech (TTS) output is generated:

- **Location**: `/app/ai-settings` → "Enable Speaker Output"
- **Permission**: System Manager role only (admin)
- **When ON (default)**: TTS is available; users can still toggle voice per-chat via `/app/voice-toggle` or the chat interface
- **When OFF**: All TTS is disabled for every user, regardless of individual voice preferences. The `is_voice_enabled()` check returns `False` immediately before any TTS subprocess is launched.

**Implementation**:
1. `erp_ai/voice/toggle.py` — `is_voice_enabled()` checks `AI Settings.speaker_enabled` first
2. `erp_ai/api.py` — `ask_v2_with_voice()` and `text_to_speech_endpoint()` both call `is_voice_enabled()` before TTS

---


---

## 🩻 Troubleshooting & Debugging

### Widget / chat not appearing on the workspace
1. Hard refresh (`Ctrl+Shift+R`) — assets are cached (hence `?v=4`).
2. Open DevTools Console; look for `[AI Widget]` logs:
   - `Script loaded ...` → script executing
   - `Checking workspace: path=... isWs=true` → route detected
   - `Target found: desk-page page-main-content` → container found
   - `Chat panel injected into workspace` → success
3. If no logs: the file is cached/old → `bench build --app erp_ai` + restart web.
4. Confirm the script tag: `grep ai_widget <page html>` → `src="/assets/erp_ai/js/ai_widget.js?v=4"`.
5. Check the served asset has the functions:
   `curl -s http://localhost/assets/erp_ai/js/ai_widget.js | grep -c mountWorkspaceChat` (expect ≥3).

### Workspace blank / Editor.js quirks
- Frappe v15 **sanitizes** paragraph HTML; the chat is injected by JS (`mountWorkspaceChat` → `buildWorkspaceChat`) into `.page-main-content`, not stored as HTML.
- If workspace content fails to render: `bench --site spi.local execute erp_ai.api.setup_workspace` then clear caches + restart.

### Voice input (mic) not working
- **HTTPS is required** except `localhost`. Use `https://spi.local`.
- Console message `Mic permission denied: ...` → grant mic permission (lock icon in address bar).
- `Microphone needs HTTPS (or localhost)` → you're on plain http.
- transcribing error / `(no speech detected)` → check whisper-cli exists at `~/ai/whisper.cpp/build/bin/whisper-cli` + model `~/ai/models/ggml-tiny.bin`; test: `echo hi | ~/ai/whisper.../whisper-cli -m ~/ai/models/ggml-tiny.bin -`.

### TTS (voice output) not playing
- API returns an `audio_url`? `curl -s -X POST ... erp_ai.api.text_to_speech -d 'text=hi'`
- File served? `curl -s -o /dev/null -w '%{http_code}' http://spi.local/files/tts/<file>.wav` (expect 200).
- `[Errno 18] Invalid cross-device link` was fixed with `shutil.move` (no longer expected).
- Piper model missing → rerun `voice/setup_voice.sh` or place `en_US-lessac-medium.onnx` / `ur_PK-fasih-medium.onnx` in `~/ai/models/`.

### AI answers wrong/old data
- Docs are created as **DRAFT** — submit them so stock/accounts update.
- Check `AI Chat Message` records for the session.
- Verify Ollama is running: `curl http://localhost:11434/api/generate -d '{"model":"qwen2.5:1.5b","prompt":"hi"}'`.

### Assets / build issues
```bash
# force full rebuild
bench build --app erp_ai
bench --site spi.local clear-cache
# restart web
supervisorctl restart frappe-bench-web:
```

### Python errors in the app
```bash
find apps/erp_ai -name '__pycache__' -exec rm -rf {} + -o -name '*.pyc' -delete
python3 -m py_compile apps/erp_ai/erp_ai/api.py apps/erp_ai/erp_ai/mcp/server.py
```

### Common error references
| Error | Cause | Fix |
|---|---|---|
| `TabError` / `IndentationError` | mixed tabs/spaces after edits | `python3 -m py_compile ...` and fix indentation |
| `NameError: _json is not defined` | missing local import in handler | `import json as _json` in the function |
| `Quantity for Item cannot be zero` | qty not parsed | provide qty, or missing item data — AI will ask |
| `item_code required in every item` | item name not resolved | ensure item exists or is created |
| `Invalid cross-device link` | `os.rename` across devices | use `shutil.move` (done) |
| `Failed to get method ...` | stale code / not migrated | `bench --site <site> migrate` + restart |
| `observeWorkspace: undefined` | old cached file | hard refresh; rebuild with `?v=` bump |

---

## 🧪 Testing

### Database-free tests (no Frappe / no site required)
```bash
cd apps/erp_ai
python -m pytest erp_ai/tests/test_core.py erp_ai/tests/test_security.py \
  erp_ai/tests/test_rbac.py erp_ai/tests/test_knowledge.py erp_ai/tests/test_infra.py \
  -q -p no:cacheprovider
```
Covers: schema integrity, intent detection, safety rules, validators, questions,
role/RBAC policies, knowledge source citations & freshness, barcode checksums,
attachment validation (MIME spoofing, sizes, traversal), and idempotency keys.

### Frappe-backed tests (needs a real site)
```bash
bench --site <site> run-tests --app erp_ai
```
`erp_ai/tests/test_erp_ai_security.py` requires a live Frappe environment
(it imports `frappe` directly) and is skipped by the pure-Python suite above.

### CI
`.github/workflows/ci.yml` runs the database-free suite, `ast.parse` syntax
check, and Ruff on push/PR. Run Frappe-backed tests inside your bench:
```bash
bench --site <site> run-tests --app erp_ai
```

### Manual smoke tests

```bash
# Message count queries
curl -s -m120 -H "Authorization: token `cat ~/ai/.erp_token`" \\
  'http://localhost/api/method/erp_ai.api.ask_v2' \\
  --data-urlencode 'prompt=How many items?'

# Shipment workflow
curl -s -m120 -H "Authorization: token `cat ~/ai/.erp_token`" \\
  'http://localhost/api/method/erp_ai.api.ask_v2' \\
  --data-urlencode 'prompt=Spring shipment arrived from ABC Traders, vehicle LEA-4521, 500 pcs pump springs'

# TTS
curl -s -H "Authorization: token `cat ~/ai/.erp_token`" \\
  'http://localhost/api/method/erp_ai.api.text_to_speech?text=Hello' \\
# expect: {"message":{"url":"/files/tts/....wav","text":"Hello"}}

# MCP
curl -s -H "Authorization: token `cat ~/ai/.erp_token`" \\
  'http://localhost/api/method/erp_ai.mcp.mcp_list_tools'
```

---

## 🧹 Maintenance

```bash
# clean caches & logs
bench --site spi.local clear-cache
find sites/spi.local/logs -name "*.log" -mtime +3 -delete

# clean python caches
find apps/erp_ai -type d -name '__pycache__' -exec rm -rf {} +

# git housekeeping
cd apps/erp_ai && git add -A && git commit -m 'update' && git gc --auto
```

---

## 🖥 Hardware requirements (verified on this server)
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
- Frappe Framework **v15**, ERPNext **v15**
- Coexists with other apps (fbr_pos_integration, etc.) — only hook is `app_include_js`; no core overrides.
- All endpoints are `@frappe.whitelist` (auth applied). Document operations enforce `frappe.has_permission()` — no `ignore_permissions=True` in the MCP tool layer. Workspace setup requires System Manager role.

---

## 📄 License
MIT
