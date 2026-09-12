# ---------------------------------------------------------------------------
# Guided conversation: collect a document's fields one question at a time.
#
# The assistant turns "make a purchase invoice" into a short natural chat:
#   AI:  Which supplier is this from?
#   You: ABC Traders
#   AI:  Which items are included? ...
#   ...
#   AI:  That is everything I need. Reply yes and I will save it.
#
# State is kept per session+user in an AI Chat Message marker (same pattern
# the codebase already uses for drafts), so it survives across stateless
# HTTP calls and the user can answer one question at a time.
# ---------------------------------------------------------------------------
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import frappe

from erp_ai.draft_workflow import (
    create_draft,
    generate_preview,
    get_missing_fields,
    resolve_party,
)
from erp_ai.schema import DOCTYPE_SCHEMAS

_GUIDED_MARKER = "[GUIDED]|"
_GUIDED_CLEARED_MARKER = "[GUIDED_CLEARED]"

# Field questions and hints are defined in erp_ai.questions (single source).
# This module adds a few guided-flow overrides on top of that base catalogue.
from erp_ai.questions import get_hint, get_question

_DOCTYPE_QUESTIONS: Dict[str, Dict[str, str]] = {
    "Item": {
        "item_name": "What should the item be called?",
        "item_group": "Which item group? I can use Products if you do not care.",
    },
}

_NUMERIC_FIELDS = frozenset({
    "standard_rate", "opening_stock", "discount_percent",
    "paid_amount", "qty", "rate",
})


def _question_for(doctype: str, field: str) -> str:
    # Doctype-specific override takes precedence, then the shared questions catalogue.
    q = _DOCTYPE_QUESTIONS.get(doctype, {}).get(field) or get_question(doctype, field)
    if q:
        if field == "items":
            hint = get_hint("items")
            if hint:
                return "%s\nUse this pattern: %s" % (q, hint)
        return q
    label = DOCTYPE_SCHEMAS.get(doctype, {}).get("labels", {}).get(field, field)
    return "What should the %s be?" % label


def _keep(d: Dict[str, Any]) -> Dict[str, Any]:
    """Drop None / empty values from collected data."""
    return {k: v for k, v in d.items() if v not in (None, "")}


# ---------------------------------------------------------------------------
# State persistence (chat marker, like the existing draft markers)
# ---------------------------------------------------------------------------

def load_guided(session: str, user: str) -> Optional[Dict[str, Any]]:
    """Return the active guided conversation state for session+user, or None."""
    if not session:
        return None
    rows = frappe.db.get_all(
        "AI Chat Message",
        filters={
            "session_id": session,
            "user": user,
            "content": ["like", "%" + _GUIDED_MARKER + "%"],
        },
        fields=["content", "creation"],
        order_by="creation desc",
        limit=1,
    )
    if not rows:
        return None
    content = rows[0]["content"] or ""
    if not content.startswith(_GUIDED_MARKER):
        return None
    # A later clear marker wins over an older state marker.
    cleared = frappe.db.get_all(
        "AI Chat Message",
        filters={
            "session_id": session,
            "user": user,
            "content": _GUIDED_CLEARED_MARKER,
        },
        fields=["creation"],
        order_by="creation desc",
        limit=1,
    )
    if cleared:
        # Compare creation timestamps of the two most recent markers.
        state_created = rows[0].get("creation")
        clear_created = cleared[0].get("creation")
        if state_created and clear_created and clear_created > state_created:
            return None
    try:
        state = json.loads(content[len(_GUIDED_MARKER):])
    except (ValueError, TypeError):
        return None
    if not isinstance(state, dict) or state.get("status") in ("done", "cancelled"):
        return None
    return state


# ---------------------------------------------------------------------------
# Answer parsing helpers
# ---------------------------------------------------------------------------

