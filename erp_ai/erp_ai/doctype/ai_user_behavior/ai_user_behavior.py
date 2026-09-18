# See license.txt for the full text of the MIT License.

"""AI User Behavior — the assistant's event log of real user interactions.

Every assistant turn is recorded here: the prompt, the intent the assistant
took, and the outcome. Read back through ``get_org_patterns`` /
``prompt_block``, this log is the app's learning layer: org-level habits and
the failures new users would repeat are folded into the assistant's context,
so the guidance survives staff turnover — the experienced user leaves, the
patterns stay.
"""

import time

import frappe
from frappe.model.document import Document

from erp_ai.audit import log_error_safely

PROMPT_MAX = 1000
REASON_MAX = 500
CACHE_TTL_SECONDS = 300
PATTERN_DOCTYPE = "AI Behavior Pattern"
PATTERN_MAX_AGE_HOURS = 26

_cache = {"at": 0.0, "value": None}


class AIUserBehavior(Document):
    """Controller: no field logic — the value of this doctype is the log itself."""


def record(prompt=None, session_id=None, intent=None, target_doctype=None,
           outcome=None, failure_reason=None, correction_count=0):
    """Append one behavior event. Telemetry: must never raise.

    The user always comes from the session, never from the arguments. The row
    is inserted with ``ignore_permissions`` because the doctype grants no
    create permission by design — it is a system log, and the request path
    must not fail (or hit a permission wall) over an analytics row.
    """
    try:
        user = frappe.session.user
    except Exception:
        return
    if not (prompt or intent):
        return
    try:
        frappe.get_doc({
            "doctype": "AI User Behavior",
            "user": user,
            "session_id": session_id,
            "prompt": (prompt or "")[:PROMPT_MAX],
            "intent": intent,
            "target_doctype": target_doctype,
            "outcome": outcome,
            "failure_reason": (failure_reason or "")[:REASON_MAX] or None,
            "correction_count": int(correction_count or 0),
        }).insert(ignore_permissions=True)
    except Exception:
        log_error_safely("erp_ai.behavior.record", "behavior row insert failed")


def _group(fields, group_by, order_by, extra_filters=None):
    try:
        return frappe.get_all(
            "AI User Behavior", fields=fields, filters=extra_filters or {},
            group_by=group_by, order_by=order_by, limit_page_length=10) or []
    except Exception:
        return []


def get_org_patterns():
    """Aggregate the behavior log into org-level learning patterns.

    Returns a dict of small lists:
    - ``top_intents``: [intent, n] — what the org actually does day to day
    - ``failure_intents``: [intent, n] — where attempts usually fail
    - ``corrected``: [intent, corrections] — where users override the answer
    - ``recent_failures``: raw prompt examples — SYSTEM MANAGER only, because
      prompts can quote business data; the aggregate counts above are safe to
      fold into any user's context.
    """
    out = {
        "top_intents": _group(
            ["intent", "count(name) as n"], "intent", "n desc"),
        "failure_intents": _group(
            ["intent", "count(name) as n"], "intent", "n desc",
            {"outcome": "failed"}),
        "corrected": _group(
            ["intent", "sum(correction_count) as corrections"], "intent",
            "corrections desc"),
    }
    try:
        is_manager = "System Manager" in frappe.get_roles()
    except Exception:
        is_manager = False
    if is_manager:
        try:
            out["recent_failures"] = frappe.get_all(
                "AI User Behavior", filters={"outcome": "failed"},
                fields=["intent", "prompt", "failure_reason"],
                order_by="creation desc", limit_page_length=5) or []
        except Exception:
            out["recent_failures"] = []
    return out


def _live_block():
    """Render the prompt block from a live aggregate of the event log."""
    p = get_org_patterns()
    lines = []
    top = [f"{r['intent']} ({r['n']})" for r in p["top_intents"][:5] if r.get("intent")]
    if top:
        lines.append("Most used assistant tasks: " + ", ".join(top))
    fails = [f"{r['intent']} ({r['n']})"
             for r in p["failure_intents"][:3] if r.get("intent")]
    if fails:
        lines.append("Tasks that commonly fail here: " + ", ".join(fails)
                     + " — pre-empt the usual mistake and explain the correct path.")
    corr = [f"{r['intent']} ({r['corrections']})" for r in p["corrected"][:3]
            if r.get("intent") and r.get("corrections")]
    if corr:
        lines.append("Tasks where users often override the first answer: "
                     + ", ".join(corr) + " — clarify before acting.")
    return "\n".join(f"- {line}" for line in lines)


