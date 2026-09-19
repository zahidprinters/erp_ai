# ---------------------------------------------------------------------------
# ERP AI - Public API facade.
#
# Thin routing layer. All real logic lives in focused modules:
#   llm/ schema/ intents/ safety/ questions/ validators/
#   reports/ duplication/ handlers/ workflows/ voice/
#   conversation/ mcp/ knowledge/
# ---------------------------------------------------------------------------
import json
import os
import re
from typing import Any, Dict, List, Optional

import frappe
import requests
from frappe import _
from frappe.utils import fmt_money

from erp_ai.audit import log_error_safely
from erp_ai.conversation import (
    OPTIONAL_FOLLOWUPS,
    clear_guided,
    guided_answer,
    guided_ready_again,
    guided_start,
    load_guided,
)
from erp_ai.draft_workflow import (
    confirm_draft,
    create_document_from_draft,
    extract_invoice_fields,
    extract_item_fields,
    extract_party_fields,
    generate_preview,
    get_draft,
    get_missing_fields,
    get_missing_labels,
)
from erp_ai.erp_ai.doctype.ai_user_behavior.ai_user_behavior import (
    apply_feedback as _apply_feedback,
)
from erp_ai.erp_ai.doctype.ai_user_behavior.ai_user_behavior import (
    prompt_block as _org_prompt_block,
)
from erp_ai.erp_ai.doctype.ai_user_behavior.ai_user_behavior import (
    record as _record_behavior,
)
from erp_ai.handlers import (
    handle_count_query,
    handle_create_customer,
    handle_create_item,
    handle_create_supplier,
    handle_print,
)
from erp_ai.handlers.formatters import format_document_view
from erp_ai.knowledge.erpnext_kb import get_kb_summary, get_knowledge_excerpt
from erp_ai.llm import ask_llm, ask_ollama
from erp_ai.mcp.server import FrappeMCP
from erp_ai.safety import check_illegal_operation
from erp_ai.schema import DOCTYPE_SCHEMAS, get_all_doctypes, get_schema
from erp_ai.voice import text_to_speech, voice_to_text
from erp_ai.workflows.shipment import handle_shipment_nl
from erp_ai.workflows.stock_issue import handle_issue_nl


# ---------------------------------------------------------------------------
# Simple chat
# ---------------------------------------------------------------------------
@frappe.whitelist()
def chat(prompt, model=None):
    """Simple AI chat."""
    if not prompt:
        frappe.throw("prompt is required")
    return {"response": ask_llm(prompt, model=model)}


# ---------------------------------------------------------------------------
# Deterministic data answers
# ---------------------------------------------------------------------------
_DATA_WORDS = {
    "delivery note": "Delivery Note", "delivery notes": "Delivery Note",
    "purchase receipt": "Purchase Receipt", "purchase receipts": "Purchase Receipt",
    "material request": "Material Request", "material requests": "Material Request",
    "purchase invoice": "Purchase Invoice", "purchase invoices": "Purchase Invoice",
    "sales invoice": "Sales Invoice", "sales invoices": "Sales Invoice",
    "sales order": "Sales Order", "sales orders": "Sales Order",
    "purchase order": "Purchase Order", "purchase orders": "Purchase Order",
    "customer": "Customer", "customers": "Customer", "client": "Customer",
    "supplier": "Supplier", "suppliers": "Supplier", "vendor": "Supplier",
    "item": "Item", "items": "Item", "product": "Item", "products": "Item",
    "warehouse": "Warehouse", "warehouses": "Warehouse",
    "lead": "Lead", "leads": "Lead",
    "employee": "Employee", "employees": "Employee",
    "stock entry": "Stock Entry", "stock entries": "Stock Entry",
}
_COUNT_WORDS = re.compile(r"\b(how many|how much|number of|count of|total)", re.I)

_DATA_INTENTS = [
    {"name": "stock_total", "kind": "bin_sum",
     "re": re.compile(r"\b(total stock|total quantity|total inventory|overall stock)", re.I)},
    {"name": "item_count", "kind": "count",
     "re": re.compile(r"\b(how many items|number of items|total items|item count)", re.I),
     "dt": "Item", "filters": {"disabled": 0}, "label": "active items"},
    {"name": "so_open", "kind": "count",
     "re": re.compile(r"\b((open|pending) sales orders?)", re.I),
     "dt": "Sales Order", "filters": {"docstatus": 1}, "label": "open sales orders"},
    {"name": "si_unpaid", "kind": "si_unpaid",
     "re": re.compile(r"\b(unpaid|outstanding|overdue) invoices?", re.I)},
]


def _num(v):
    try:
        v = float(v)
        return f"{int(v):,}" if v == int(v) else f"{v:,.2f}"
    except Exception:
        return str(v)


def _plural(n, word):
    if n == 1 and word.endswith("s"):
        return word[:-1]
    return word


def _aggregate(dt, expr, filters=None):
    """Return one aggregate over `dt`, honouring the caller's read scope.

    ``frappe.db.count`` and raw SQL apply no permissions at all — neither the
    role check nor the ``permission_query_conditions``/User Permission filters
    (company, warehouse, item, cost centre, ...) take part in the query, so a
    restricted user gets totals for rows they may not read.

    Delegates to ``erp_ai.erp_tools._fetch`` — the one validated ``get_list``
    read path — instead of building its own ``frappe.get_list`` call, so the
    aggregate can never drift from the row-level read (audit point 11: one
    helper per concern). Returns None when the user may not read `dt` or the
    query fails.
    """
    from erp_ai.erp_tools import _fetch

    if not frappe.has_permission(dt, "read"):
        return None
    try:
        rows = _fetch(dt, filters=filters or {}, fields=[f"{expr} as total"],
                      limit_page_length=0)
    except Exception:
        return None
    return rows[0].get("total") if rows else None


def _count(dt, filters=None):
    """Permission-aware count. Returns None when the caller may not read `dt`
    or the filtered query fails (e.g. an invalid filter field) — it must never
    fall back to an unfiltered count, which would leak totals outside the
    caller's row-level scope."""
    total = _aggregate(dt, "count(name)", filters)
    return None if total is None else int(total)


def _run_intent(it):
    kind = it.get("kind", "count")
    try:
        if kind == "bin_sum":
            if not frappe.has_permission("Bin", "read"):
                return {"ok": False}
            n = _aggregate("Bin", "sum(actual_qty)") or 0
            return {"ok": True, "answer": f"Total stock: {_num(n)} units."}
        if kind == "si_unpaid":
            if not frappe.has_permission("Sales Invoice", "read"):
                return {"ok": False}
            unpaid = {"docstatus": 1, "outstanding_amount": [">", 0]}
            cnt = int(_aggregate("Sales Invoice", "count(name)", unpaid) or 0)
            amt = _aggregate("Sales Invoice", "sum(outstanding_amount)", unpaid) or 0
            try:
                cur = frappe.db.get_single_value("Global Defaults", "default_currency")
                money = fmt_money(amt, currency=cur)
            except Exception:
                money = _num(amt)
            return {"ok": True, "answer": f"{cnt:,} unpaid invoices, outstanding: {money}."}
        dt, label = it["dt"], it.get("label", it["dt"])
        n = _count(dt, it.get("filters"))
        if n is None:
            return {"ok": False}
        return {"ok": True, "answer": f"We have {n:,} {_plural(n, label)}."}
    except Exception:
        return {"ok": False}


