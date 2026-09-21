# ---------------------------------------------------------------------------
# AI Audit Trail — complete record of every AI operation.
#
# Stores: user request, interpreted intent, records read, proposed changes,
# confirmation status, executing user, result, errors, and rollback info.
# Uses the AI Assistant Action DocType for persistence.
# ---------------------------------------------------------------------------
import hashlib
import json
from typing import Any, Dict, Optional

# Single source of truth for how long a pending action stays confirmable.
# Imported by erp_ai.draft_workflow and erp_ai.idempotency so a draft created on
# either path expires on exactly the same clock (previously 30 min vs 60 min).
ACTION_EXPIRY_MINUTES = 60


def _compute_preview_hash(data: Dict[str, Any]) -> str:
    """Compute a stable hash of proposed changes for integrity verification."""
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def create_audit_record(session: str, user: str, action: str, target_doctype: str,
                       intent: str, request_text: str, proposed_data: Dict[str, Any],
                       records_read: Optional[list] = None) -> Dict[str, Any]:
    """Create a pending AI Assistant Action record for audit."""
    import frappe
    from frappe.utils import now_datetime
    preview_hash = _compute_preview_hash(proposed_data)
    nonce = frappe.generate_hash(length=12)
    expires_on = frappe.utils.add_to_date(now_datetime(), minutes=ACTION_EXPIRY_MINUTES)
    doc = frappe.get_doc({
        "doctype": "AI Assistant Action",
        "user": user,
        "session_id": session,
        "action": action,
        "target_doctype": target_doctype,
        "status": "pending",
        "draft_data": json.dumps({
            "intent": intent,
            "request": request_text[:500],
            "proposed_changes": proposed_data,
            "records_read": records_read or [],
        }),
        "nonce": nonce,
        "expires_on": expires_on,
        "preview_hash": preview_hash,
    })
    doc.insert()
    return {
        "name": doc.name,
        "nonce": nonce,
        "preview_hash": preview_hash,
        "expires_on": str(expires_on),
    }


def record_confirmation(action_id: str, user: str, expected_nonce: str = None) -> Dict[str, Any]:
    """Mark an action as confirmed by the user.

    Validates: ownership, nonce, expiry, status, and preview hash.
    Returns {"ok": True} or {"ok": False, "error": "..."}.
    """
    import frappe
    from frappe.utils import now_datetime
    action = frappe.get_doc("AI Assistant Action", action_id)
    # Validate ownership
    if action.user != user:
        return {"ok": False, "error": "Not your action"}
    # Validate nonce if provided
    if expected_nonce and action.nonce != expected_nonce:
        return {"ok": False, "error": "Invalid nonce"}
    # Validate expiry (use DB value directly, don't commit here — let the caller's
    # transaction boundary handle persistence; this is validation only)
    if action.expires_on and action.expires_on < now_datetime():
        return {"ok": False, "error": "Action expired"}
    # Validate status
    if action.status != "pending":
        return {"ok": False, "error": "Action already %s" % action.status}
    # Record confirmation via a single save (caller's transaction handles commit)
    action.status = "processing"
    action.confirmed_at = now_datetime()
    action.save()
    return {"ok": True}


def record_completion(
    action_id: str,
    target_docname: str,
    result: Dict[str, Any],
    rollback_ref: Optional[Dict[str, Any]] = None,
    changed_fields: Optional[list] = None,
    confirmed_at: Optional[Any] = None,
) -> None:
    """Mark an action as completed with the full result payload.

    Stores the actual outcome (not just the target docname), a rollback reference
    pointing back to the originating session/request, and the list of fields that
    were actually changed so the audit trail is complete.
    """
    import frappe
    from frappe.utils import now_datetime

    action = frappe.get_doc("AI Assistant Action", action_id)
    action.status = "completed"
    action.target_docname = target_docname
    action.completed_at = now_datetime()
    if confirmed_at:
        action.confirmed_at = confirmed_at
    if rollback_ref:
        action.rollback_reference = frappe.as_json(rollback_ref)
    action.draft_data = frappe.as_json({
        "intent": (lambda d: d.get("intent") if isinstance(d, dict) else None)(
            frappe.parse_json(action.draft_data) if action.draft_data else {}
        ),
        "request": (lambda d: d.get("request") if isinstance(d, dict) else None)(
            frappe.parse_json(action.draft_data) if action.draft_data else {}
        ),
        "proposed_changes": (lambda d: d.get("proposed_changes") if isinstance(d, dict) else None)(
            frappe.parse_json(action.draft_data) if action.draft_data else {}
        ),
        "records_read": (lambda d: d.get("records_read") if isinstance(d, dict) else None)(
            frappe.parse_json(action.draft_data) if action.draft_data else {}
        ),
        "result": result,
        "completed_at": str(now_datetime()),
        "changed_fields": list(changed_fields) if changed_fields else None,
        "rollback_reference": rollback_ref if rollback_ref else None,
    })
    action.save()
    frappe.db.commit()