def _pattern_block():
    """Render the block from the nightly AI Behavior Pattern table.

    Returns None when the table is empty or older than PATTERN_MAX_AGE_HOURS
    — the caller then falls back to a live aggregate.
    """
    rows = frappe.get_all(
        PATTERN_DOCTYPE,
        fields=["intent", "use_count", "fail_count", "correction_count", "modified"],
        order_by="modified desc", limit_page_length=10) or []
    if not rows:
        return None
    try:
        newest = frappe.utils.get_datetime(rows[0]["modified"])
        age = (frappe.utils.now_datetime() - newest).total_seconds()
        if age > PATTERN_MAX_AGE_HOURS * 3600:
            return None
    except Exception:
        return None

    def _pick(field, limit, minimum=1):
        ranked = sorted(rows, key=lambda r: int(r.get(field) or 0), reverse=True)[:limit]
        return [f"{r['intent']} ({int(r.get(field) or 0)})" for r in ranked
                if r.get("intent") and int(r.get(field) or 0) >= minimum]

    lines = []
    top = _pick("use_count", 5, 1)
    if top:
        lines.append("Most used assistant tasks: " + ", ".join(top))
    fails = _pick("fail_count", 3, 1)
    if fails:
        lines.append("Tasks that commonly fail here: " + ", ".join(fails)
                     + " — pre-empt the usual mistake and explain the correct path.")
    corr = _pick("correction_count", 3, 1)
    if corr:
        lines.append("Tasks where users often override the first answer: "
                     + ", ".join(corr) + " — clarify before acting.")
    return "\n".join(f"- {line}" for line in lines)


def prompt_block():
    """Compact aggregate-only org context for the system prompt, cached.

    Counts only — raw failure prompts stay manager-visible (see
    ``get_org_patterns``), so this block is safe to fold into ANY user's
    prompt. Empty string when there is nothing to say yet.

    Reads the nightly AI Behavior Pattern table when it is fresh so the chat
    path stays cheap however big the event log grows; falls back to a live
    aggregate otherwise.

    ponytail: per-worker TTL cache on purpose (stdlib, no Redis coupling) —
    a few minutes of staleness is fine for prompt context; upgrade to
    ``frappe.cache`` only if cross-worker freshness ever matters.
    """
    if _cache["value"] is not None and time.monotonic() - _cache["at"] < CACHE_TTL_SECONDS:
        return _cache["value"]
    try:
        block = _pattern_block() or _live_block() or ""
    except Exception:
        block = ""
    _cache["at"] = time.monotonic()
    _cache["value"] = block
    return block


def reset_patterns_cache():
    """Drop the cached prompt block; the nightly refresh calls this."""
    _cache["at"] = 0.0
    _cache["value"] = None


def on_update(doc, method):
    """Best-effort realtime nudge that the log changed; never blocks a save."""
    try:
        frappe.publish_realtime(
            "erp_ai:behavior_changed",
            {"doctype": "AI User Behavior", "name": doc.name},
            after_commit=True,
        )
    except Exception:
        log_error_safely("erp_ai.behavior.on_update", "publish_realtime failed")


def apply_feedback(session_id=None, helpful=None):
    """Thumb up/down on the last assistant turn of this session. Never raises.

    Thumbs-up needs no write: the turn was already recorded ``success``.
    Thumbs-down marks the last turn ``corrected`` and increments its
    correction count — the "users often override this answer" signal.
    """
    try:
        user = frappe.session.user
    except Exception:
        return {"updated": 0}
    if not session_id or helpful in (1, "1", True, "true", "True"):
        return {"updated": 0}
    try:
        rows = frappe.get_all(
            "AI User Behavior",
            filters={"user": user, "session_id": session_id},
            fields=["name"], order_by="creation desc", limit_page_length=1) or []
        if not rows:
            return {"updated": 0}
        # ponytail: last-turn heuristic — users rate right after a reply, so
        # the newest row of the session is the rated turn; firing two quick
        # questions and then rating the first is rare. Upgrade path: replies
        # carry their behavior-row id once the widget tracks it.
        doc = frappe.get_doc("AI User Behavior", rows[0]["name"])
        doc.correction_count = int(doc.correction_count or 0) + 1
        doc.outcome = "corrected"
        doc.save(ignore_permissions=True)
        return {"updated": 1}
    except Exception:
        log_error_safely("erp_ai.behavior.feedback", "feedback apply failed")
        return {"updated": 0}
