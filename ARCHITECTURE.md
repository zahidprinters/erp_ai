# Architecture

**Last updated:** 2026-09-21

This document is a plain-language map of ERP AI. It is written for humans
and for agents that need a one-shot overview before diving into a subsystem.
For the *planned* improvements, see [ROADMAP.md](../ROADMAP.md). For the
*capabilities* and how to use them, see [README.md](../README.md).

## How to read this document

The architecture is described in layers, from the outside in:

1. **User-facing surfaces** — where the assistant is reachable.
2. **The API layer** — the `@frappe.whitelist` endpoints and the god nodes.
3. **The runtime layers** — LLM, voice, audit, knowledge, drafts.
4. **Data & permissions** — DocTypes, RBAC, row-level scoping.
5. **Non-functional** — testing, CI, observability.

## Source of truth

This architecture is based on a graphify audit of the repository
(2553 nodes, 3638 edges, 290 communities; built from commit `57853d47`).
The god nodes and community structure below are extracted from that audit,
not invented.

---

## 1. User-facing surfaces

The assistant is reachable in several forms, all backed by the same API layer:

- **Widget** — small assistant widget on desk pages; voice-capable (mic → STT).
- **Full-page chat** — dedicated assistant page (`ai_assistant` page).
- **Form button** — assistant button on DocType forms.
- **Workspace** — `ai_assistant_hub` workspace for workspace-style interaction.
- **Voice** — mic input via Whisper STT (local); TTS via Piper for spoken replies.

All surfaces call into `erp_ai.api` (the API layer). The surfaces are thin;
the logic lives in the API layer and the runtime layers below.

---

## 2. The API layer (the loaded core)

The API layer is `erp_ai.api`. It holds the most connected functions in the
codebase (the god nodes from the graphify audit):

| God node | Edges | What it does |
|---|---|---|
| God node | Edges | What it does |
|---|---|---|
| `FrappeMCP` | 53 | MCP permission-checking document tool layer. |
| `confirm_draft()` | 35 | Confirms a pending AI Assistant Action; validates ownership / nonce / expiry. |
| `create_draft()` | 32 | Persists a pending operation to the AI Assistant Action DocType. |
| `_fetch()` | 32 | Data-fetch helper used widely across dataanswer paths. |
| `TestQueryPermissionScoping` | 29 | Row-level permission scoping under ERPNext (a god node per the fresh audit). |
| `log_error_safely()` | 27 | Error logging used broadly across the app. |
| `ask_llm()` | 21 | Central LLM entry point; routes to Ollama / Anthropic / Google. |
| `validate_field()` | 21 | Field-level validation for proposed edits. |
| `_SkipIfNoDB` | 19 | Test helper that skips DB-backed tests when there is no site (god node in the fresh audit). |

The API layer is the right place to look first when something feels wrong
with the assistant's behavior — most of the logic lives here.

### Whitelisted endpoints

The app exposes 35+ `@frappe.whitelist` endpoints. They are grouped in
README.md's "API reference" table. The main groups are:

- **Chat / answers** — ask, chat, guided answer, data answers.
- **Voice** — `voice_to_text` (STT), voice-aware chat entry.
- **MCP tools** — permission-checked document tools, tool execution.
- **Workflow handlers** — confirm / cancel workflows, shipment, stock issue.
- **Help & knowledge** — help center, knowledge base, sources, citations.
- **Feedback / permissions / audit** — feedback, my_permissions, action audit.
- **Infrastructure** — health, settings helpers.

The full list is maintained in README.md — not here — so it stays in sync
with the code.

---

## 3. Runtime layers

### 3.1 LLM integration

`erp_ai.llm` is the provider layer. It supports Ollama (local), Anthropic
(cloud), and Google (cloud), and routes based on the AI Settings config.

Key points:

- `ask_llm()` is the spine; every LLM call goes through it.
- Provider selection and model are set in the AI Settings DocType.
- Robustness gaps exist today: no per-request timeout, no retry policy for
  read-only calls, `health()` is incomplete. See ROADMAP Phase 1.1.

See [skills/local-llm-runtime.md](../skills/local-llm-runtime.md) for the
detailed runtime skill.

### 3.2 Voice

Voice is a cascaded pipeline: Whisper STT → LLM → Piper TTS.

- **STT** — Whisper (local); path/model configured in AI Settings.
- **LLM** — same `ask_llm()` path as chat.
- **TTS** — Piper (local) for spoken replies.

The voice path lives in `erp_ai.api` (the Voice Chat API community, 36 nodes).
Voice robustness gaps: no stage timeout budget, STT model speed. See
ROADMAP Phase 2.1.

### 3.3 Audit and draft persistence

The assistant's action flow is built around the **AI Assistant Action**
DocType. The flow:

1. `create_draft()` persists a pending operation.
2. A preview hash (`generate_preview_hash()`) stabilizes the proposed action.
3. The user confirms via `confirm_draft()` (validates ownership / nonce /
expiry).
4. The action is marked confirmed and executed.

This is the draft→confirm flow that the guided conversation surfaces
(Sales Invoice, Purchase Receipt, Stock Issue).

**Idempotency** is built in via nonces + expiry + preview hash. The remaining
hardening (truly idempotent re-confirm, immutable audit row, admin listing)
is ROADMAP Phase 4.2.