def _data_answer(prompt):
    if not prompt:
        return {"ok": False}
    q = re.sub(r"[?.,;:!]", " ", prompt.lower())
    for it in _DATA_INTENTS:
        if it["re"].search(q):
            res = _run_intent(it)
            res["intent"] = it["name"]
            return res
    if _COUNT_WORDS.search(q):
        for phrase, dt in sorted(_DATA_WORDS.items(), key=lambda kv: -len(kv[0])):
            if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", q):
                n = _count(dt)
                if n is not None:
                    return {"ok": True, "answer": f"There are {n:,} {_plural(n, phrase)}.",
                            "intent": "count", "target_doctype": dt}
    return {"ok": False}


@frappe.whitelist()
def data_answer(prompt):
    """Deterministic ERP data answers."""
    return _data_answer(prompt)


# ---------------------------------------------------------------------------
# Document resolution
# ---------------------------------------------------------------------------
def _resolve(doctype, name):
    """Exact lookup first, then partial-tolerant title search."""
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        meta = frappe.get_meta(doctype)
        candidates = []
        tf = meta.get_title_field()
        if tf:
            candidates.append(tf)
        if meta.has_field("customer_name"):
            candidates.append("customer_name")
        for f in candidates:
            hits = frappe.get_list(doctype, filters={f: ["like", f"%{name}%"]}, limit_page_length=1, pluck="name")
            if hits:
                return frappe.get_doc(doctype, hits[0])
        raise


@frappe.whitelist()
def summarize_doc(doctype, name):
    """AI summary of any ERPNext document in 3 bullet points."""
    doc = _resolve(doctype, name)
    doc.check_permission("read")
    fields = {df.fieldname: getattr(doc, df.fieldname) for df in doc.meta.fields if getattr(doc, df.fieldname, None) not in (None, "")}
    data = json.dumps(fields, default=str)[:6000]
    prompt = f"You are an ERP assistant. Summarize this ERPNext {doctype} in 3 short bullet points:\n{data}"
    return {"summary": ask_llm(prompt)}


@frappe.whitelist()
def draft_email(purpose, recipient=None, doctype=None, name=None):
    """Draft a professional email, optionally grounded on an ERPNext document."""
    ctx = ""
    if doctype and name:
        doc = frappe.get_doc(doctype, name)
        doc.check_permission("read")
        ctx = json.dumps({df.fieldname: getattr(doc, df.fieldname) for df in doc.meta.fields if getattr(doc, df.fieldname, None) not in (None, "")}, default=str)[:4000]
    prompt = f"Draft a professional business email. Purpose: {purpose}. Recipient: {recipient or 'Customer'}. Context: {ctx}. Include a Subject line. Keep it under 150 words."
    return {"email": ask_llm(prompt)}


# ---------------------------------------------------------------------------
# Desk assistant with memory
# ---------------------------------------------------------------------------
def _assistant_reply(prompt, session=None, model=None):
    """Shared core of the chat endpoints: deterministic data answers first,
    then the configured LLM with session memory. Returns (reply, session).

    Restores the pipeline that was gutted when the inline chat-dispatch
    handlers (_handle_create_intent and friends) were removed in favour of
    the draft -> confirm endpoints: the create/submit flows now live in
    their own whitelisted endpoints and the guided conversation, so the chat
    surface answers questions and points users at those flows.
    """
    session = session or frappe.generate_hash(length=10)
    user = frappe.session.user
    apps = ", ".join(frappe.get_installed_apps())
    roles = ", ".join(frappe.get_roles())
    fullname = frappe.utils.get_fullname(user)
    system = (
        f"You are the built-in AI assistant of SPI's ERPNext system, running on Frappe Framework 15. "
        f"Installed apps: {apps}. The current user is {fullname} ({user}), roles: {roles}. "
        f"Adapt your answer: give administrators technical detail; give operators short, simple guidance."
    )
    history = frappe.get_all("AI Chat Message", filters={"session_id": session, "user": user},
                             fields=["role", "content"], order_by="creation asc", limit_page_length=8)
    mem = "\n".join(f"{m.role}: {m.content}" for m in history)
    org_block = _org_prompt_block()
    if org_block:
        system += f"\n\nOrg usage patterns (behavior-log aggregates):\n{org_block}"
    full_prompt = f"{system}\n\nConversation history:\n{mem}\n\nUser: {prompt}\nAssistant:"
    data = _data_answer(prompt)
    if data.get("ok"):
        _record_behavior(prompt=prompt, session_id=session, intent=data.get("intent"),
                         target_doctype=data.get("target_doctype"), outcome="success")
        return data["answer"], session
    if data.get("intent"):
        # A data intent matched but declined (permission or query failure):
        # exactly the org signal worth learning — users asking for what they
        # cannot read, or reports that keep breaking.
        _record_behavior(prompt=prompt, session_id=session, intent=data.get("intent"),
                         target_doctype=data.get("target_doctype"), outcome="failed",
                         failure_reason="data intent declined")
    try:
        reply = ask_llm(full_prompt, model=model)
    except Exception as e:
        _record_behavior(prompt=prompt, session_id=session, intent="llm_chat",
                         outcome="failed", failure_reason=str(e))
        raise
    _record_behavior(prompt=prompt, session_id=session, intent="llm_chat",
                     outcome="success" if reply else "failed")
    return reply, session


@frappe.whitelist()
def ask(prompt, session=None, model=None):
    """Desk AI assistant with saved memory + Frappe-aware context."""
    if not prompt:
        frappe.throw("prompt is required")
    reply, _session = _assistant_reply(prompt, session, model)
    return reply


@frappe.whitelist()
def record_feedback(session=None, helpful=None):
    """Thumb up/down on the assistant's last reply of this session.

    Thumbs-up is a no-op by design (the turn was already recorded as a
    success); thumbs-down marks the last turn ``corrected`` and increments
    its correction count — the "users often override this answer" signal
    that the nightly pattern job turns into pre-emptive guidance.
    """
    return _apply_feedback(session or None, helpful)


def ask_v2(prompt, session=None, model=None):
    """Dict-returning chat variant ({response, session}) consumed by
    ``ask_v2_with_voice`` and the Desk widget."""
    if not prompt:
        frappe.throw("prompt is required")
    reply, session = _assistant_reply(prompt, session, model)
    return {"response": reply, "session": session}


