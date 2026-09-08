# ERP AI — Intelligent AI Assistant for ERPNext

A complete AI assistant (chat + voice) integrated into **Frappe Framework v15 / ERPNext v15**. It can answer questions about your ERP data, guide users through any business workflow, create and update documents, print, and speak answers aloud in English and Urdu — all running **fully offline** on your own server.

---

## ✨ Features

| Capability | Description |
|---|---|
| 💬 **Chat** | Floating 🤖 widget on every page + embedded workspace chat + full-page chat |
| 🎤 **Voice input** | Speak in the chat (MediaRecorder → Whisper.cpp STT), words appear in the input box — needs HTTPS |
| 🔊 **Voice output** | AI answers played aloud via Piper TTS (English `en_US-lessac-medium`, Urdu `ur_PK-fasih-medium`) — 🔊/🔇 toggle |
| 📊 **Real data answers** | "How many items?", "Total stock?", "Unpaid invoices?" → exact numbers from the DB |
| 🛠 **MCP tool access** | Query any doctype, list/search docs, get doc details, create/update/submit documents |
| 📦 **Workflow NLP** | Plain-language shipment receipt, stock issue, invoice creation, item/customer/supplier creation |
| 🧠 **Knowledge base** | Full ERPNext workflow KB injected into every answer (selling, buying, stock, manufacturing, accounting, setup) |
| 👤 **Per-user memory** | Each user has private conversation history stored in `AI Chat Message` |
| 🎭 **Role-aware** | Admins get technical detail; operators get short step-by-step guidance |
| 📄 **Print links** | AI returns PDF print URLs for created/submitted documents |

---

## 📦 Components

```
erp_ai/
├── erp_ai/
│   ├── api.py                  # All API endpoints + workflow handlers
│   ├── mcp/
│   │   ├── __init__.py         # mcp_list_tools / mcp_call_tool whitelisted endpoints
│   │   └── server.py           # FrappeMCP class (tool implementations)
│   ├── knowledge/
│   │   └── erpnext_kb.py       # ERPNext workflow knowledge base (fed to AI)
│   ├── workspace/
│   │   └── ai_assistant_hub/   # Workspace fixture
│   ├── page/
│   │   └── ai_assistant/       # Dedicated full chat page
│   ├── doctype/
│   │   └── ai_chat_message/    # Conversation history storage
│   └── voice/
│       ├── setup_voice.sh      # Provision Whisper.cpp + Piper (run as root)
│       └── voice_assistant.py  # Voice pipeline helpers
├── public/
│   └── js/
│       └── ai_widget.js        # Floating widget, workspace chat, voice, TTS playback
└── README.md
```

---

## 🚀 Installation

### 1. Install the app
```bash
# from frappe-bench
bench get-app erp_ai /path/to/erp_ai
bench --site spi.local install-app erp_ai
bench --site spi.local migrate
```

### 2. Set up the workspace (embeds chat + help on the dashboard)
```bash
bench --site spi.local execute erp_ai.api.setup_workspace
bench --site spi.local clear-cache
```

### 3. Provision voice stack (STT/TTS)
```bash
# Requires: ffmpeg, compile tools. Builds whisper.cpp and Piper.
sudo bash apps/erp_ai/erp_ai/voice/setup_voice.sh
```
Runtime files expected:
- Whisper: `$HOME/ai/whisper.cpp/build/bin/whisper-cli`, model `$HOME/ai/models/ggml-tiny.bin`
- Piper: `$HOME/ai/piper/piper`, voices `$HOME/ai/models/en_US-lessac-medium.onnx` + `ur_PK-fasih-medium.onnx`

### 4. Add models for the LLM
```bash
ollama pull qwen2.5:1.5b          # default reasoning model
# (optional) ollama pull qwen2.5:7b   for higher quality on stronger hardware
```

### 5. Rebuild assets & restart
```bash
bench build --app erp_ai
cd apps/erp_ai && cp public/js/ai_widget.js erp_ai/public/js/ai_widget.js && cd ../..
bench build --app erp_ai
bench --site spi.local clear-cache
# restart web (bench setup production or supervisor)
supervisorctl restart frappe-bench-web:
```

### 6. HTTPS (for mic voice input)
```bash
sudo apt-get install -y mkcert && mkcert -install
mkcert spi.local 192.168.10.2 127.0.0.1 localhost
# add a 443 ssl server block to nginx pointing at the .pem files
sudo nginx -t && sudo systemctl reload nginx
```

---

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
- `Spring shipment arrived from ABC Traders, vehicle LEA-4521, 500 pcs pump springs` → creates Supplier + Stock Entry (Material Receipt) as DRAFT
- `Issue 10 pump springs from Stores to Engr Ali Production` → Stock Entry Material Issue/Transfer with issued-to tracking
- `Make invoice for ABC Traders, 2 pump springs @ 500` → Sales Invoice DRAFT + print URL
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
| Default model | `frappe.conf.ai_model` or `DEFAULT_MODEL` in api.py | `qwen2.5:1.5b` |
| Ollama URL | `OLLAMA_URL` in api.py | `http://localhost:11434/api/generate` |
| Voice model paths | `erp_ai.api._ai_home()` | env `AI_HOME` or `~/ai` or `/home/erpnext/ai` |
| Hook | `app_include_js = "/assets/erp_ai/js/ai_widget.js?v=2"` | loads widget on every desk page |
| TTS files | `sites/<site>/public/files/tts/*.wav` | served at `/files/tts/...` |
| Conversation store | Doctype `AI Chat Message` (fields: user, session_id, role, content) | per-user, last 8 used in context |

---

## 🩻 Troubleshooting & Debugging

### Widget / chat not appearing on the workspace
1. Hard refresh (`Ctrl+Shift+R`) — assets are cached (hence `?v=2`).
2. Open DevTools Console; look for `[AI Widget]` logs:
   - `Script loaded ...` → script executing
   - `Checking workspace: path=... isWs=true` → route detected
   - `Target found: desk-page page-main-content` → container found
   - `Chat panel injected into workspace` → success
3. If no logs: the file is cached/old → `bench build --app erp_ai` + restart web.
4. Confirm the script tag: `grep ai_widget <page html>` → `src="/assets/erp_ai/js/ai_widget.js?v=2"`.
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
cd apps/erp_ai && cp public/js/ai_widget.js erp_ai/public/js/ai_widget.js && cd ../..
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
- All endpoints are `@frappe.whitelist` (auth applied), docs created with `ignore_permissions=True` (same user context).

---

## 📄 License
MIT