### 3.4 Knowledge and citations

`erp_ai.knowledge` (the Knowledge Sources community, 48 nodes) provides:

- Knowledge Source DocType (sources + tags).
- Citation helper `get_citation_for_doctype()`.
- Source lookup by ID / tag / doctype.

Today `check_freshness()` is not fully real (no TTL / stale flag / re-index
trigger). That's ROADMAP Phase 1.2. Citations are returned by the assistant
but should be made fully verifiable — see Phase 1.2.

### 3.5 Guided conversation

`erp_ai.guided` (Guided Conversation community, 45 nodes) implements the
step-by-step assistant flows. Key functions: `guided_answer()`,
`apply_answer()`, `_ask_next()`, `next_missing()`, `clear_guided()`.

This is a user-visible module that the e2e tests (ROADMAP Phase 3.1) should
cover.

### 3.6 Tool execution engine

`erp_ai.tools` (Tool Execution Engine community, 17 nodes) parses and
executes tool calls from LLM replies. Key functions: `_parse_tool_call()`,
`call_erp_tool()`, `execute_erp_tool()`, `_fallback_to_llm()`.

Tools are permission-checked (MCP layer) and audit-logged (AI Action Audit).

---

## 4. Data & permissions

### 4.1 DocTypes

ERP AI's runtime data lives in these DocTypes:

- **AI Assistant Action** — pending / confirmed actions (the audit table).
- **AI User Behavior** — per-user behavior tracking.
- **Knowledge Source** — sources + citations.
- **AI Settings** — app configuration (provider, model, voice, etc.).
- **AI Behavior Pattern** — behavior pattern DocType.

### 4.2 RBAC and row-level scoping

ERP AI extends ERPNext's permission system:

- **Row-level security** — `get_department_restrictions()` returns warehouse /
  company restrictions for a user. The `TestQueryPermissionScoping` test
  (a god node, 29 edges) covers this.
- **Permission checks** — `check_my_permission()`, `my_permissions()`,
  `_extract_fields_for()`.
- **Operator tools** — restricted user flows (operator tool authorization).

The RBAC Seed Data community (40 nodes) covers the seed data for these tests.

### 4.3 Audit trail

AI actions are audited through the AI Assistant Action DocType and the
AI Action Audit community (49 nodes, cohesion 0.05 — weak, a future
refactor candidate). Key functions: `create_audit_record()`,
`_compute_preview_hash()`, verify-pending / confirm / fail paths.

---

## 5. Non-functional

### 5.1 Testing

ERP AI has two test tiers:

1. **Database-free tests** (`erp_ai/tests/test_core.py`,
   `test_security.py`, `test_rbac.py`, `test_knowledge.py`,
   `test_infra.py`) — run in the `lint-and-unit` CI job. These test logic
   without a Frappe site.
2. **Frappe-backed tests** — run in the `frappe-tests` CI job against a
   fresh site with MariaDB + Redis, seeded via `erp_ai.tests.ci_seed`.

### 5.2 CI

The CI is in `.github/workflows/ci.yml`. It has two jobs:

- `lint-and-unit` — syntax + db-free tests.
- `frappe-tests` — full bench setup, site creation, seeding, and app tests.

The CI was hardened through several fixes (correct ERPNext version tag,
`--skip-assets`, bench-path fixes, seed-as-module, pytest in bench venv).
See [ROADMAP.md](../ROADMAP.md) Phase 3.2 for ongoing hygiene.

### 5.3 Observability

- **Logging** — `log_error_safely()` is the central error logger (27 edges).
  It logs file + stripped stack, and now supports structured fields (action_id
  / provider / model / session / tool / user) via the `context` kwarg, plus
  `retryable` classification (timeout/connection → retryable, else fatal).
  See ROADMAP Phase 1.3 (done).
- **Health** — `erp_ai.api.health()` reports configured LLM provider plus voice
  runtime reachability; see ROADMAP Phase 1.1 (done).

---

## 6. Weak spots and future refactor candidates

From the graphify audit:

- **AI Action Audit** (community `audit.py`, 32 nodes, cohesion 0.05) —
  weakly interconnected; a future refactor candidate.
- **Knowledge Sources** (community `KnowledgeSource`, 16 nodes, cohesion 0.12) —
  fresh audit shows higher cohesion after Phase 1.2 (verifiable citations +
  freshness). Refactor later if warranted.
- **Inferred edges** — `FrappeMCP` has 8 inferred (model-reasoned) edges that
  need manual verification (Phase 1.3-adjacent cleanup).

---

## 7. External references

- [graphify audit output](graphify-out/GRAPH_REPORT.md) — the raw audit (2553 nodes, 3638 edges, 290 communities; built from commit `57853d47`).
- [skills/local-llm-runtime.md](../skills/local-llm-runtime.md) — LLM runtime skill.
- [ROADMAP.md](../ROADMAP.md) — planned improvements.
- [README.md](../README.md) — capabilities and usage.
- [UPGRADE.md](../UPGRADE.md) — upgrade guide.
- [ERP AI GitHub repository](https://github.com/zahidprinters/erp_ai) — source, issues, CI.

---

*This document is maintained by hand and updated when the architecture
changes. It is a fact document, not a plan — it should always match the
code.*