@frappe.whitelist()
def ask_with_doc(doctype, name, prompt, session=None, model=None):
    """Document-grounded chat variant used by the Desk widget on a form.

    Grounds the answer on the document's readable fields; the caller still
    needs read permission on the document.
    """
    if not prompt:
        frappe.throw("prompt is required")
    doc = _resolve(doctype, name)
    doc.check_permission("read")
    fields = {
        df.fieldname: getattr(doc, df.fieldname)
        for df in doc.meta.fields
        if getattr(doc, df.fieldname, None) not in (None, "")
    }
    ctx = json.dumps(fields, default=str)[:4000]
    grounded = (
        f"The user is looking at {doctype} '{name}'. Document data:\n{ctx}\n\n"
        f"User question: {prompt}"
    )
    reply, session = _assistant_reply(grounded, session, model)
    return {"response": reply, "session": session, "doctype": doctype, "docname": name}


def _process_with_mcp(prompt, session, user, model=None):
    """Evaluation hook: answer through the real assistant core (read paths).

    Deliberately does NOT execute create/submit intents — evaluations must
    never write documents. Create/submit coverage goes through the dedicated
    workflow tests instead.
    """
    return _assistant_reply(prompt, session, model)[0]


def _handle_create_intent(doctype, prompt, session, user, mcp):
    from erp_ai.rbac import check_amount_limit, check_permission
    err = check_permission(user, doctype, "create")
    if err:
        return "🚫 " + err
    # Financial docs: enforce approval limit before even starting the draft
    if doctype in ("Sales Invoice", "Purchase Invoice", "Payment Entry", "Journal Entry"):
        _amount = _extract_amount(prompt)
        if _amount is not None:
            ok, limit = check_amount_limit(user, _amount)
            if not ok:
                fmt = frappe.utils.fmt_money(limit) if limit else "no limit"
                return f"🚫 Amount {frappe.utils.fmt_money(_amount)} exceeds your approval limit of {fmt}. A supervisor must approve this."
    if doctype == "Item":
        _data = extract_item_fields(prompt)
        if _data.get("item_name"):
            return guided_start(session, user, "Item", _data)
        return handle_create_item(prompt, mcp)
    if doctype == "Customer":
        return handle_create_customer(prompt, mcp)
    if doctype == "Supplier":
        return handle_create_supplier(prompt, mcp)
    if doctype in ("Sales Invoice", "Purchase Invoice"):
        _data = extract_invoice_fields(prompt)
        return guided_start(session, user, doctype, _data)
    _data = _extract_fields_for(doctype, prompt)
    return guided_start(session, user, doctype, _data)


def _extract_amount(prompt):
    """Extract the first plausible currency amount from free text."""
    if not prompt:
        return None
    from erp_ai.validators import parse_number
    candidates = re.findall(r"[0-9][0-9,]*\.?[0-9]*", prompt)
    if not candidates:
        return None
    return parse_number(candidates[0])


def _handle_view_intent(prompt, mcp):
    # Try to extract doctype from the prompt for RBAC
    _doc_match = re.search(r"\b(show|view|details|dekho|dikhhao)\s+(?:of\s+)?(?:item\s+|invoice\s+|customer\s+)?([A-Z][A-Z0-9\-]{2,20})", prompt, re.I)
    if _doc_match:
        _doc_name = _doc_match.group(2).upper()
        for _dt in ["Item", "Customer", "Supplier", "Sales Invoice", "Purchase Invoice"]:
            # get_document enforces read permission, so one call answers both
            # "does it exist" and "may this user read it" (frappe.db.exists()
            # checks neither and would leak the existence of other users' docs).
            _doc = mcp.call_tool("get_document", {"doctype": _dt, "name": _doc_name})
            if "error" not in _doc:
                return format_document_view(_dt, _doc)
        return f"Document '{_doc_name}' not found."
    return "Please specify which document to view. Example: 'show item STEEL-ROD'"


def _handle_report(report, mcp):
    name, config = report
    doctype = config.get("doctype", "Sales Invoice")
    result = mcp.call_tool("query_doctype", {"doctype": doctype, "filters": config.get("filters", {}), "fields": ["name"], "limit": 10000})
    count = result.get("count", 0)
    label = config.get("label", doctype)
    return f"📊 {label}: {count} records found."


def _extract_fields_for(doctype, prompt):
    if doctype == "Item":
        return extract_item_fields(prompt) or {}
    if doctype in ("Sales Invoice", "Purchase Invoice"):
        data = extract_invoice_fields(prompt) or {}
        if doctype == "Purchase Invoice" and "customer" in data:
            data["supplier"] = data.pop("customer")
        return data
    if doctype == "Customer":
        return extract_party_fields(prompt, "customer") or {}
    if doctype == "Supplier":
        return extract_party_fields(prompt, "supplier") or {}
    return {}


# ---------------------------------------------------------------------------
# ERP Operator: bounded tool-calling loop
# ---------------------------------------------------------------------------
# The LLM may answer directly, or request an ERP tool by replying with a single
# JSON object: {"tool": "<name>", "parameters": {...}}. The result is fed back
# and the loop repeats until the model answers in prose or hits the iteration
# cap. A live system snapshot is injected up front so even small local models
# (which cannot reliably emit JSON) still answer with real numbers instead of
# telling the user to open a menu.
_OPERATOR_MAX_ITERS = 3
_OPERATOR_SNAPSHOT_CHARS = 4000


def _operator_snapshot():
    """Live site counts the model can quote without a tool call. Best-effort."""
    try:
        from erp_ai.erp_tools import get_system_overview
        data = get_system_overview()
    except Exception:
        log_error_safely("erp_ai._operator_snapshot")
        return ""
    if not data:
        return ""
    text = json.dumps(data, default=str)
    if len(text) > _OPERATOR_SNAPSHOT_CHARS:
        text = text[:_OPERATOR_SNAPSHOT_CHARS] + "...(truncated)"
    return text


def _operator_system_prompt(user):
    """System prompt: operator role, callable tools, and live ERP state.

    Only read tools are advertised: operator writes must go through the
    draft -> confirm pipeline (preview, idempotency, audit), never a direct
    tool call from the model.
    """
    from erp_ai.erp_tools import get_erp_tools_list
    lines = [
        f"You are the ERP Operator for this ERPNext site. The user is "
        f"{frappe.utils.get_fullname(user)} ({user}).",
        "You have DIRECT access to the database through the tools below. NEVER tell",
        "the user to open a menu, click a report or navigate somewhere — call the",
        "tool yourself and report the real values you get back. If a count is in the",
        "snapshot below, quote it directly.",
        "",
        "To call a tool, reply with ONE JSON object and nothing else:",
        '{"tool": "get_customers", "parameters": {"limit": 10}}',
        "You will then receive the result; after that, answer the user in plain",
        "language. These tools are read-only: to create or change documents, tell",
        "the user to ask the assistant to create it (guided draft + confirmation).",
        "",
        "Available tools:",
    ]
    for tool in get_erp_tools_list():
        if tool.get("name", "").startswith(("create_", "update_", "delete_", "submit_")):
            continue
        params = ", ".join(tool.get("parameters", {}).keys()) or "no parameters"
        lines.append("- %s(%s): %s" % (tool["name"], params, tool["description"]))
    snapshot = _operator_snapshot()
    if snapshot:
        lines += ["", "Current live snapshot of this site:", snapshot]
    return "\n".join(lines)


