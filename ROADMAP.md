# ERP AI — Development Phases & Improvement Roadmap

**Last updated:** 2026-09-19  
**Status:** Phase 0 complete. Phases 1–5 planned, not started.

This document is the single source of truth for *what comes next* in ERP AI. It is phase-based so work can be tracked, prioritized, and reviewed one phase at a time.

> **Note:** This file is actively maintained. If a section feels stale, open an issue — the roadmap is only useful if it's honest.

---

## Table of Contents

1. [How to read this roadmap](#how-to-read-this-roadmap)
2. [Phase 0 — Foundation (DONE)](#phase-0--foundation-done)
3. [Phase 1 — Production-relevant robustness](#phase-1--production-relevant-robustness)
4. [Phase 2 — Voice & latency robustness](#phase-2--voice--latency-robustness)
5. [Phase 3 — Flow-level e2e tests in CI](#phase-3--flow-level-e2e-tests-in-ci)
6. [Phase 4 — Scale / multi-model / multi-user](#phase-4--scale--multi-model--multi-user)
7. [Phase 5 — Maintainer quality-of-life](#phase-5--maintainer-quality-of-life)
8. [Status legend](#status-legend)
9. [Current status](#current-status)
10. [How to propose a change to this roadmap](#how-to-propose-a-change-to-this-roadmap)

---

## How to read this roadmap

Phases are numbered in the order they should be tackled, **not** in order of excitement. A phase is "ready" when its prerequisites are met and its acceptance criteria are clear. Each phase lists:

| Field | Meaning |
|---|---|
| **Goal** | The one-sentence outcome |
| **Why now** | Why this phase is placed here rather than later |
| **Scope** | Concrete deliverables |
| **Prerequisites** | What must exist first |
| **Acceptance criteria** | How you know the phase is done |
| **Effort** | Rough size: small / medium / large |
| **Risk** | What could go wrong |

Top-level tiers (from the development-audit roadmap):

- **Tier 1 — Immediately production-relevant** (robustness, correctness, credibility)
- **Tier 2 — Robustness & operability** (before scaling to more users)
- **Tier 3 — Scale / multi-user / multi-model** (next phase)
- **Tier 4 — Maintainer quality-of-life** (free-hour work)

---

## Phase 0 — Foundation (DONE)

> *Make the project's own documentation trustworthy before promising more.*

| Field | Value |
|---|---|
| **Goal** | All canonical docs exist and are internally consistent with the real codebase. |
| **Why now** | Code review revealed doc drift: dead `erp_ai/config/`, stale ROADMAP.md references, empty VERSIONS.md, stale DOCUMENTATION.md, roadmap fragments that no longer matched reality. A roadmap is only useful if readers trust it. |
| **Scope** | 1. Refresh ROADMAP.md to this file (phase-based, no dead references). 2. Replace empty VERSIONS.md with a proper CHANGELOG.md (Keep a Changelog). 3. Add UPGRADE.md for site admins. 4. Add ARCHITECTURE.md summarizing the god nodes and the 90 communities from the graphify audit. 5. Add a `skills/` directory with skill.md files. 6. Remove stale scratch files (bug_report.md / feature_request.md / patches.txt / DOCUMENTATION.md). |
| **Prerequisites** | Nothing — this phase *is* the prerequisite for the rest. |
| **Acceptance criteria** | - `ROADMAP.md` is this file. <br>- `CHANGELOG.md` exists and follows Keep a Changelog; the `[Unreleased]` section matches the most recent commits. <br>- `UPGRADE.md` describes what migrations/seeding/settings change on upgrade. <br>- `ARCHITECTURE.md` is written in plain language and references the real god nodes. <br>- `skills/` exists with at least the SKILLS.md index + the first skill file (`skills/local-llm-runtime.md`). <br>- `ruff check` clean. <br>- Graphify audit files committed to `docs/` as a maintained artifact. |
| **Effort** | Medium |
| **Risk** | Low — doc work only; no runtime behavior changes. |
| **Status** | ✅ **Done** |

### What was delivered in Phase 0

1. **ROADMAP.md** — replaced with this phase-based document.
2. **CHANGELOG.md** — created in Keep a Changelog format; `[Unreleased]` section captures the recent work (AI provider fix, db-free tests, CI seed, draft-confirm bug fixes, voice STT fix, cleanup).
3. **UPGRADE.md** — created for site admins with migration/seeding/settings guidance.
4. **ARCHITECTURE.md** — created summarizing the god nodes and the 90 communities from the graphify audit.
5. **skills/** — created with SKILLS.md index + first skill file (`skills/local-llm-runtime.md`).
6. **Doc cleanup** — removed `DEAD_CODE_CLEANUP.md`, `bug_report.md`, `feature_request.md` (replaced with proper GitHub issue templates), `patches.txt`, and the stale `DOCUMENTATION.md`.

---

## Phase 1 — Production-relevant robustness

> *Make the assistant fail well before it scales.*

### 1.1 Ollama request timeouts, retry, and healthy-report

| Field | Value |
|---|---|
| **Goal** | Every Ollama-backed call has a timeout, a retry policy for read-only calls, and the runtime reports healthy/unhealthy in `erp_ai.api.health()`. |
| **Why now** | `ask_llm()` is a god node (20 edges) and is the spine of chat, voice, and MCP tool calls. A slow or down local Ollama box currently stalls or fails without a clear, recoverable path. This is the single highest-leverage robustness change. |
| **Scope** | - Enforce a per-request timeout (settings field `ollama_timeout` + hard ceiling, e.g. 90s for interactive chat). <br>- Read-only calls retry once with backoff on transient errors. <br>- `health()` reports provider + model loaded + voice runtime available + (if enabled) knowledge-source freshness. <br>- Audit notes when a retry happens. |
| **Prerequisites** | Phase 0 (docs) complete so the behavior is described and readable. |
| **Acceptance criteria** | - A call to an unreachable Ollama endpoint returns a clear, user-facing degradation message, not a traceback. <br>- `health()` returns a structured summary that an admin can read. <br>- Retry is read-only only and is documented in README / UPGRADE. |
| **Effort** | Medium |
| **Risk** | Medium — touches the LLM spine; test well. |
| **Status** | ✅ **Done** — timeout ceiling (`OLLAMA_TIMEOUT_CEILING = 30s`), retry wrapper (`_ask_ollama_with_retry` on ConnectionError/HTTPError, max 2 retries), and `health()` reachability (delegates to `_llm_runtime_available`) all landed; documented in `skills/local-llm-runtime.md`. |

### 1.2 Knowledge base: real freshness + verifiable citations

| Field | Value |
|---|---|
| **Goal** | Knowledge sources are world-readable as "fresh" or "stale", citations returned by the assistant include enough metadata to verify them, and there is one test that a cited source actually exists. |
| **Why now** | The `Knowledge Sources` community (48 nodes, cohesion 0.06) is one of the two weakest in the graphify audit. External safe-agentic research stresses verifiable sources; an assistant that cites nothing or cites wrong sources loses credibility fast. |
| **Scope** | - `check_freshness()` becomes real: TTL / stale flag + re-index trigger. <br>- Citations include at least doctype + source id + short excerpt. <br>- One integration test: query that returns a cited source → verify source exists and matches. |
| **Prerequisites** | 1.1 not strictly required, but do it first so the assistant's "I don't know" path is also robust. |
| **Acceptance criteria** | - A stale source is flagged and re-indexable. <br>- A citation is verifiable from the returned metadata. <br>- The test passes locally and in CI. |
| **Effort** | Small–Medium |
| **Risk** | Low |
| **Status** | ✅ **Done** — `citation_dict()` verifiable metadata, `check_freshness()` TTL + `reindex_required` trigger, stale flag in citations, 7 new tests |

### 1.3 Error observability — structured logging for AI actions

| Field | Value |
|---|---|
| **Goal** | `log_error_safely()` (19 edges) records enough context to diagnose a failure: action_id / draft_id / provider / model / outcome, with a machine-readable retryable-vs-fatal flag. |
| **Why now** | Right now the log is file + stripped stack. That's enough to see *that* something broke; it's not enough to see *which action, on which provider, for which user intent*. This matters for ops and for CI failure-context annotations. |
| **Scope** | - Structured fields in the log entry when available. <br>- A flag or code distinguishing retryable transient from fatal. <br>- Keep the stripped stack (don't lose it). |
| **Prerequisites** | 1.1 (Ollama healthy/report) so the provider context is available to log. |
| **Acceptance criteria** | - A failure in chat/voice/MCP logs an entry with provider + model + action context when available. <br>- No regression in existing callers (God-node, widely used — test carefully). |
| **Effort** | Medium |
| **Risk** | Medium — widely used function; coordinate with 1.1. |
| **Status** | ✅ **Done** — `context` + `retryable` kwargs (exception auto-classified via `_classify_retryable`), wired into `confirm_draft`, MCP `call_tool`/`create_document`, and `ask_llm` failure paths; 4 new tests |

---

## Phase 2 — Voice & latency robustness

> *Make the voice round-trip feel like a tool, not a gamble.*

### 2.1 Voice timeout budget across STT → LLM → TTS

| Field | Value |
|---|---|
| **Goal** | Each voice stage (STT, LLM, TTS) has a hard timeout so a stuck stage can't hang the round trip, and a stuck voice runtime is reported cleanly. |
| **Why now** | Voice is a real user-facing path (widget → mic → STT → LLM → TTS). The external research on cascaded Whisper→LLM→TTS assistants stresses per-stage timeouts as the basic safety net. `erp_ai.api` is the God-node module for voice (Community 5, 36 nodes) — keep the change centralized. |
| **Scope** | - Timeout budget across STT→LLM→TTS. <br>- "Voice unavailable" surfaced cleanly, not as a traceback. <br>- Prefer `faster-whisper` + INT8 quant if still on base Whisper (concrete speedup). <br>- Piper voice selection matched to server CPU. |
| **Prerequisites** | 1.1 (LLM timeout) so the LLM stage in the voice path shares the same timeout discipline. |
| **Acceptance criteria** | - A voice round-trip completes or fails within a bounded time with a clear message. <br>- The README voice section reflects the actual stack and any quant/speedup notes. |
| **Effort** | Medium |
| **Risk** | Medium — keep it in `erp_ai.api` and test on both CPU and where a GPU is available. |
| **Status** | ✅ **Done** — `STAGE_BUDGET` (ffmpeg 30s / STT 120s / TTS 30s), `voice_runtime_available()` clean missing-components report, TTS failure surfaced as `voice_error` without failing the turn, `ask_v2` base64-decode bug fixed |

### 2.2 Pre-commit + formatting consistency

| Field | Value |
|---|---|
| **Goal** | `.pre-commit-config.yaml` actually enforces ruff + ruff-format + trailing-whitespace + check-yaml (including CI yml) + commit-msg, wired into a pre-push hook. |
| **Why now** | `.pre-commit-config.yaml` exists (8 entries) but isn't obviously enforced. CI catches formatting issues, but pre-commit catches them before they become commits — cheaper and more local. |
| **Scope** | - Update hooks. <br>- Add pre-push enforcement. <br>- Run once to lint-clean any existing drift. |
| **Prerequisites** | Phase 0 (so the CI yml and docs being linted are final for now). |
| **Acceptance criteria** | - `pre-commit run --all-files` passes. <br>- README / UPGRADE / ROADMAP all lint-clean. |
| **Effort** | Small |
| **Risk** | Low |
| **Status** | 🔲 **Not started** |

---

## Phase 3 — Flow-level e2e tests in CI

> *Prove the user-visible contract, not just the unit contract.*

### 3.1 Guided conversation + draft-confirm e2e tests

| Field | Value |
|---|---|
| **Goal** | CI runs at least two flow-level end-to-end tests on a fresh site: (a) a guided-conversation interaction that exercises next-step / missing-fields, and (b) create_draft → confirm_draft → verify action recorded + document created. |
| **Why now** | Graphify shows `Guided Conversation` (45 nodes) and `Draft Persistence` (19 nodes) as real, user-visible modules. The CI fixes so far proved *the app boots and runs*, but didn't prove the actual assistant flow works end to end. This is the highest-value test addition. |
| **Scope** | - One guided e2e test. <br>- One draft confirm e2e test (idempotent re-confirm is a no-op / re-confirm, not a duplicate). <br>- Both run in the `frappe-tests` CI job on a fresh seeded site. |
| **Prerequisites** | Phase 1 (Ollama robustness) so the tests don't depend on a flaky LLM for the core assert; at minimum the flow should be testable with deterministic data-answer paths. |
| **Acceptance criteria** | - The two tests pass locally on a fresh seeded site and in CI. <br>- README "Testing" section reflects the e2e tests. |
| **Effort** | Medium |
| **Risk** | Medium — e2e tests depend on site state; seed carefully (Phase 0 UPGRADE/seed discipline helps). |
| **Status** | 🔲 **Not started** |

### 3.2 Pre-commit Config and workflow hygiene

| Field | Value |
|---|---|
| **Goal** | The pre-commit config is complete and the CI failure-context step reliably surfaces the right logs. |
| **Why now** | The CI failure annotations were built during the CI-fix work; now that the app is more robust, confirm they still point at the right thing and that `.pre-commit-config.yaml` covers yaml + commit-msg. |
| **Scope** | - Review `.github/workflows/ci.yml` failure-context step. <br>- Confirm `.pre-commit-config.yaml` covers `.github/workflows/*.yml`. |
| **Prerequisites** | 2.2 (pre-commit). |
| **Acceptance criteria** | - A CI failure on a workflow yml would be caught by pre-commit locally before push. <br>- CI failure-context annotations point at the relevant log. |
| **Effort** | Small |
| **Risk** | Low |
| **Status** | 🔲 **Not started** |

---

## Phase 4 — Scale / multi-model / multi-user

> *Next phase — only after 1–3 are stable.*

### 4.1 Multi-model routing with capability tags + fallback

| Field | Value |
|---|---|
| **Goal** | The assistant can route between a small/fast model for data lookups and a larger model for drafting, with a documented fallback when the primary is unavailable. |
| **Why now** | The current `AISettings` holds `default_model` + `ollama_url`. The Collabnix Ollama production pattern (model routing + metrics + caching) maps directly onto what a production assistant wants. This is Tier-3 by design — don't add routing complexity before the single-model path is robust (Phase 1). |
| **Scope** | - Capability tags per model (fast-data, drafting, voice). <br>- Routing by intent. <br>- Fallback with a clear user-facing note. |
| **Prerequisites** | Phase 1 (single-model robustness), Phase 2 (voice latency), Phase 3 (flow tests). |
| **Acceptance criteria** | - Routing is documented in README + UPGRADE. <br>- Fallback degrades gracefully. |
| **Effort** | Large |
| **Risk** | High — touches ask_llm(), the God-node. Keep it as a separate PR. |
| **Status** | 🔲 **Not started** (deferred) |

### 4.2 Idempotency + draft nonce hardening (finish the last 20%)

| Field | Value |
|---|---|
| **Goal** | Re-confirming the same valid nonce is a no-op / re-confirm (not a duplicate document), and the audit record is immutable + queryable by admin with model version + raw input + nonce + outcome. |
| **Why now** | The draft-confirm flow already uses nonces + expiry + preview hash — this is the final hardening the safe-agentic pattern calls for. Tier 3 because it depends on the flow tests proving the current behavior first. |
| **Scope** | - Idempotent confirm. <br>- Immutable audit row with the full context. <br>- Admin view/action listing pending drafts older than N minutes. |
| **Prerequisites** | Phase 3 (e2e draft-confirm test) so the idempotency behavior is tested. |
| **Acceptance criteria** | - Duplicate confirm attempts don't create duplicate documents. <br>- An admin can list / inspect pending and completed actions. |
| **Effort** | Medium |
| **Risk** | Medium — audit schema changes need migration + seed consideration (Phase 0 UPGRADE). |
| **Status** | 🔲 **Not started** (deferred) |

### 4.3 Row-level / operator scoping resilience tests

| Field | Value |
|---|---|
| **Goal** | Add failure-injection tests for the scoped query path: LLM unreachable, knowledge source missing/stale, repeated confirm attempts. |
| **Why now** | `TestQueryPermissionScoping` is a top god node (29 edges) and already runs many sub-scenarios. The next step is targeted failure injection, not more happy-path tests. Tier 3 because it's a hardening of an already-strong module. |
| **Scope** | - Ollama unreachable → graceful degradation. <br>- Stale/missing source → clear "I don't know" rather than hallucination. <br>- Repeated confirms → no duplicates. |
| **Prerequisites** | Phase 1 (robust failure paths) + Phase 3 (e2e flow tests). |
| **Acceptance criteria** | - The failure-injection tests pass in CI. <br>- README "Testing" + "Troubleshooting" reflect the degraded states. |
| **Effort** | Medium |
| **Risk** | Medium |
| **Status** | 🔲 **Not started** (deferred) |

---

## Phase 5 — Maintainer quality-of-life

> *Free-hour work — do whenever you have one.*

### 5.1 One maintained internal knowledge graph

| Field | Value |
|---|---|
| **Goal** | The graphify output for this repo is a maintained artifact, regenerated on push to `develop`, and summarized in `ARCHITECTURE.md`. |
| **Why now** | You just ran graphify and got a real 1319-node / 90-community map. That's valuable and easy to lose. |
| **Scope** | - Commit `graphify-out/graph.html` + `graph.json` to `docs/`. <br>- Add CI step or Makefile target to regenerate. <br>- `ARCHITECTURE.md` summarizes the god nodes + communities in plain language. |
| **Prerequisites** | Phase 0. |
| **Acceptance criteria** | - `docs/graph.html` opens and shows the current repo. <br>- `ARCHITECTURE.md` is readable and matches the graph. |
| **Effort** | Small |
| **Risk** | Low |
| **Status** | 🔲 **Not started** |

### 5.2 Remove doc drift

| Field | Value |
|---|---|
| **Goal** | No stale scratch files, no dumped "documentation" that nobody maintains. |
| **Why now** | Graphify flagged `bug_report.md`, `feature_request.md`, `patches.txt` as producing no nodes. `DOCUMENTATION.md` is a 190KB raw dump. Either fold into a real docs tree or delete. |
| **Scope** | - Remove or replace the flagged files. <br>- If keeping anything, give it a real home and owner. |
| **Prerequisites** | Phase 0. |
| **Acceptance criteria** | - `git status` clean. <br>- No orphaned doc files without an owner. |
| **Effort** | Small |
| **Risk** | Low |
| **Status** | 🔲 **Not started** |

---

## Status legend

| Status | Meaning |
|---|---|
| **Not started** | Phase not begun. |
| **In progress** | Active work, PR open or local branch. |
| **Done** | Merged to `develop`, CI green, docs updated. |
| **Deferred** | Intentionally pushed later (usually because a prerequisite isn't ready). |

---

## Current status (as of this writing)

- **Phase 0** — Done. This file + CHANGELOG.md + UPGRADE.md + ARCHITECTURE.md + SKILLS.md + doc cleanup landed together.
- **Phase 1** — Done. 1.1 (Ollama timeout/retry/health) done; auto-confirm-on-affirmative + `ask`/`ask_v2` whitelist landed; 1.2 (verifiable citations + real freshness with reindex trigger) done; 1.3 (structured error logging with retryable/fatal classification) done.
- **Phase 2** — Not started.
- **Phase 3** — Not started.
- **Phase 4** — Deferred.
- **Phase 5** — Not started.

---

## How to propose a change to this roadmap

1. Open an issue or PR against `develop`.
2. If you're adding a phase, mirror the phase template above (Goal / Why now / Scope / Prerequisites / Acceptance criteria / Effort / Risk / Status).
3. If you're reordering phases, explain the dependency you're changing — phases are ordered by dependency, not excitement.
4. Keep the "Current status" table honest. If a phase is done, mark it done and update CHANGELOG.md's `[Unreleased]` section.

<!-- phasetoc -->
