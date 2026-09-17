# ---------------------------------------------------------------------------
# Scheduled maintenance for ERP AI.
#
# Registered in hooks.scheduler_events. Every function here is idempotent and
# bounded (batched) so a backlog cannot turn a scheduler tick into a long
# transaction. Lifecycle transitions go through the document API rather than
# raw SQL so they stay auditable and pass the transition guard in
# AIAssistantAction.validate.
# ---------------------------------------------------------------------------
import frappe

ACTION_DOCTYPE = "AI Assistant Action"
BATCH_SIZE = 500


def expire_stale_actions(batch_size: int = BATCH_SIZE) -> dict:
    """Hourly: expire unconfirmed drafts and reclaim abandoned claims.

    Two stale states exist and both must be closed out, because a stale action
    holds an idempotency key and therefore blocks the caller's retry:

    - ``pending`` past ``expires_on``: the user never confirmed it → ``expired``.
    - ``processing`` past ``expires_on``: the worker holding the claim died
      mid-request (killed, crashed, timed out) → ``failed``, so retries work.

    Returns counts for the scheduler log.
    """
    now = frappe.utils.now_datetime()
    counts = {"expired": 0, "reclaimed": 0}

    stale_pending = frappe.db.get_all(
        ACTION_DOCTYPE,
        filters={"status": "pending", "expires_on": ["<", now]},
        pluck="name",
        order_by="modified asc",
        limit_page_length=batch_size,
    )
    for name in stale_pending:
        if _close_action(name, "expired", "Expired before confirmation"):
            counts["expired"] += 1

    stale_processing = frappe.db.get_all(
        ACTION_DOCTYPE,
        filters={"status": "processing", "expires_on": ["<", now]},
        pluck="name",
        order_by="modified asc",
        limit_page_length=batch_size,
    )
    for name in stale_processing:
        if _close_action(name, "failed", "Abandoned mid-execution (stale claim)"):
            counts["reclaimed"] += 1

    frappe.db.commit()
    if counts["expired"] or counts["reclaimed"]:
        frappe.logger("erp_ai").info(
            "erp_ai: expire_stale_actions expired=%s reclaimed=%s"
            % (counts["expired"], counts["reclaimed"])
        )
    return counts


def _close_action(name: str, status: str, reason: str) -> bool:
    """Move one action into a terminal state; returns False if it was skipped.

    Per-row isolation: one unreadable row must not abort the batch, and losing a
    race against the user's own confirm/cancel is not an error.
    """
    try:
        action = frappe.get_doc(ACTION_DOCTYPE, name)
        if action.status not in ("pending", "processing"):
            return False
        action.status = status
        if status == "failed" and not action.failure_reason:
            action.failure_reason = reason
        action.save(ignore_permissions=True)
        return True
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "erp_ai.tasks: could not close %s as %s" % (name, status),
        )
        return False


def cleanup_expired_actions(days: int = 30, batch_size: int = BATCH_SIZE) -> dict:
    """Daily: delete closed actions older than ``days``.

    Only terminal, already-audited rows are removed (completed/failed/expired/
    cancelled). Completed actions are kept by default because their
    ``rollback_reference`` is the audit pointer back to the created document —
    raise ``days`` rather than expect instant deletion.
    """
    cutoff = frappe.utils.add_days(frappe.utils.now_datetime(), -abs(days))
    stale = frappe.db.get_all(
        ACTION_DOCTYPE,
        filters={
            "status": ["in", ["failed", "expired", "cancelled"]],
            "modified": ["<", cutoff],
        },
        pluck="name",
        order_by="modified asc",
        limit_page_length=batch_size,
    )
    for name in stale:
        try:
            frappe.delete_doc(ACTION_DOCTYPE, name, ignore_permissions=True, force=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                "erp_ai.tasks: could not delete action %s" % name,
            )
    frappe.db.commit()
    return {"deleted": len(stale)}