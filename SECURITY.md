# SECURITY.md

Supported versions
==================

ERP AI is a Frappe app. Releases follow ERPNext / Frappe Framework v15
compatibility:

| Version | Frappe / ERPNext | Status |
| ------- | ---------------- | ------ |
| develop | v15              | Active development, supported on `develop` |
| main    | v15              | Current release track |

## Reporting a vulnerability

Please report security vulnerabilities responsibly. **Do not open a public
issue for suspected security problems.**

- **Email**: open an issue in this repository (marking it for the attention of
  a private/maintainer channel) or contact the maintainer through the GitHub
  repository owner.
- **What to include**:
  - A description of the issue and the potential impact.
  - Steps to reproduce, including the minimal prompt or API call.
  - The affected commit/branch/version (run `git rev-parse HEAD`).
- **What to expect**:
  - We will acknowledge your report within 3 business days.
  - We will investigate and, if confirmed, ship a fix on `develop` and
    back-port to `main` as a patch release.
  - We will credit the reporter in the release notes unless you ask to remain
    anonymous.

## Security model — what you should already know

- ERP AI does **not** store LLM API keys by default. Cloud-provider keys belong
  in the user's `AI Settings` DocType or in Frappe site config (`site_config.json`),
  never in code or in git.
- Document operations are routed through a permission-checked MCP tool layer
  (`erp_ai/mcp/server.py`), which enforces:
  - an explicit **allowlist** of business DocTypes,
  - rejection of all system/security DocTypes (User, Role, DocType, etc.),
  - HR/personnel DocTypes are denied by default,
  - `frappe.has_permission()` is always enforced — there is no
    `ignore_permissions=True` path in the MCP layer.
- Public workflow endpoints return a **draft preview** and never auto-create or
  auto-submit financial/stock documents without explicit user confirmation.

If a contribution changes any of the above, it must include a security review
note in the PR description and an updated/added test.

## Hardened defaults

- Voice input requires HTTPS (except `localhost`).
- Temporary files created for OCR/voice processing are deleted after use.
- The app uses timeouts around voice subprocesses so a slow/missing local voice
  runtime cannot hang a request indefinitely.
