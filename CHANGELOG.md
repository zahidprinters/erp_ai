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
