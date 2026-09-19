# Skill: Local LLM runtime (Ollama / Anthropic / Google)

**Related:** [ROADMAP.md](../ROADMAP.md) Phase 1.1, 4.1 · [README.md](../README.md) "LLM providers" · [UPGRADE.md](../UPGRADE.md) "Voice runtime" · `erp_ai.llm` · `erp_ai.api.ask_llm()`

## What this skill covers

ERP AI's LLM layer is the spine of the assistant: chat answers, tool-call
reasons, draft preview text, and voice round-trips all flow through it.
This skill describes the runtime as it *actually is* today, what it depends
on, what breaks, and what robustness work is planned.

## Current runtime (as of 2026-09-19)

### Providers

ERP AI supports three provider backends, selected in the **AI Settings**
DocType:

| Provider | Backend | Notes |
|---|---|---|
| Ollama | Local HTTP at `ollama_url` (default `http://localhost:11434`) | Runs locally; models pulled into `~/.ollama`. |
| Anthropic | Cloud API | Requires `anthropic_api_key` in AI Settings. |
| Google | Cloud API (Gemini) | Requires Google provider config in AI Settings. |

The provider is chosen in `erp_ai.llm` based on the AI Settings config, and
`erp_ai.api.ask_llm()` delegates to the appropriate `_ask_*()` helper.

### What `ask_llm()` does (the god node)

`erp_ai.api.ask_llm()` is the central LLM entry point. It:

- Accepts a prompt + context (conversation history, system prompt, tools info).
- Routes to the configured provider.
- Returns the model's text reply (or a structured tool call, in the MCP path).
- Is referenced by chat, voice, MCP tools, draft preview, and knowledge answer paths.

### Settings live in AI Settings

The relevant settings are stored in the `AI Settings` DocType and read at
runtime. Do not edit them by hand in the database; use the DocType.

Key settings (as of 2026-09-19):

- Provider selection.
- `default_model` (model name for the chosen provider).
- `ollama_url` (for the Ollama provider).
- Provider API keys (Anthropic / Google).
- Voice-related settings (Whisper path, model, TTS) — see the voice skill
  when it exists.

## What can break (robustness gaps today)

These are the gaps that Phase 1.1 in ROADMAP.md is meant to close:

1. **No per-request timeout.** A slow or stalled Ollama instance can hang
   `ask_llm()` until the HTTP client times out at a high level. There is no
   app-level timeout ceiling today.
2. **No retry policy.** If Ollama returns a transient error, the call fails
   once. Read-only calls (data questions) are good candidates for a single
   retry with backoff.
3. **`health()` is incomplete.** `erp_ai.api.health()` originally called the
   now-deleted `erp_ai.diagnostics` module. It was fixed to not crash, but
   does not yet give a full "runtime healthy" picture (provider reachable +
   model loaded + voice runtime available).
4. **Voice round-trip has no stage timeout budget.** The voice path chains
   STT → LLM → TTS. If any stage hangs, the round trip stalls. See the voice
   skill (to be added) for the voice-specific half of this.

## How to test LLM robustness

- **Reachability.** Point AI Settings at an unreachable Ollama URL and confirm
  the assistant returns a clear degradation message, not a traceback.
- **Timeout.** If you can simulate a slow response (e.g., a model that is
  mid-load), confirm the call fails within the timeout ceiling.
- **Retry.** For a read-only data question, cause a transient Ollama error on
  the first attempt and confirm a single retry is attempted and logged.
- **Health.** Call the health path (internally) and confirm it reports provider
  status without crashing.

## Planned robustness work (ROADMAP Phase 1.1)

- Add a per-request timeout (settings field `ollama_timeout` + hard ceiling).
- Add a single retry with backoff for read-only calls.
- Make `health()` report a structured summary: provider reachable, model
  loaded, voice runtime available, (if enabled) knowledge-source freshness.
- Add audit notes when a retry happens (ties into Phase 1.3 structured logging).

## Multi-model routing (ROADMAP Phase 4.1 — deferred)

Today there is one `default_model` per provider. Phase 4.1 will add:

- Capability tags per model (fast-data, drafting, voice).
- Routing by intent (small model for lookups, larger model for drafting).
- Fallback when the primary is unavailable.

This is deferred until Phase 1 makes the single-model path robust.

## External references

- [Collabnix — Ollama API integration, production patterns](https://collabnix.com/ollama-api-integration-building-production-ready-llm-applications/) — timeouts, backoff, model-loading-failure handling, metrics.
- [Local AI Master — cascaded Whisper → Ollama → Piper voice assistant](https://localaimaster.com/blog/local-voice-assistant-whisper-ollama-piper/) — per-stage latency budget, streaming, timeouts.
- [fuzzy.website — safe agentic actions: idempotency, audit, fuzzy intent](https://fuzzy.website/designing-safe-agentic-actions-idempotency-auditing-and-fuzz/) — applies to the LLM reply path as well as the action path.

## Keep this skill current

If the provider stack changes (new provider, new settings field, new timeout
behavior, new health output), update this skill and the relevant ROADMAP
phase. This skill is a fact document, not a plan — it should always match
the code.
