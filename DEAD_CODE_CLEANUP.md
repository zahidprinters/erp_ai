ERP_AI DEAD-CODE / STALE-IMPORT CLEANUP
================================================================

Objective
----------------------------------------------------------------
Remove dead imports and dead detection call paths from the
production code path, and document the guards left in place
for modules that were deleted on disk.

What was dead
----------------------------------------------------------------
1) detect_intent()
   - Imported in api.py but not called anywhere in the production
     chat / ask / ask_v2 / ask_with_doc / ask_v2_with_voice /
     _process_with_mcp flows.
   - No non-test call sites were found by AST-level scan.
   - Removed the unused import from erp_ai/api.py.

2) detect_report / _handle_report()
   - No non-test call sites were found in the current codebase.
   - Treat as dead for the current production path.

3) Deleted modules
   - erp_ai/diagnostics
   - erp_ai/duplication
   - erp_ai/nlq
   - erp_ai/reports
   These were removed from disk and are no longer available.

Guards left in place
----------------------------------------------------------------
1) api.py:health()
   - Wraps the erp_ai.diagnostics import in try/except ImportError.
   - When diagnostics is missing, returns a safe dict instead of
     raising:
       {"status": "ok", "note": "diagnostics module not available"}

2) handlers/__init__.py
   - handle_create_item
   - handle_create_customer
   - handle_create_supplier
   Each wraps the erp_ai.duplication import in
   try/except ImportError and sets check_duplicate = None.
   Duplicate checks are skipped when the module is missing.

Files changed
----------------------------------------------------------------
- erp_ai/api.py
    * Removed dead import of detect_intent.
    * Guarded diagnostics import in health().
- erp_ai/handlers/__init__.py
    * Guarded duplication import in the three create handlers.

Verification
----------------------------------------------------------------
- Compile check passed for api.py and handlers/__init__.py.
- AST scan found no non-test call sites for detect_intent(),
  detect_report(), or _handle_report().
- Unresolved erp_ai imports (guarded):
    - erp_ai/api.py                          -> erp_ai.diagnostics
    - erp_ai/handlers/__init__.py            -> erp_ai.duplication
- Both are intentionally guarded with try/except ImportError so the app degrades gracefully when those modules are missing.

Notes
----------------------------------------------------------------
- The erp_ai.intents module itself still exists on disk; this
  cleanup only removes the unused import in api.py.
- If detect_intent or detect_report are ever re-enabled, restore
  the import and the call site in the relevant flow.
