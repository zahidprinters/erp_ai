# Contributing to ERP AI

Thanks for your interest in improving ERP AI! This is a Frappe Framework v15 /
ERPNext v15 app, so contributions must keep the Frappe app conventions intact
and preserve the app's security posture. Please read this guide before opening a
pull request.

## Table of contents

- [How to get the code](#how-to-get-the-code)
- [Branch strategy](#branch-strategy)
- [Coding standards](#coding-standards)
- [Security and sensitive data](#security-and-sensitive-data)
- [Testing](#testing)
- [Pull requests](#pull-requests)
- [Release process](#release-process)

## How to get the code

```bash
# fork first, then clone your fork
git clone https://github.com/<your-username>/erp_ai.git
cd erp_ai
git remote add upstream https://github.com/zahidprinters/erp_ai.git
```

ERP AI is developed as a Frappe app on a bench. To run it locally:

```bash
cd /path/to/frappe-bench
bench get-app erp_ai /path/to/erp_ai
bench new-site spi_dev --install-app erpnext erp_ai
bench --site spi_dev run-tests --app erp_ai
```

## Branch strategy

- `develop` — default branch for ongoing work and PRs.
- `main` — release branch. Releases are cut from `develop` via a PR.
- Use short, descriptive branch names:
  - `feat/assistants-role-filter`
  - `fix/kb-source-freshness`
  - `docs/readme-restructure`

Prefix with `fix/`, `feat/`, `chore/`, `docs/`, `refactor/`, or `ci/`.

## Coding standards

- **Python 3.10+** (the bench runs Python 3.11).
- **Ruff** is the configured linter/formatter:

  ```bash
  ruff check erp_ai/
  ruff format erp_ai/        # format only — do NOT reformat generated DocType JSON
  ```

  Generated DocType `.json` files and compiled assets are intentionally
  left alone; do not reformat them.

- **Imports:** keep them tidy. Avoid new top-level `frappe` imports in modules
  that are imported at bench startup; import lazily inside functions where the
  cost matters.
- **Docstrings:** write them. One-line for trivial functions, multi-line for
  anything with branching or side effects.
- **Keep diffs small:** one logical change per PR.

## Security and sensitive data

This app enforces hard security boundaries. Contributions that weaken them will
not be merged. In particular:

- **Never** use `ignore_permissions=True` in the MCP tool layer.
- Only business DocTypes belong in the tool allowlist (`erp_ai/mcp/server.py`).
  Security/system DocTypes and HR/personnel DocTypes are denied by default.
- Keep the **draft → confirm** boundary: public endpoints must not create or
  submit financial/stock documents without explicit confirmation.
- **No secrets in git.** `.env`, `*_KEY`, `*_SECRET`, `site_config.json`, and
  bench site directories are in `.gitignore`. Double-check before committing.
- Temporary files from OCR/voice processing are deleted after use; do not
  introduce long-lived user-controlled file paths.

If a bug fix changes security behavior, call it out in the PR description and
add or update a test.

## Testing

- **Fast, database-free tests** (run anywhere, no Frappe site):

  ```bash
  python -m pytest erp_ai/tests/test_core.py \
    erp_ai/tests/test_security.py \
    erp_ai/tests/test_rbac.py \
    erp_ai/tests/test_knowledge.py \
    erp_ai/tests/test_infra.py -q -p no:cacheprovider
  ```

- **Frappe-backed tests** (need a real bench site):

  ```bash
  bench --site <site> run-tests --app erp_ai
  ```

Add a test that fails if the new logic breaks (assert-based is fine; no heavy
framework needed).

## Pull requests

1. Open a PR against `develop` (not `main`).
2. Fill in the template:
   - **What does this change and why?**
   - **How was it tested?** (paste test command output)
   - **Security impact?** (yes/no, and what was checked)
3. Keep CI green: `ruff check`, `ast.parse` syntax check, and the
   database-free test suite must pass (see `.github/workflows/ci.yml`).
4. Request review from a maintainer. Do not merge your own PRs without review.

## Release process

- Releases are cut from `develop` by a maintainer into `main`.
- Update `RELEASE_NOTES.md` with each meaningful change.
- Bump the version in `erp_ai/__init__.py` only at release time.

## Code of conduct

Be respectful and constructive. Harassment or personal attacks of any kind will
not be tolerated. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
