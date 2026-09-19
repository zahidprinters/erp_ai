# Skills index

This directory holds **skill.md** files — small, focused documents that
describe a specific capability, integration, or operational concern of ERP AI,
in a form that is useful to both humans and LLMs working with the codebase.

## What a skill.md file is

A skill.md file is:

- **Scoped to one thing.** Example: "local LLM runtime with Ollama", or
  "voice STT with Whisper", or "draft confirmation idempotency".
- **Fact-first.** It describes what the code *actually does*, what it
  depends on, what can break, and how to test it — not aspirational plans.
- **Cross-referenced.** It links to the relevant code, README sections,
  ROADMAP phases, and CHANGELOG entries.

## Why skills exist

ERP AI is a medium-sized Frappe app with a lot of moving parts (LLM providers,
audit, drafts, workflows, knowledge, voice, RBAC). A single README cannot
hold all the operational detail. Skill files let a maintainer or agent pick
the one thing they need to reason about without loading the whole project.

## How to use these files

- **For humans:** skim `SKILLS.md` (this file) for the list, then read the
  one that matches the problem you are solving.
- **For agents / LLMs:** these files are structured so a tool can read one
  skill and have enough ground truth to work on that subsystem accurately.

## How to add a new skill

1. Pick a scoped topic that is bigger than a single function but smaller than
   the whole app. Good candidates: a runtime dependency (Ollama, Whisper,
   Piper), a cross-cutting concern (audit, idempotency, permissions), or a
   user-facing flow (draft confirmation, guided conversation).
2. Create `skills/<topic>.md` using `skills/local-llm-runtime.md` as a
   template.
3. Add a one-line entry to this file's table.
4. Keep it factual and current. If the code changes, update the skill.

## Skill files

| File | Topic |
|---|---|
| `local-llm-runtime.md` | Ollama / Anthropic / Google provider integration, timeouts, retry, health, and robustness guidance (Phase 1.1). |

> More skill files will be added as the roadmap progresses. If you need a
> skill for a topic that isn't listed, add it following the template.