def _iter_json_objects(text):
    """Yield each balanced-brace JSON object found in `text`.

    Tool-call parameters are nested objects, so a non-greedy regex would stop
    at the first inner `}` and hand json.loads a truncated payload. Scan with a
    brace counter, skipping braces that live inside strings.
    """
    depth = 0
    start = None
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth:
                depth -= 1
                if depth == 0 and start is not None:
                    yield text[start:i + 1]
                    start = None


def _parse_tool_call(text):
    """Return (tool_name, parameters) if the reply is a valid tool call, else None."""
    if not text or '"tool"' not in text:
        return None
    for candidate in _iter_json_objects(text):
        if '"tool"' not in candidate:
            continue
        try:
            payload = json.loads(candidate)
        except ValueError:
            continue
        name = payload.get("tool")
        params = payload.get("parameters") or {}
        if isinstance(name, str) and name and isinstance(params, dict):
            return (name, params)
    return None


def _fallback_to_llm(prompt, session, user, model):
    """Answer via the LLM with live ERP data, executing read tool calls on request.

    Read-only by design (audit P0: operator bypass): a model-requested write
    tool (create_*/update_*/delete_*/submit_*) is never executed here — those
    must go through the draft -> confirm pipeline with preview, idempotency
    and audit. The model gets a read-only observation and answers accordingly.
    """
    from erp_ai.erp_tools import ERP_TOOLS, execute_erp_tool
    system = _operator_system_prompt(user)
    reply = ask_llm(system + "\n\nUser: " + prompt + "\nAssistant:", model=model)

    for _iteration in range(_OPERATOR_MAX_ITERS):
        call = _parse_tool_call(reply)
        if not call:
            break
        name, params = call
        if name not in ERP_TOOLS:
            break
        if name.startswith(("create_", "update_", "delete_", "submit_")):
            observation = json.dumps({
                "tool": name, "error": "read-only operator",
                "message": "Writes are not allowed through the operator loop. "
                           "Tell the user to ask the assistant to create it, which "
                           "shows a preview and requires explicit confirmation.",
            })
        else:
            result = execute_erp_tool(name, params)
            observation = json.dumps(
                {"tool": name, "parameters": params, "result": result}, default=str
            )
        reply = ask_llm(
            system
            + "\n\nUser: " + prompt
            + "\n\nYou called %s and got:\n%s" % (name, observation)
            + "\n\nNow answer the user using this data. Do not call another tool "
              "unless the data above is insufficient.\nAssistant:",
            model=model,
        )
    return reply


# ---------------------------------------------------------------------------
# Voice-enhanced assistant
# ---------------------------------------------------------------------------
@frappe.whitelist()
def ask_v2_with_voice(prompt, session=None, model=None, voice=True):
    """Enhanced AI assistant with optional voice output."""
    if not prompt:
        frappe.throw("prompt is required")
    result = ask_v2(prompt, session, model)
    response_text = result.get("response", "")
    audio_url = None
    if voice and response_text:
        from erp_ai.voice.toggle import is_voice_enabled
        if is_voice_enabled():
            tts_result = text_to_speech(response_text)
            audio_url = tts_result.get("url")
    return {"response": response_text, "session": result.get("session"), "audio_url": audio_url}


# ---------------------------------------------------------------------------
# Workflow endpoints - NOW routed through preview/confirmation flow
# ---------------------------------------------------------------------------
@frappe.whitelist()
def workflow_shipment_receipt(data=None):
    """Record an incoming shipment via preview -> confirm flow.

    This endpoint no longer creates documents directly. It parses the request,
    saves a draft, and returns a preview for confirmation.
    """
    import json
    data = json.loads(data) if isinstance(data, str) else (data or {})
    user = frappe.session.user
    session = frappe.session.session_id
    if not session:
        session = "sess-" + frappe.generate_hash(length=12)
        frappe.session.session_id = session

    # Parse the shipment data
    parsed = handle_shipment_nl_request(data)
    if not parsed.get("ok"):
        return parsed

    # Save as draft for confirmation
    draft_id = save_shipment_draft(session, user, parsed.get("data", {}))
    if not draft_id:
        return {"ok": False, "error": "Failed to save draft"}

    return {
        "ok": True,
        "mode": "draft_shipment",
        "draft_id": draft_id,
        "message": "Shipment draft saved. Please confirm to proceed.",
        "preview": parsed.get("data", {})
    }


@frappe.whitelist()
def workflow_stock_issue(data=None):
    """Issue/transfer stock via preview -> confirm flow.

    This endpoint no longer creates documents directly. It parses the request,
    saves a draft, and returns a preview for confirmation.
    """
    import json
    data = json.loads(data) if isinstance(data, str) else (data or {})
    user = frappe.session.user
    session = frappe.session.session_id
    if not session:
        session = "sess-" + frappe.generate_hash(length=12)
        frappe.session.session_id = session

    # Parse the stock issue data with warehouse requirement
    parsed = handle_stock_issue_nl_request(data)
    if not parsed.get("ok"):
        return parsed

    # Require from_warehouse
    if not parsed.get("data", {}).get("from_warehouse"):
        return {
            "ok": False,
            "error": "from_warehouse is required. Please specify the source warehouse."
        }

    # Save as draft for confirmation
    draft_id = save_stock_issue_draft(session, user, parsed.get("data", {}))
    if not draft_id:
        return {"ok": False, "error": "Failed to save draft"}

    return {
        "ok": True,
        "mode": "draft_stock_issue",
        "draft_id": draft_id,
        "message": "Stock issue draft saved. Please confirm to proceed.",
        "preview": parsed.get("data", {})
    }


# Draft/Confirm helper functions for workflow endpoints
# ---------------------------------------------------------------------------

def handle_shipment_nl_request(data):
    """Parse shipment natural language request and return structured data.

    Parsing is local; the parsed payload is persisted by the caller only as a
    draft via ``erp_ai.draft_workflow``, never materialized directly here.
    """
    import json

    text = data.get("text", "") or data.get("message", "")
    if not text:
        return {"ok": False, "error": "No shipment text provided"}

    mcp = FrappeMCP()
    result = handle_shipment_nl(text, mcp)
    return result


def handle_stock_issue_nl_request(data):
    """Parse stock issue natural language request and return structured data.

    Parsing is local; the parsed payload is persisted by the caller only as a
    draft via ``erp_ai.draft_workflow``, never materialized directly here.
    """
    import json

    text = data.get("text", "") or data.get("message", "")
    if not text:
        return {"ok": False, "error": "No stock issue text provided"}

    mcp = FrappeMCP()
    result = handle_issue_nl(text, mcp)
    return result


