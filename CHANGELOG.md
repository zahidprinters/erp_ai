# CHANGELOG

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Production-grade README.md covering all capabilities, API reference, architecture, installation, usage, troubleshooting, and development guide.
- `skills/` directory with `SKILLS.md` index and `skills/local-llm-runtime.md` skill documentation.
- `ARCHITECTURE.md` summarizing the codebase god nodes and community structure (from graphify audit).
- `UPGRADE.md` for site administrators covering upgrade migrations, seeding, and settings.
- `ROADMAP.md` — phase-based improvement roadmap.

- `erp_ai.conversation` now auto-confirms a pending guided draft when the user replies with a clear affirmative (e.g. "yes", "sure", "go ahead", "create it"). The gate is intentionally strict: hedged/qualified yeses ("yes but", "yeah maybe") and prompt-injection attempts are NOT treated as affirmative. Clear negatives ("no", "not now", "cancel") stop the guided flow without creating anything. Only confirms, never auto-submits.
- `erp_ai.api.ask_v2` is now `@frappe.whitelisted` and accepts an optional `audio_base64` parameter that is transcribed via the local Whisper path before processing. The old non-whitelisted `ask_v2` duplicate is removed.
- `erp_ai.api.ask` is now `@frappe.whitelisted` (it already called `_assistant_reply` under the hood; the decorator was missing).
- New standalone pure-Python module `erp_ai.affirm` with the affirmative/negative detector functions (`is_affirmative`, `is_negative`, `auto_confirm_reply`) so the DB-free test suite can cover them without a Frappe context.
- **Phase 1.2 — verifiable citations + real freshness**: `KnowledgeSource.citation_dict()` returns machine-verifiable metadata (source id, url, version, freshness, 200-char excerpt, doctype); `erp_ai.api.citation_for` now returns this verifiable dict (unknown doctypes get `citation: None` — never an invented reference); `check_freshness()` returns fresh/stale partition with a `reindex_required` trigger and supports a custom `max_days` TTL; stale sources are flagged `[STALE]` in human citations; `erp_ai.api.knowledge_freshness` includes the verifiable metadata per source.
- **Phase 1.3 — structured error logging**: `log_error_safely()` accepts `context` (dict of action_id/provider/model/session/tool/user, rendered as a machine-readable `context: {json}` line) and `retryable` (bool, or an exception auto-classified by `_classify_retryable`: timeout/connection errors → retryable, everything else → fatal, rendered as a `class:` line). Wired at the AI action failure points: `confirm_draft` execution failures (action/doctype/session/user), MCP `call_tool` and `create_document` exceptions (tool/doctype/user), and `ask_llm` chat failures (provider/model/session/user). Existing callers unchanged; stripped-stack and never-raise guarantees preserved.
- **Phase 2.1 — voice timeout budget + clean unavailability**: `erp_ai.voice.STAGE_BUDGET` documents the per-stage ceilings (ffmpeg 30 s / Whisper 120 s / Piper 30 s; the LLM stage shares the Phase 1.1 clamp); `voice_runtime_available()` reports exactly which runtime components are missing; `ask_v2_with_voice` never fails the turn on a broken TTS stage — the text answer survives and a clean `voice_error` replaces the audio. Fixed the `ask_v2` audio path: the base64 payload is now decoded before transcription (it used to be handed through undecoded, so the combined audio path could never transcribe).

### Fixed

- `erp_ai.api.voice_to_text` is now `@frappe.whitelisted` — the widget mic→Whisper STT path now works over HTTP (was previously Not permitted).
- `erp_ai.api.confirm_workflow_action` and `cancel_workflow_action` are now `@frappe.whitelisted` — the draft→confirm loop now has a complete HTTP completion path.
- `erp_ai.api.health()` no longer calls the deleted `erp_ai.diagnostics` module; now reports configured LLM provider + voice runtime reachability.
- Removed dead `erp_ai/config/` package (empty, never used).
- Removed `DEAD_CODE_CLEANUP.md` (was a dev-process log).
- Removed stale `erp_ai/www/` and empty root `tests/` directories.
- Fixed trailing-newline lint in `scripts/sync_workspace.py`.

### Changed

- README.md API reference table synced to the actual 35+ `@frappe.whitelist` endpoints; stale entries removed (`ask_v2`, `text_to_speech`, `workflow_sales_invoice`, `setup_ai_settings`).
- RELEASE_NOTES.md restructured into Keep a Changelog format; legacy multi-provider section trimmed.
- CONTRIBUTING.md updated to mention the two CI jobs (Frappe-backed + db-free) and the CI seed step.
- ROADMAP.md replaced with phase-based document (this file).

### Removed

- `erp_ai/config/` — empty dead package.
- `DEAD_CODE_CLEANUP.md` — dev-process log.
- `erp_ai/www/` — empty directory.
- Root `tests/` — empty directory.
- `bug_report.md`, `feature_request.md` — replaced with GitHub issue templates.
- `patches.txt` — stale scratch file.
- `DOCUMENTATION.md` — stale 190KB dump; replaced with proper docs (README, ARCHITECTURE, UPGRADE, ROADMAP, SKILLS).

---

## [0.1.0] - 2025-09-23

### Added

- Initial release of ERP AI: local AI assistant for ERPNext.
- LLM integration with Ollama, Anthropic, and Google providers.
- Chat interface: widget, full-page, form button, workspace.
- Guided conversation flows (draft→confirm for Sales Invoices, Purchase Receipts, Stock Issues).
- MCP permission-checked document tools.
- Knowledge base with sources and citations.
- Per-user memory and behavior tracking.
- Role-aware answers respecting ERPNext permissions.
- Print URL generation and audit/rollback for AI actions.
- Idempotency via nonces and preview hashes.
- Voice input via Whisper STT (local).
- Barcode lookup, OCR for attachments, help center, evaluation.

### Changed

- Initial project structure and configuration.
