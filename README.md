# ERP AI — Frappe/ERPNext AI Assistant (Local, Private)

A self-contained Frappe app that adds a **local AI assistant** to any ERPNext site:
- 🤖 **Chat with memory** — floating widget on every Desk page + full chat page + workspace
- 📄 **ERP-aware answers** — summarizes any document, drafts emails, knows your installed apps
- 🎤 **Voice** — speech-to-text (whisper.cpp), text-to-speech (Piper, English + **Urdu**)
- 🔒 **100% local & private** — runs on Ollama (CPU), no data leaves the machine

## Requirements
- Frappe Framework v14/v15 + ERPNext (works on any bench project)
- Debian/Ubuntu with sudo, ~4GB free disk, 8GB RAM (more RAM = smarter models)

## Install on a new Frappe project

```bash
# 1. get the app into the bench
cd ~/frappe-bench
bench get-app <path-or-git-url-of-erp_ai>

# 2. install on the site
bench --site yoursite.local install-app erp_ai
bench --site yoursite.local migrate
bench build --app erp_ai
bench restart

# 3. create the "AI Assistant Hub" workspace (page + shortcut)
bench --site yoursite.local execute erp_ai.api.setup_workspace

# 4. voice stack (optional) — deps, Ollama, whisper.cpp, piper, voices, models
bash ./apps/erp_ai/erp_ai/voice/setup_voice.sh

# 5. API token for voice->ERP lookups (voice assistant only)
bench --site yoursite.local execute erp_ai.api.make_token --args "['Administrator']"
# paste the printed key:secret into $AI_HOME/.erp_token (chmod 600)
```

## What gets installed where (voice stack)
| Path | Purpose |
|---|---|
| `$AI_HOME` (default `~/ai`) | runtime root |
| `$AI_HOME/whisper.cpp/` | compiled speech-to-text engine |
| `$AI_HOME/models/` | whisper + piper voice models (EN + UR) |
| `$AI_HOME/piper/` | piper TTS binary |
| `$AI_HOME/.erp_token` | API token for voice→ERP lookups |

## Using it
- **Desk:** click the floating 🤖 button (bottom-right) → ask anything
- **Full page:** `/app/ai-assistant`
- **Workspace:** sidebar → "AI Assistant Hub"
- **Voice:** `ai-voice` (or `ai-voice ur` for Urdu, `ai-voice --text "..."` for one-shot)

## API
| Endpoint | Purpose |
|---|---|
| `erp_ai.api.ask(prompt, session)` | chat with memory (saved in AI Chat Message) |
| `erp_ai.api.chat(prompt)` | stateless one-shot chat |
| `erp_ai.api.summarize_doc(doctype, name)` | AI summary of any document (fuzzy name match) |
| `erp_ai.api.draft_email(purpose, recipient, doctype, name)` | draft emails grounded on ERP data |

All endpoints require a logged-in session (Desk uses cookies automatically) or
`Authorization: token <key>:<secret>` for external callers.

## Notes
- The AI model does **not** self-train on your data. Conversations are stored in the
  `AI Chat Message` doctype for context memory and auditing (admin can purge anytime).
- Installed apps list (incl. custom apps like fbr_pos_integration) is injected into
  every answer's context dynamically.
- After upgrading RAM, switch `DEFAULT_MODEL` in `erp_ai/api.py` (e.g. `qwen2.5:7b`)
  for much smarter answers.