def save_shipment_draft(session, user, data):
    """Save a shipment draft for later confirmation.

    Persisted only through the auditable draft store (``AI Assistant Action``).
    A rollback_reference is recorded only if the action later reaches a terminal
    state (completed or failed) through confirmation.
    """
    from erp_ai.draft_workflow import create_draft

    draft_data = {
        "supplier": data.get("supplier", ""),
        "vehicle_no": data.get("vehicle_no", ""),
        "items": data.get("items", []),
        "remarks": data.get("remarks", ""),
    }
    # A Purchase Receipt carries its warehouse on each item row, so the
    # resolved one must be pushed down here: create_draft normalizes the
    # payload against the DocType schema, which has no top-level warehouse,
    # and would otherwise strip it before confirmation.
    warehouse = data.get("warehouse") or ""
    for item in draft_data["items"]:
        if isinstance(item, dict) and not item.get("warehouse"):
            item["warehouse"] = warehouse

    draft = create_draft(
        session=session,
        action="create",
        target_doctype="Purchase Receipt",
        draft_data=draft_data,
        user=user,
    )
    return draft.get("name") if isinstance(draft, dict) else None


def save_stock_issue_draft(session, user, data):
    """Save a stock issue draft for later confirmation.

    Persisted only through the auditable draft store (``AI Assistant Action``).
    A rollback_reference is recorded only if the action later reaches a terminal
    state (completed or failed) through confirmation.
    """
    from erp_ai.draft_workflow import create_draft

    draft_data = {
        "from_warehouse": data.get("from_warehouse", ""),
        "to_warehouse": data.get("to_warehouse", ""),
        "items": data.get("items", []),
        "purpose": data.get("purpose", "Material Issue"),
        "remarks": data.get("remarks", ""),
    }

    draft = create_draft(
        session=session,
        action="create",
        target_doctype="Stock Entry",
        draft_data=draft_data,
        user=user,
    )
    return draft.get("name") if isinstance(draft, dict) else None


def confirm_workflow_action(action_id, user, data=None):
    """Confirm a workflow action and execute it through the draft engine.

    This is the public confirm/cancel boundary; it delegates to
    ``erp_ai.draft_workflow.confirm_draft`` so the finalisation path
    (pending -> processing -> completed/failed) and audit writes stay centralized.
    """

    confirm_result = confirm_draft(
        session=frappe.session.session_id,
        action_id=action_id,
        user=user,
    )

    if isinstance(confirm_result, dict) and confirm_result.get("error"):
        return confirm_result

    # confirm_draft already materializes the document on success. If the caller
    # still wants an explicit execution hook, it can call
    # ``erp_ai.draft_workflow.create_document_from_draft`` directly.
    return confirm_result


def cancel_workflow_action(action_id, user):
    """Cancel a pending workflow action.

    This is the public cancel boundary. It is deliberately action-id based rather
    than session based: the caller names the exact action to abandon, so a stale
    browser session cannot cancel the wrong draft. Cancellation writes only
    through the auditable action DocType.
    """
    import frappe

    action = frappe.get_doc("AI Assistant Action", action_id)
    if action.user != user:
        return {"ok": False, "error": "Not your action"}
    if action.status not in ("pending",):
        return {"ok": False, "error": "Action cannot be cancelled in its current state"}
    action.status = "cancelled"
    action.save()
    return {"ok": True, "action_id": action_id}


def make_token(user="Administrator"):
    """CLI-only: regenerate API token pair."""
    frappe.only_for("Administrator")
    u = frappe.get_doc("User", user)
    u.api_key = frappe.generate_hash(length=15)
    secret = frappe.generate_hash(length=15)
    u.api_secret = secret
    u.save()
    frappe.db.commit()
    print("%s:%s" % (u.api_key, secret))


