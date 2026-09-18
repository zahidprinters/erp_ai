# ERP AI Release Notes

Changelog for the ERP AI Frappe app. Entries follow [Keep a Changelog](https://keepachangelog.com/)
style. The latest release is at the bottom of this file.

---

## [Unreleased]

### Added
- `LICENSE` file (MIT) so GitHub detects the license and the repository is
  explicitly open-source-friendly for contributions.
- `CONTRIBUTING.md` describing the Frappe-specific contribution workflow
  (branch strategy, Ruff linting, security boundaries, testing).
- `CODE_OF_CONDUCT.md` (Contributor Covenant v2.1).
- `SECURITY.md` describing the security model and how to report vulnerabilities.
- GitHub issue templates (`bug_report.md`, `feature_request.md`).
- Project structure and a table of contents in `README.md`.

### Changed
- Removed the dead `detect_intent` import from `erp_ai/api.py`.
- Removed the dead `detect_report`/`_handle_report` call paths from the
  production flow (`erp_ai/handlers/__init__.py`).
- Fixed the `knowledge` import in `erp_ai/api.py` to use
  `erp_ai.knowledge.erpnext_kb` (the module that exists on disk).

### Removed / deleted modules
The following module packages were deleted on disk and are no longer available.
Their callers were guarded so the app degrades gracefully:
- `erp_ai/diagnostics`
- `erp_ai/duplication`
- `erp_ai/nlq`
- `erp_ai/reports`

Both `erp_ai.diagnostics` and `erp_ai.duplication` are imported in
`try/except ImportError` blocks (`api.py:health()` and the three create handlers)
so the rest of the app keeps working when those modules are absent.

### Security
- Confirmed the MCP tool layer still enforces the DocType allowlist and never
  uses `ignore_permissions=True`.
- Confirmed public workflow endpoints still return a draft preview and never
  auto-create/auto-submit financial/stock documents without confirmation.

---

# ERP AI Release Notes - LLM Provider Multi-Support & Admin Settings

## Release Date: September 2024
## Version: Production-Ready

---

## What's New

### 1. Multi-LLM Provider Support

ERP AI now supports **10 different LLM providers**, giving administrators complete flexibility to choose the best AI backend for their needs:

**Local Options (Free, Self-Hosted):**
- **Ollama** - Local LLM runner (default, already integrated)
- **LM Studio** - Local GUI for open-source models

**Cloud API Options (Pay-per-token):**
- **OpenRouter** - Single API for 100+ models (OpenAI, Anthropic, Google, Mistral, etc.)
- **Together AI** - High-performance open-source model hosting
- **Groq** - Ultra-fast Llama inference
- **Anthropic** - Claude models (Haiku, Sonnet, Opus)
- **OpenAI** - GPT-4, GPT-4o, GPT-3.5 models
- **Google Gemini** - Gemini Flash, Pro models
- **Mistral** - Mistral Small, Medium, Large models
- **Custom API** - Any OpenAI-compatible endpoint

### 2. Admin Settings UI

New **AI Settings** DocType (`/app/ai-settings`) with comprehensive configuration:

**Speaker Control (Admin Only):**
- **Enable Speaker Output** - Master toggle to enable/disable TTS
- **Voice Enabled By Default** - New chat voice state
- **Default Voice Model** - Piper voice selection (EN/UR)

**LLM Provider Selection:**
- **LLM Provider** - Dropdown with all 10 providers
- **API Key** - Secure password field for cloud APIs
- **Custom API Base URL** - For Custom API / LM Studio

**Model Selection:**
- **Default Model** - Per-provider model name
- **Available Models (JSON)** - Optional model dropdown list

**Advanced Controls:**
- Temperature (0.0-1.0)
- Max Tokens (response length)
- Request Timeout (seconds)

**Feature Toggles:**
- Chat History
- Voice Input (STT)
- MCP Tools
- Document Creation Workflows

### 3. Provider-Specific Settings

- OpenAI Organization ID
- Anthropic API Version
- Google API Key (alternative)
- Mistral API Key (alternative)

---

## Configuration Examples

### Using OpenRouter (Recommended for flexibility)
1. Get free API key: https://openrouter.ai/api-keys
2. AI Settings → Provider: **OpenRouter**
3. API Key: your key
4. Model: ~openai/gpt-4o-mini (cheap) or ~anthropic/claude-3-haiku

### Using Together AI (Open-source models)
1. Get API key: https://api.together.ai/settings
2. AI Settings → Provider: **Together AI**
3. API Key: your key
4. Model: meta-llama/Llama-3.3-70B-Instruct-Turbo

### Using Groq (Fast inference)
1. Get API key: https://console.groq.com/keys
2. AI Settings → Provider: **Groq**
3. API Key: your key
4. Model: llama-3.1-8b-instant

### Using Local Ollama (Default, no cost)
Already configured. Just ensure Ollama is running:
```bash
ollama serve
ollama pull qwen2.5:1.5b
```

---

## Files Changed

### Core LLM Module
- `erp_ai/llm/__init__.py` - Complete rewrite with multi-provider support
  - New `ask_llm()` function (replaces direct Ollama calls)
  - Provider configuration dictionary
  - Anthropic-specific API handler
  - Google Gemini-specific API handler
  - OpenAI-format chat completions handler
  - Backward-compatible `ask_ollama()` legacy function

### API Layer
- `erp_ai/api.py` - Updated to use new `ask_llm()` with settings
  - All chat endpoints now use configured provider
  - Model parameter passed through to LLM layer

### DocType Configuration
- `erp_ai/doctype/ai_settings/ai_settings.json` - Enhanced fields
  - Added 15+ new configuration fields
  - Section breaks for organization
  - Provider dropdown with all options

### Documentation
- `README.md` - Added comprehensive LLM Provider Configuration section
  - Provider comparison table
  - Setup guides for each provider
  - Model recommendations by use case

---

## Testing

All existing tests continue to pass. The new `ask_llm()` function is backward compatible with existing `ask_ollama()` calls.

To test a specific provider:
```python
from erp_ai.llm import ask_llm

# Test with different providers
response = ask_llm("Hello", provider="Ollama (Local)")
response = ask_llm("Hello", provider="OpenRouter", api_key="your_key")
response = ask_llm("Hello", provider="Groq", api_key="your_key")
```

---

## Security Notes

- API keys stored in Doctype (password field - masked in UI)
- All provider calls go through permission-checked channels
- Custom API URLs validated before use
- No API keys logged or exposed in responses
- **Admin speaker master toggle**: When "Enable Speaker Output" is unchecked in AI Settings, all TTS is disabled for every user regardless of individual preferences

---

## Voice & Speaker Control

### Admin Master Toggle (Speaker Enabled)

The **"Enable Speaker Output"** checkbox in AI Settings is an **admin-only master toggle** that can shut off all text-to-speech speaker output for every user:

- **Location**: `/app/ai-settings` → "Enable Speaker Output" checkbox
- **Permission**: System Manager role only (admin)
- **Effect**: When unchecked, `is_voice_enabled()` returns `False` for all users, bypassing all voice output
- **Override**: No user-level preference can override this — it's the master kill switch

**Implementation**:
1. `erp_ai/voice/toggle.py` — `is_voice_enabled()` now checks `AI Settings.speaker_enabled` first
2. `erp_ai/api.py` — `ask_v2_with_voice()` and `text_to_speech_endpoint()` both check `is_voice_enabled()` before calling TTS

---

## Migration Guide

**For existing Ollama users:** No changes needed. Default provider is still Ollama (Local).

**To switch providers:**
1. Go to AI Settings (/app/ai-settings)
2. Select your provider from dropdown
3. Enter API key (for cloud providers)
4. Set your preferred model
5. Save - changes take effect immediately

**To disable speaker:**
1. Go to AI Settings
2. Uncheck "Enable Speaker Output"
3. Save - speaker disabled for all users

---

## Model Recommendations

**Best for production (balanced):**
- OpenRouter: ~openai/gpt-4o-mini (fast, cheap, good quality)
- Groq: llama-3.1-8b-instant (free tier available)

**Best for quality:**
- OpenRouter: ~anthropic/claude-3-opus
- Together AI: meta-llama/Llama-3.3-70B-Instruct-Turbo

**Best for speed:**
- Ollama: qwen2.5:1.5b (local, instant)
- Groq: llama-3.1-8b-instant (cloud, very fast)

**Best for coding:**
- OpenRouter: ~deepseek/codestral-latest
- Together AI: gpt-oss-120B

---

## Verification Checklist

Before going live with a new provider:

- [ ] API key is valid and has sufficient quota
- [ ] Model name is correct for the provider
- [ ] Test chat works: Ask a simple question
- [ ] Voice works (if enabled): Check speaker output
- [ ] Timeout is appropriate for model latency
- [ ] Temperature is set correctly (0.7 default)

---

## Support

For issues:
1. Check AI Settings → verify provider, API key, model
2. Check Ollama is running (if using local)
3. Check network connectivity to API endpoint
4. Review error messages in browser console or server logs
