# ERP AI — versions & milestones

This file is a historical record of ERP AI releases and the major
capability milestones behind them. For day-to-day changes, see
[CHANGELOG.md](../CHANGELOG.md) (Keep a Changelog format).

## Current version

The current version is recorded in the app's `pyproject.toml` (`version`
field) and in the `AI Settings` DocType where relevant. The canonical
changelog is [CHANGELOG.md](../CHANGELOG.md).

## v0.1.0 — initial release (2025-09-23)

The first public release of ERP AI.

### Capabilities

- **Chat surfaces:** widget, full-page page, form button, workspace.
- **LLM providers:** Ollama (local), Anthropic (cloud), Google (cloud).
- **Guided conversation flows:** draft → confirm for Sales Invoice, Purchase
  Receipt, Stock Issue.
- **MCP permission-checked document tools** — tools the assistant can call
  with permission guards.
- **Knowledge base** — sources, tags, citations.
- **Per-user memory and behavior tracking** — AI User Behavior DocType.
- **Role-aware answers** — respects ERPNext permissions and row-level scoping.
- **Audit and rollback** — AI Assistant Action DocType with nonce / expiry /
  preview hash idempotency.
- **Print URL generation** — print URLs for created documents.
- **Voice input** — Whisper STT (local); TTS via Piper.
- **Barcode lookup, OCR for attachments, help center, evaluation.**

### Notes

- The initial release was built and tested primarily on a single full
  ERPNext site.
- CI was added alongside the release; see `.github/workflows/ci.yml`.
- The roadmap that follows this release lives in [ROADMAP.md](../ROADMAP.md).

## Post-release work (2026-09-19)

A round of robustness and correctness work was done after the initial
release. The changes are captured in [CHANGELOG.md](../CHANGELOG.md) under
`## [Unreleased]` and in the following commits:

- Whitelisted `voice_to_text`, `confirm_workflow_action`, `cancel_workflow_action`.
- Fixed `health()` to not call the deleted `erp_ai.diagnostics` module.
- Removed dead `erp_ai/config/`, `DEAD_CODE_CLEANUP.md`, empty dirs.
- Fixed fresh-site test failures exposed by the CI seed (`ci_seed`).
- Rewrote README.md to production grade.
- Added ROADMAP.md (phase-based), CHANGELOG.md, UPGRADE.md, ARCHITECTURE.md,
  and the `skills/` directory.

## Future milestones

Milestones are defined in [ROADMAP.md](../ROADMAP.md) by phase, not by
version, because the version number will follow Semantic Versioning and the
phases are about capability, not releases.

Roughly:

- **Phase 1** → makes the assistant robust on a single provider/site.
- **Phase 2** → makes voice latency sane and enforces formatting.
- **Phase 3** → proves the user-visible flows in CI.
- **Phase 4** → multi-model routing and idempotency hardening.
- **Phase 5** → maintainer quality-of-life.

Each phase, when done, will be recorded in CHANGELOG.md under a versioned
entry when it ships.