# ---------------------------------------------------------------------------
# Workspace setup
# ---------------------------------------------------------------------------
@frappe.whitelist()
def setup_workspace(**kwargs):
    """Create the AI Assistant Hub workspace from the bundled JSON spec.

    Requires System Manager role — workspaces and pages are privileged setup objects.
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Only System Manager can set up the workspace", frappe.PermissionError)
    import json
    import pathlib
    try:
        if not frappe.db.exists("Page", "ai-assistant"):
            frappe.get_doc({"doctype": "Page", "page_name": "ai-assistant", "module": "ERP AI", "standard": "Yes", "title": "AI Assistant"}).insert()
        # Fixture lives in the ERP AI module dir (Frape-standard location),
        # i.e. <app>/erp_ai/erp_ai/workspace/... — parent is <app>/erp_ai.
        ws_path = pathlib.Path(__file__).resolve().parent / "erp_ai" / "workspace" / "ai_assistant_hub" / "ai_assistant_hub.json"
        spec = json.loads(ws_path.read_text(encoding="utf-8"))
        content_blocks = json.loads(spec["content"])
        shortcuts_data = spec.get("shortcuts", [])
        links_data = _available_workspace_links(spec.get("links", []))
        if frappe.db.exists("Workspace", {"label": "AI Assistant Hub"}):
            ws = frappe.get_doc("Workspace", "AI Assistant Hub")
            ws.content = json.dumps(content_blocks)
            ws.shortcuts = []
            for s in shortcuts_data:
                ws.append("shortcuts", s)
            ws.links = []
            for link in links_data:
                ws.append("links", link)
            ws.number_cards = []
            for card in spec.get("number_cards", []):
                ws.append("number_cards", card)
            for k in ("label","title","module","public","indicator_color","sequence_id"):
                if k in spec:
                    setattr(ws, k, spec[k])
            ws.save()
            frappe.db.commit()
            return ws.name
        ws = frappe.new_doc("Workspace")
        ws.label = spec.get("label", "AI Assistant Hub")
        ws.title = spec.get("title", "AI Assistant Hub")
        ws.module = spec.get("module", "ERP AI")
        ws.public = spec.get("public", 1)
        ws.indicator_color = spec.get("indicator_color", "green")
        ws.sequence_id = spec.get("sequence_id", 1.0)
        ws.content = json.dumps(content_blocks)
        for s in shortcuts_data:
            ws.append("shortcuts", s)
        for link in links_data:
            ws.append("links", link)
        for card in spec.get("number_cards", []):
            ws.append("number_cards", card)
        ws.insert()
        frappe.db.commit()
        return ws.name
    except Exception:
        import traceback
        traceback.print_exc()
        return None


def _available_workspace_links(links):
    """Keep fixture links that exist on this site's installed apps.

    ERPNext deployments vary: HRMS and custom app DocTypes are optional. A
    missing target must not prevent the rest of the workspace from syncing.
    Empty card breaks are omitted after filtering.
    """
    available = []
    pending_break = None
    pending_links = []
    for link in links:
        if link.get("type") == "Card Break":
            if pending_break and pending_links:
                available.extend([pending_break, *pending_links])
            pending_break = link
            pending_links = []
            continue
        link_type = link.get("link_type")
        target = link.get("link_to")
        exists = (
            frappe.db.exists("DocType", target)
            if link_type == "DocType"
            else frappe.db.exists("Page", target)
            if link_type == "Page"
            else True
        )
        if exists:
            pending_links.append(link)
    if pending_break and pending_links:
        available.extend([pending_break, *pending_links])
    return available


@frappe.whitelist()
def sync_workspace_from_json():
    """Public entry point for install-time hook and manual refresh.

    Reads the bundled workspace JSON and writes it to the live Workspace
    DocType. Requires System Manager role.
    """
    return setup_workspace()


# ---------------------------------------------------------------------------
# Voice toggle endpoints
# ---------------------------------------------------------------------------
@frappe.whitelist()
def voice_status():
    """Get current voice on/off status for the user."""
    from erp_ai.voice.toggle import is_voice_enabled
    return {"voice_enabled": is_voice_enabled()}


@frappe.whitelist()
def voice_toggle():
    """Toggle voice on/off. Returns new state."""
    from erp_ai.voice.toggle import toggle_voice
    new_state = toggle_voice()
    return {"voice_enabled": new_state, "message": "Voice " + ("ON" if new_state else "OFF")}


@frappe.whitelist()
def voice_set(enabled):
    """Explicitly set voice on/off."""
    from erp_ai.voice.toggle import set_voice_enabled
    set_voice_enabled(bool(enabled))
    return {"voice_enabled": bool(enabled)}


# ---------------------------------------------------------------------------
# Health check endpoint
# ---------------------------------------------------------------------------
@frappe.whitelist()
def health():
    """Run a comprehensive app health check."""
    try:
        from erp_ai.diagnostics import health_check
    except ImportError:
        health_check = None
    if health_check:
        return health_check()
    return {"status": "ok", "note": "diagnostics module not available"}


# ---------------------------------------------------------------------------
# List available doctypes and capabilities
# ---------------------------------------------------------------------------
@frappe.whitelist()
def capabilities():
    """Return what the AI can do — doctypes, actions, features."""
    from erp_ai.mcp.server import FrappeMCP
    mcp = FrappeMCP()
    return {
        "doctypes": get_all_doctypes(),
        "actions": ["create", "view", "print", "report", "submit", "cancel"],
        "tools": [t["name"] for t in mcp.tools],
        "features": {
            "voice": True,
            "guided_conversation": True,
            "draft_workflow": True,
            "reports": True,
        },
    }


# ---------------------------------------------------------------------------
# RBAC endpoints
# ---------------------------------------------------------------------------
@frappe.whitelist()
def my_permissions():
    """Return the current user's roles and allowed doctypes."""
    from erp_ai.rbac import get_allowed_doctypes, get_user_categories, get_user_roles
    return {
        "roles": get_user_roles(),
        "categories": get_user_categories(),
        "can_create": get_allowed_doctypes(action="create"),
        "can_submit": get_allowed_doctypes(action="submit"),
        "can_read": get_allowed_doctypes(action="read"),
    }


@frappe.whitelist()
def check_my_permission(doctype, action="read"):
    """Check if the current user can perform an action on a doctype."""
    from erp_ai.rbac import can, get_doctype_category
    allowed = can(None, doctype, action)
    return {"doctype": doctype, "action": action, "allowed": allowed, "category": get_doctype_category(doctype)}


# ---------------------------------------------------------------------------
# Barcode / OCR / Audit / Evaluation / Knowledge endpoints
# ---------------------------------------------------------------------------
@frappe.whitelist()
def barcode_lookup(code):
    """Resolve a scanned barcode/QR to an ERP document (permission-checked)."""
    from erp_ai.barcode import resolve_barcode
    return resolve_barcode(code)


@frappe.whitelist()
def ocr_extract_text(file_url):
    """Extract text from an uploaded File (image/PDF) using OCR.

    Accepts the URL of a Frappe-uploaded File doctype so the file is
    already inside Frappe's managed storage, never an arbitrary server path.
    """
    import os

    from frappe.utils.file_manager import get_file

    from erp_ai.attachments import ALLOWED_BASE_DIR, _safe_path, extract_text_from_file, validate_file

    if not file_url:
        frappe.throw("file_url is required")
    # Only operate on Frappe-managed files
    if not file_url.startswith(("/files/", "/private/files/")):
        return {"error": "Only Frappe-managed uploads are supported (use a /files/ URL)"}
    # frappe.utils.file_manager.get_file() reads straight from the filesystem
    # without any permission check, so resolve the File doc and enforce read
    # permission first: another user's private upload must not be OCR-able by
    # URL. File.has_permission() still allows public files and files attached to
    # a document the caller may read, mirroring the Desk behaviour.
    file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not file_name or not frappe.has_permission("File", "read", doc=file_name):
        frappe.throw(
            frappe._("You do not have permission to read this file"),
            frappe.PermissionError,
        )
    try:
        content, filename = get_file(file_url)
    except Exception:
        return {"error": "File not found in Frappe storage"}
    if check_illegal_operation(filename):
        return {"error": "File name not allowed"}
    err = validate_file(filename, len(content), content_head=content[:16])
    if err:
        return {"error": err}
    safe = _safe_path(ALLOWED_BASE_DIR, filename)
    if not safe:
        return {"error": "Could not resolve a safe path for this upload"}
    os.makedirs(ALLOWED_BASE_DIR, exist_ok=True)
    with open(safe, "wb") as f:
        f.write(content)
    try:
        return extract_text_from_file(safe)
    finally:
        # Temp uploads are deleted after processing (no retention surface)
        try:
            os.remove(safe)
        except OSError:
            pass


@frappe.whitelist()
def audit_history(session=None, limit=50):
    """Return the current user's AI action audit trail."""
    from erp_ai.audit import get_audit_trail
    user = frappe.session.user
    if not session:
        # No session given: list the user's most recent actions across sessions
        records = frappe.get_all("AI Assistant Action",
            filters={"user": user},
            fields=["name", "action", "target_doctype", "target_docname", "status",
                    "confirmed_at", "failure_reason", "creation", "session_id"],
            order_by="creation desc",
            limit_page_length=max(1, min(int(limit or 50), 200)))
        return {"records": records}
    return {"records": get_audit_trail(session, user)}


@frappe.whitelist()
def knowledge_freshness():
    """List knowledge sources with freshness status and citations."""
    from erp_ai.knowledge.sources import SOURCES, check_freshness
    result = check_freshness()
    result["sources"] = [
        {
            "id": s.id, "title": s.title, "source_type": s.source_type,
            "version": s.version, "last_updated": s.last_updated,
            "confidence": s.confidence, "url": s.url, "fresh": s.is_fresh(),
            "citation": s.citation(),
        }
        for s in SOURCES.values()
    ]
    return result