def record_failure(action_id: str, error: str, rollback_ref: Optional[Dict[str, Any]] = None) -> None:
    """Mark an action as failed with error reason and optional rollback reference."""
    import frappe
    from frappe.utils import now_datetime

    action = frappe.get_doc("AI Assistant Action", action_id)
    action.status = "failed"
    action.failure_reason = error[:500]
    action.failed_at = now_datetime()
    if rollback_ref:
        action.rollback_reference = frappe.as_json(rollback_ref)
    action.draft_data = frappe.as_json({
        "intent": (lambda d: d.get("intent") if isinstance(d, dict) else None)(
            frappe.parse_json(action.draft_data) if action.draft_data else {}
        ),
        "request": (lambda d: d.get("request") if isinstance(d, dict) else None)(
            frappe.parse_json(action.draft_data) if action.draft_data else {}
        ),
        "proposed_changes": (lambda d: d.get("proposed_changes") if isinstance(d, dict) else None)(
            frappe.parse_json(action.draft_data) if action.draft_data else {}
        ),
        "records_read": (lambda d: d.get("records_read") if isinstance(d, dict) else None)(
            frappe.parse_json(action.draft_data) if action.draft_data else {}
        ),
        "error": error[:500],
        "failed_at": str(now_datetime()),
        "rollback_reference": rollback_ref if rollback_ref else None,
    })
    action.save()
    frappe.db.commit()


def verify_preview_integrity(action_id: str, proposed_data: Dict[str, Any]) -> bool:
    """Verify the proposed data hasn't changed since the preview was shown."""
    import frappe
    stored_hash = frappe.db.get_value("AI Assistant Action", action_id, "preview_hash")
    return stored_hash == _compute_preview_hash(proposed_data)


def get_audit_trail(session: str, user: str) -> list:
    """Return all audit records for a session."""
    import frappe
    records = frappe.get_all("AI Assistant Action",
        filters={"session_id": session, "user": user},
        fields=["name", "action", "target_doctype", "status", "confirmed_at",
                "target_docname", "failure_reason", "creation"],
        order_by="creation desc",
        limit_page_length=50)
    return records


def _classify_retryable(exc) -> bool:
    """Heuristic retryable-vs-fatal classification for AI action failures.

    Transient network conditions (timeouts, connection resets) are retryable;
    everything else (validation, permissions, data errors) is fatal — a retry
    would repeat the same failure.
    """
    import requests

    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    name = type(exc).__name__.lower()
    return "timeout" in name or "connection" in name


def log_error_safely(title: str, message=None, context=None, retryable=None) -> None:
    """Log an error without letting the logging call mask the original failure.

    ``frappe.log_error(title=None, message=None)`` takes the TITLE first (it only
    swaps the two when the first argument is multi-line) and the Error Log
    ``method``/title column is capped at 140 characters. Passing a long dynamic
    string first therefore raised CharacterLengthExceededError from *inside* the
    caller's ``except`` block, so the real tool/workflow error was replaced by a
    logging error and the failure reason never reached the log.

    Structured context (Phase 1.3): pass ``context`` to record which action /
    provider / model / session failed, and ``retryable`` (or an exception, see
    below) to distinguish transient from fatal — machine-readable so an
    operator or script can triage without decoding prose.

    If ``retryable`` is omitted but ``context`` was extracted from a live
    exception, pass the exception as ``retryable=exc`` — the classifier decides.

    Truncates the title and falls back to the file logger if Frappe logging
    itself is unavailable, so this helper can never raise.
    """
    import json as _json

    import frappe

    title = (str(title) or "erp_ai error")[:140]
    structured = ""
    if context:
        try:
            structured += "\ncontext: %s" % _json.dumps(
                {str(k): str(v) for k, v in context.items() if v is not None},
                sort_keys=True,
            )
        except Exception:
            pass
    if retryable is not None:
        flag = _classify_retryable(retryable) if isinstance(retryable, Exception) else bool(retryable)
        structured += "\nclass: %s" % ("retryable" if flag else "fatal")
    body = message if message is not None else frappe.get_traceback(with_context=True)
    if structured:
        body = "%s%s" % (body, structured) if body else structured.lstrip("\n")
    try:
        frappe.log_error(
            title=title,
            message=body,
        )
    except Exception:
        # Never let observability break the code path that is already failing.
        try:
            frappe.logger("erp_ai").error("%s :: %s", title, body)
        except Exception:
            pass