def _to_number(raw: str, field: str) -> Optional[float]:
    text = raw.strip().replace(",", "").replace("rs", "").replace("pk", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


_ITEM_LINE_PATTERNS = [
    # name, quantity, price  /  name | quantity | price
    re.compile(r"^\s*([A-Za-z][A-Za-z0-9 .&/-]*?)\s*[,|/]\s*([\d.,]+)\s*[,|/]\s*([\d.,]+)\s*$"),
    # quantity x name @ price
    re.compile(r"^\s*([\d.,]+)\s*[xX*]\s*([A-Za-z][A-Za-z0-9 .&/-]*?)\s*(?:@\s*([\d.,]+))?\s*$"),
    # name @ price
    re.compile(r"^\s*([A-Za-z][A-Za-z0-9 .&/-]*?)\s*@\s*([\d.,]+)\s*$"),
]


def _parse_item_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line:
        return None
    for pat in _ITEM_LINE_PATTERNS:
        m = pat.match(line)
        if m:
            groups = m.groups()
            if pat is _ITEM_LINE_PATTERNS[0]:
                name, qty, rate = groups[0], groups[1], groups[2]
            elif pat is _ITEM_LINE_PATTERNS[1]:
                qty, name, rate = groups[0], groups[1], groups[2]
            else:
                name, rate = groups[0], groups[1]
                qty = None
            try:
                q = float(qty.replace(",", "")) if qty else 1.0
                r = float(rate.replace(",", "")) if rate else 0.0
            except (ValueError, AttributeError):
                return None
            return {
                "description": name.strip(),
                "item_code": name.strip(),
                "qty": q,
                "rate": r,
            }
    return None


def _parse_items_answer(raw: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Parse the user's item list into line items."""
    lines = [ln for ln in re.split(r"[;\n]", raw) if ln.strip()]
    items: List[Dict[str, Any]] = []
    bad: List[str] = []
    for ln in lines:
        item = _parse_item_line(ln)
        if item:
            items.append(item)
        else:
            bad.append(ln.strip())
    if bad:
        return items, (
            "I could not read this line: \"%s\".\n"
            "Use: name, quantity, price (e.g. pump spring, 2, 500)" % bad[0]
        )
    return items, None


def apply_answer(
    doctype: str,
    data: Dict[str, Any],
    field: str,
    raw: str,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Merge the user's answer into collected data. Returns (data, error)."""
    data = dict(data)
    raw = (raw or "").strip()

    if field == "items":
        items, err = _parse_items_answer(raw)
        if err:
            return data, err
        existing = [dict(i) for i in data.get("items", [])]
        existing.extend(items)
        data["items"] = existing
        return data, None

    if field in _NUMERIC_FIELDS:
        num = _to_number(raw, field)
        if num is None:
            hint = get_hint(field) or ""
            return data, "That did not look like a number to me. Please give me a number%s." % (
                (" (%s)" % hint) if hint else ""
            )
        data[field] = num
        return data, None

    if field in ("customer", "supplier"):
        party_dt = "Customer" if field == "customer" else "Supplier"
        candidates = resolve_party(raw, party_dt)
        if not candidates:
            data[field] = raw
            return data, (
                "I could not find a %s named \"%s\" in your account yet. "
                "Reply with the correct name, or say \"create %s\" and I will "
                "set up a new %s as well." % (party_dt.lower(), raw, raw, party_dt.lower())
            )
        if len(candidates) > 1:
            opts = []
            for i, c in enumerate(candidates, 1):
                label = c.get("customer_name") or c.get("supplier_name") or c.get("name", "?")
                opts.append("%d. %s" % (i, label))
            return data, "I found more than one %s. Which one did you mean?\n%s" % (
                party_dt.lower(), "\n".join(opts)
            )
        data[field] = candidates[0]["name"] if candidates[0].get("name") else raw
        return data, None

    # Plain text field.
    data[field] = raw
    return data, None


def save_guided(
    session: str,
    user: str,
    doctype: str,
    data: Dict[str, Any],
    pending_field: Optional[str] = None,
    status: str = "collecting",
    skipped: Optional[List[str]] = None,
) -> bool:
    if not session:
        return False
    state = {
        "doctype": doctype,
        "data": _keep(data),
        "pending_field": pending_field,
        "status": status,
        "skipped": list(skipped or []),
    }
    frappe.get_doc({
        "doctype": "AI Chat Message",
        "user": user,
        "session_id": session,
        "role": "user",
        "content": _GUIDED_MARKER + json.dumps(state, default=str),
         }).insert()
    # Transaction boundary moved to caller (ask_v2) — no direct commit here
    return True


def clear_guided(session: str, user: str) -> bool:
    if not session:
        return False
    frappe.get_doc({
        "doctype": "AI Chat Message",
        "user": user,
        "session_id": session,
        "role": "user",
        "content": _GUIDED_CLEARED_MARKER,
         }).insert()
    # Transaction boundary moved to caller (ask_v2) — no direct commit here
    return True


# ---------------------------------------------------------------------------
# The guided turn itself
# ---------------------------------------------------------------------------

def next_missing(doctype: str, data: Dict[str, Any]) -> List[str]:
    """Required fields still missing, in schema order."""
    return get_missing_fields(doctype, data)


# Optional but valuable follow-ups, asked after the required fields are done.
# The user can answer "skip" and the assistant moves on / finishes up.
OPTIONAL_FOLLOWUPS: Dict[str, List[str]] = {
    "Item": ["standard_rate", "opening_stock"],
    "Sales Invoice": ["due_date"],
    "Purchase Invoice": ["due_date"],
    "Customer": ["mobile_no"],
    "Supplier": ["mobile_no"],
}

_SKIP_WORDS = frozenset({"skip", "no", "na", "nahi", "none", "later", "baad mein", "-"})


def _pending_question(doctype, data, skipped):
    """Next question to ask: a required field first, then a useful optional.

    Returns (field, is_optional) or (None, False) when ready.
    """
    missing = next_missing(doctype, data)
    if missing:
        return missing[0], False
    for f in OPTIONAL_FOLLOWUPS.get(doctype, []):
        if f not in data and f not in skipped:
            return f, True
    return None, False


def _so_far(doctype: str, data: Dict[str, Any]) -> str:
    """Short, human recap of what we already have (or empty string)."""
    parts = []
    if doctype == "Item":
        if data.get("item_name"):
            parts.append("item %s" % data["item_name"])
        if data.get("standard_rate"):
            parts.append("price %s per unit" % data["standard_rate"])
    elif doctype in ("Sales Invoice", "Purchase Invoice"):
        who = data.get("customer" if doctype == "Sales Invoice" else "supplier")
        if who:
            parts.append("for %s" % who)
        items = data.get("items", [])
        if items:
            parts.append("%d item(s)" % len(items))
    elif doctype in ("Customer", "Supplier"):
        key = "customer_name" if doctype == "Customer" else "supplier_name"
        if data.get(key):
            parts.append(key.replace("_", " ") + " " + str(data[key]))
    if not parts:
        return ""
    return "So far: " + ", ".join(parts) + "."


def _ready_reply(session: str, user: str, doctype: str, data: Dict[str, Any]) -> str:
    """Create the pending action and reply ready for confirmation."""
    create_draft(
        session=session,
        action="create",
        target_doctype=doctype,
        draft_data=data,
        user=user,
    )
    preview = generate_preview(doctype, data)
    return (
        "%s\n\nThat is everything I need. Reply yes and I will create it, "
        "or tell me what to change." % preview
    )


def _ask_next(session, user, doctype, data, skipped):
    """Save state for the next question and return the reply text."""
    field, optional = _pending_question(doctype, data, skipped)
    if not field:
        save_guided(
            session, user, doctype, data,
            pending_field=None, status="ready", skipped=skipped,
        )
        return _ready_reply(session, user, doctype, data)
    save_guided(
        session, user, doctype, data,
        pending_field=field, status="collecting", skipped=skipped,
    )
    question = _question_for(doctype, field)
    if optional:
        question = "%s\n(You can also say skip.)" % question
    return "%s\n\n%s" % (_so_far(doctype, data), question)


def guided_start(session: str, user: str, doctype: str, data: Dict[str, Any]) -> str:
    """Start (or continue) guided collection when a create intent arrives."""
    data = _keep(data)
    return _ask_next(session, user, doctype, data, skipped=[])


def guided_ready_again(session: str, user: str) -> str:
    """Re-show the ready preview while the user decides (or empty string)."""
    state = load_guided(session, user)
    if not state:
        return ""
    return _ready_reply(session, user, state["doctype"], state.get("data") or {})


def guided_answer(session: str, user: str, prompt: str) -> str:
    """Answer received for the pending question of an active guided session."""
    state = load_guided(session, user)
    if not state:
        return ""
    doctype = state["doctype"]
    data = dict(state.get("data", {}))
    field = state.get("pending_field")
    skipped = list(state.get("skipped", []))

    if field and prompt.strip().lower() in _SKIP_WORDS:
        skipped = skipped + [field]
        return _ask_next(session, user, doctype, data, skipped)

    if field:
        data, err = apply_answer(doctype, data, field, prompt)
        if err:
            save_guided(
                session, user, doctype, data,
                pending_field=field, status="collecting", skipped=skipped,
            )
            return "%s\n\n%s" % (err, _question_for(doctype, field))

    return _ask_next(session, user, doctype, data, skipped)