@frappe.whitelist()
def citation_for(doctype):
    """Return the citation for a doctype's knowledge source."""
    if not doctype:
        frappe.throw("doctype is required")
    from erp_ai.knowledge.sources import get_citation_for_doctype
    return {"doctype": doctype, "citation": get_citation_for_doctype(doctype)}


@frappe.whitelist()
def run_evaluation(category=None, limit=20):
    """Run the model evaluation suite. Requires System Manager."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Only System Manager can run evaluations", frappe.PermissionError)
    from erp_ai.evaluation import EVAL_SUITE, run_evaluation
    cases = EVAL_SUITE
    if category:
        cases = [c for c in EVAL_SUITE if c.category == category]
    if limit:
        cases = cases[: max(1, int(limit))]
    # Ask function: use the real ask() pipeline so evaluation exercises integrations
    def _ask(prompt):
        return _process_with_mcp(prompt, frappe.generate_hash(length=8), frappe.session.user, None)
    return run_evaluation(_ask, cases)


# ---------------------------------------------------------------------------
# Help System API
# ---------------------------------------------------------------------------


@frappe.whitelist()
def help_get_categories():
    """Return help article categories."""
    from erp_ai.help.articles import get_help_categories
    return get_help_categories()


@frappe.whitelist()
def help_get_quick_actions():
    """Return quick-action cards."""
    from erp_ai.help.articles import get_quick_actions
    return get_quick_actions()


@frappe.whitelist()
def help_get_articles(category=None, search=None, limit=50):
    """Return help articles, optionally filtered."""
    from erp_ai.help.articles import get_articles
    return get_articles(category=category, search=search, limit=int(limit))


@frappe.whitelist()
def help_get_article(name):
    """Return a single help article."""
    from erp_ai.help.articles import get_article
    return get_article(name)


@frappe.whitelist()
def help_search(query):
    """Search help articles by query string."""
    from erp_ai.help.articles import search_articles
    return search_articles(query)


@frappe.whitelist()
def help_get_knowledge_base():
    """Return the ERPNext knowledge base summary."""
    from erp_ai.help.articles import get_knowledge_base
    return get_knowledge_base()


# ---------------------------------------------------------------------------
# LLM Model Discovery API (OpenRouter-style model listing)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def list_available_models(provider=None, api_key="", base_url=""):
    """List all available models from the specified LLM provider.

    Like OpenRouter's /models endpoint: returns a list of model objects with
    "id", "name", and provider-specific metadata. Used by the AI Settings UI
    to populate the model dropdown dynamically when the provider changes.

    Args:
        provider (str): LLM provider key, e.g. "ollama", "openrouter", "groq".
            Defaults to the currently configured provider in AI Settings.
        api_key (str): Provider API key. If omitted, reads from AI Settings.
            Only required for cloud providers (OpenRouter, Together, Groq, etc.).
            Local providers (Ollama, LM Studio) ignore this.
        base_url (str): Custom base URL for local providers. Only used for
            Ollama, LM Studio, or Custom API providers.

    Returns:
        list[dict]: Each dict has at least "id" (model identifier) and "name"
        (human-readable label). Cloud providers also return "context_window",
        "pricing", "provider", etc.
    """
    # Settings-page helper. It reads AI Settings (including the configured API
    # key) and then performs an outbound HTTP request to a caller-supplied
    # ``base_url``, so it is a privileged surface, gated like the settings it
    # serves: a caller who is not a System Manager must not be able to make the
    # server fetch an arbitrary URL.
    if "System Manager" not in frappe.get_roles():
        frappe.throw(
            frappe._("Only System Manager can list provider models"),
            frappe.PermissionError,
        )

    # ``import requests as _requests`` used to live here, which left the extracted
    # ``_list_*_models`` helpers at module scope referencing an undefined name —
    # every provider raised NameError. They now use the module-level ``requests``.

    from erp_ai.llm import LLMProvider

    # Resolve provider from AI Settings if not given
    if not provider:
        settings = frappe.get_single("AI Settings")
        if settings:
            # Select stores the full option string ("ollama|Ollama (Local - Free)"):
            # keep only the key part so both spellings resolve below.
            provider = (settings.get("llm_provider") or "").split("|", 1)[0].strip()
        else:
            provider = LLMProvider.OLLAMA
    provider = (provider or LLMProvider.OLLAMA).strip().lower()

    # Resolve credentials
    if not api_key:
        settings = frappe.get_single("AI Settings")
        if settings:
            api_key = (settings.get("api_key") or "").strip()
    if not base_url:
        settings = frappe.get_single("AI Settings")
        if settings:
            base_url = (settings.get("custom_api_base_url") or "").strip()

    provider_methods = {
        "ollama": lambda: _list_ollama_models(base_url),
        "lm_studio": lambda: _list_openai_compat_models(
            base_url or "http://localhost:1234/v1", api_key
        ),
        "openrouter": lambda: _list_openrouter_models(api_key),
        "together": lambda: _list_together_models(api_key),
        "groq": lambda: _list_groq_models(api_key),
        "anthropic": lambda: _list_anthropic_models(api_key),
        "openai": lambda: _list_openai_models(api_key),
        "gemini": lambda: _list_gemini_models(api_key),
        "mistral": lambda: _list_mistral_models(api_key),
        "custom": lambda: _list_openai_compat_models(
            base_url or "http://localhost:8080/v1", api_key
        ),
    }

    method = provider_methods.get(provider)
    if method is None:
        frappe.throw(f"Unknown LLM provider: {provider}")

    try:
        return method()
    except Exception:
        log_error_safely("erp_ai.list_available_models")
        frappe.throw(
            _("Failed to list models for {0}").format(provider)
        )


def _list_ollama_models(base_url=None):
    """Query Ollama /api/tags and return local models."""
    base_url = base_url or _get_ollama_base_url()
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        frappe.msgprint(_("Could not reach Ollama at {0}: {1}").format(base_url, e))
        return []

    models = []
    for model in data.get("models", []):
        name = model.get("name") or "unknown"
        models.append({
            "id": name,
            "name": name,
            "provider": "ollama",
            "owned_by": "local",
        })
    return models


def _list_openai_compat_models(base_url, api_key=""):
    """List models from any OpenAI-compatible API (LM Studio, Custom, etc.)."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        resp = requests.get(f"{base_url}/models", headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        frappe.msgprint(_("Could not reach API at {0}: {1}").format(base_url, e))
        return []

    models = []
    for m in data.get("data", []):
        models.append({
            "id": m.get("id") or m.get("name") or "unknown",
            "name": m.get("id") or m.get("name") or "unknown",
            "provider": "custom",
            "owned_by": m.get("owned_by", "local"),
        })
    return models


