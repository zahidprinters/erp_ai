# UPGRADE

This document is for site administrators upgrading ERP AI between versions.
It covers what migrations run, what seeding happens, and what settings
must be checked after an upgrade.

## Before you upgrade

1. **Back up your site.**
   ```bash
   bench backup --site <site>
   ```
2. **Note your AI Settings.** If you have custom Ollama URLs, Anthropic keys,
   or Google provider config, note them before upgrading — they live in the
   `AI Settings` DocType and survive app upgrades.
3. **Pin the version you are upgrading *from* and *to*.** ERP AI follows
   [Semantic Versioning](https://semver.org/). Breaking changes will be
   called out in [CHANGELOG.md](../CHANGELOG.md) under `## [X.Y.Z]`.

## Upgrading the app

```bash
cd frappe-bench
bench --site <site> install-app erp_ai   # or: bench get-app erp_ai <url>
bench --site <site> migrate
```

- `bench migrate` runs `erp_ai.install.before_migrate` / `after_migrate` and
  any DocType migrations (new fields, new DocTypes, renamed fields).
- `bench build` may be needed if assets changed (JS/CSS). Run it when the
  release notes say "assets changed" — otherwise skip it.

## After upgrading

1. **Check the AI Settings DocType.** Open `AI Settings` on your site and
   confirm the provider, model, and voice settings still look right.
2. **Look at the logs.** If the assistant behaves differently, check
   `sites/<site>/logs/` for `erp_ai`-related entries. The assistant
   logs errors through `log_error_safely()` — see README.md "Troubleshooting".
3. **Test a basic flow.** Open the AI Assistant widget on a desk page and
   ask a simple data question (e.g., "show me the last 5 sales invoices").
   If it answers, the LLM routing and permissions layer is up.
4. **Re-index knowledge sources if you use them.** If your release added
   knowledge source changes, re-create or re-index sources via the
   Knowledge Source DocType. See README.md "Knowledge Base".

## Seeding and default data

ERP AI seeds minimal runtime data on install via `erp_ai.install.after_install`:

- **AI Assistant Action** DocType (the audit/pending-action table).
- **AI User Behavior** DocType (per-user behavior tracking).
- **Knowledge Source** DocType (sources + citations).
- **Default settings** are written into `AI Settings`.

On upgrade, `before_migrate` / `after_migrate` run. If a new release adds
required seed data, UPGRADE.md will say so explicitly in the `[X.Y.Z]` section.

## Voice runtime

If you use voice input (Whisper STT), the voice path depends on external
binaries/path config. After an upgrade:

- Confirm `whisper_path` / `whisper_model` in AI Settings still point to a
  working runtime.
- If you changed the voice model or path, test with the widget mic button
  before rolling out to users.

See README.md "Voice" and "Troubleshooting" for concrete checks.

## Breaking changes

Breaking changes are called out in [CHANGELOG.md](../CHANGELOG.md) under the
relevant version. If a release has no `### Breaking` entry, assume the upgrade
is non-breaking (migration-only).

## Rolling back

If an upgrade breaks your site:

1. Restore the backup taken in "Before you upgrade".
   ```bash
   bench restore --site <site> --backup-file ~/sites/<site>/private/backups/<backup>.sql
   ```
2. Re-install the previous app version if needed.

## Questions

- [README.md](../README.md) — capabilities, API, troubleshooting.
- [CONTRIBUTING.md](../CONTRIBUTING.md) — development setup, testing, CI.
- [SECURITY.md](../SECURITY.md) — how to report security issues.
- [ROADMAP.md](../ROADMAP.md) — what is coming next.
