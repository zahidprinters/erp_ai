# ERP AI — In-progress work tracker

Updated: 2026-09-21 (resume)

## Done today (commit pending)

- [x] Phase 1.1: Ollama timeout ceiling + retry wrapper + health() reachability (commit d95b4da, CI green)
- [x] Phase 1.1.1: CI fix — ensure erp_ai in apps.txt before bench install-app (commit b85db0b, CI green)
- [x] Auto-confirm pending drafts on clear affirmative reply (`erp_ai.conversation` + new `erp_ai.affirm` module)
- [x] Whitelist `erp_ai.api.ask` and `erp_ai.api.ask_v2` (ask_v2 also gains audio_base64 transcription support)
- [x] DB-free tests for affirmative/negative detectors (11 tests in test_core.py + 2 security tests)
- [x] Frappe-backed tests for auto-confirm flow (5 tests in test_frappe_integration.py)
- [x] Update ROADMAP.md (Phase 1.1 → Done, Phase 1 → In progress with accurate status)
- [x] Update CHANGELOG.md [Unreleased] → Added
- [x] Update skills/local-llm-runtime.md (completed 1.1 + new auto-confirm section)

## Still to do

### Phase 1 — Production-relevant robustness (in progress)

- [ ] 1.2 Knowledge base: real freshness + verifiable citations
- [ ] 1.3 Error observability — structured logging for AI actions
- [ ] Phase 1 remaining items from prior notes: etcd timing out in install path, empty recipe_name fallback to "Recipe", MySQL support plan, etc.

### Phase 2 — Voice & latency robustness (not started)
- [ ] Re-prompt on STT timeout
- [ ] Configurable STT backend per site
- [ ] Initial speech detection
- [ ] Voice runtime resilience improvements

### Phase 3 — Flow-level e2e tests in CI (not started)
- [ ] End-to-end flow tests for the guided draft→confirm→submit cycle
- [ ] CI job that exercises the full voice→transcribe→draft→confirm path

### Phase 4 — Scale / multi-model / multi-user (deferred)
- [ ] Deferred until Phase 1 is complete

### Phase 5 — Maintainer quality-of-life (not started)
- [ ] 5.1: Maintain graphify output as a committed artifact
- [ ] 5.2: Remove doc drift (already mostly done in Phase 0)