def _list_openrouter_models(api_key):
    """Fetch the full model catalog from OpenRouter."""
    if not api_key:
        frappe.msgprint(_("OpenRouter API key is required to list models."))
        return []

    try:
        resp = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        frappe.msgprint(_("Could not reach OpenRouter: {0}").format(e))
        return []

    models = []
    for m in data.get("data", []):
        models.append({
            "id": m.get("id", ""),
            "name": m.get("id", ""),
            "provider": "openrouter",
            "context_window": m.get("context_window"),
            "pricing": m.get("pricing", {}),
            "provider_info": {
                "id": m.get("provider", {}).get("id", ""),
                "name": m.get("provider", {}).get("name", ""),
            },
            "object": m.get("object", "model"),
        })
    return models


def _list_together_models(api_key):
    """Fetch models from Together AI."""
    if not api_key:
        frappe.msgprint(_("Together AI API key is required to list models."))
        return []

    try:
        resp = requests.get(
            "https://api.together.ai/models",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        frappe.msgprint(_("Could not reach Together AI: {0}").format(e))
        return []

    models = []
    for m in data.get("models", []):
        models.append({
            "id": m.get("name") or m.get("model", ""),
            "name": m.get("display_name") or m.get("name", ""),
            "provider": "together",
            "context_window": m.get("context_length"),
            "pricing": {
                "input": m.get("pricing", {}).get("input", "unknown"),
                "output": m.get("pricing", {}).get("output", "unknown"),
            },
            "owned_by": "together",
        })
    return models


def _list_groq_models(api_key):
    """Fetch models from Groq."""
    if not api_key:
        frappe.msgprint(_("Groq API key is required to list models."))
        return []

    try:
        resp = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        frappe.msgprint(_("Could not reach Groq: {0}").format(e))
        return []

    models = []
    for m in data.get("data", []):
        models.append({
            "id": m.get("id", ""),
            "name": m.get("id", ""),
            "provider": "groq",
            "context_window": m.get("context_window"),
            "owned_by": m.get("owned_by", "groq"),
        })
    return models


def _list_anthropic_models(api_key):
    """Return a curated list of Anthropic models.

    Anthropic does not expose a public model listing endpoint, so we return
    the well-known production models. The API key is still required to prove
    the user has credentials.
    """
    if not api_key:
        frappe.msgprint(_("Anthropic API key is required to authenticate."))
        return []

    known_models = [
        ("claude-opus-4-5-20251001", "Claude Opus 4.5", 200000),
        ("claude-sonnet-4-5-20250929", "Claude Sonnet 4.5", 200000),
        ("claude-haiku-4-5-20251001", "Claude Haiku 4.5", 200000),
        ("claude-opus-4-1-20241219", "Claude Opus 4 (2024)", 200000),
        ("claude-sonnet-4-20241022", "Claude Sonnet 4 (2024)", 200000),
        ("claude-haiku-3-5-20241022", "Claude Haiku 3.5", 200000),
        ("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", 200000),
        ("claude-3-opus-20240229", "Claude 3 Opus", 200000),
        ("claude-3-sonnet-20240229", "Claude 3 Sonnet", 200000),
        ("claude-3-haiku-20240307", "Claude 3 Haiku", 200000),
        ("claude-2.1", "Claude 2.1", 200000),
        ("claude-2.0", "Claude 2", 100000),
        ("claude-instant-1.2", "Claude Instant 1.2", 100000),
    ]
    return [
        {
            "id": model_id,
            "name": display_name,
            "provider": "anthropic",
            "context_window": context_window,
            "owned_by": "anthropic",
        }
        for model_id, display_name, context_window in known_models
    ]


def _list_openai_models(api_key):
    """List OpenAI models via the official API."""
    if not api_key:
        frappe.msgprint(_("OpenAI API key is required to list models."))
        return []

    try:
        resp = requests.get(
            "https://api.openai.com/v1/models",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        frappe.msgprint(_("Could not reach OpenAI: {0}").format(e))
        return []

    models = []
    for m in data.get("data", []):
        models.append({
            "id": m.get("id", ""),
            "name": m.get("id", ""),
            "provider": "openai",
            "context_window": m.get("context_window"),
            "owned_by": m.get("owned_by", "openai"),
        })
    return models


def _list_gemini_models(api_key):
    """Return a curated list of Google Gemini models.

    Gemini does not expose a public model listing endpoint via the REST API
    in the same way OpenAI does, so we return the well-known production models.
    """
    if not api_key:
        frappe.msgprint(_("Google Gemini API key is required to authenticate."))
        return []

    known_models = [
        ("gemini-2.5-pro", "Gemini 2.5 Pro", 1000000),
        ("gemini-2.5-flash", "Gemini 2.5 Flash", 1000000),
        ("gemini-2.0-flash", "Gemini 2.0 Flash", 1000000),
        ("gemini-2.0-flash-lite", "Gemini 2.0 Flash Lite", 1000000),
        ("gemini-1.5-pro", "Gemini 1.5 Pro", 2000000),
        ("gemini-1.5-flash", "Gemini 1.5 Flash", 1000000),
        ("gemini-1.5-flash-8b", "Gemini 1.5 Flash-8B", 1000000),
        ("gemini-1.0-pro", "Gemini 1.0 Pro", 30720),
        ("gemini-1.0-pro-vision", "Gemini 1.0 Pro Vision", 30720),
        ("gemini-1.0-ultra", "Gemini 1.0 Ultra", 32768),
    ]
    return [
        {
            "id": model_id,
            "name": display_name,
            "provider": "gemini",
            "context_window": context_window,
            "owned_by": "google",
        }
        for model_id, display_name, context_window in known_models
    ]


def _list_mistral_models(api_key):
    """Return a curated list of Mistral models.

    Mistral's API does not expose a simple model listing endpoint, so we
    return the well-known production models.
    """
    if not api_key:
        frappe.msgprint(_("Mistral API key is required to authenticate."))
        return []

    known_models = [
        ("mistral-large-latest", "Mistral Large 2", 128000),
        ("mistral-medium-latest", "Mistral Medium", 128000),
        ("mistral-small-latest", "Mistral Small 3", 128000),
        ("open-mixtral-8x22b", "Mixtral 8x22B", 128000),
        ("open-mixtral-8x7b", "Mixtral 8x7B", 32000),
        ("open-mistral-7b", "Mistral 7B", 32000),
        ("codestral-latest", "Codestral (Code)", 32000),
        ("ministral-8b-latest", "Ministral 8B", 32000),
        ("ministral-3b-latest", "Ministral 3B", 32000),
    ]
    return [
        {
            "id": model_id,
            "name": display_name,
            "provider": "mistral",
            "context_window": context_window,
            "owned_by": "mistral",
        }
        for model_id, display_name, context_window in known_models
    ]


def _get_ollama_base_url():
    """Read the Ollama base URL from AI Settings or environment."""
    settings = frappe.get_single("AI Settings")
    if settings:
        base_url = (settings.get("custom_api_base_url") or "").strip()
        if base_url:
            return base_url
    return os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434"
