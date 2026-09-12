# ---------------------------------------------------------------------------
# ERP AI - Public API facade.
#
# Thin routing layer. All real logic lives in focused modules:
#   llm/ schema/ intents/ safety/ questions/ validators/
#   reports/ duplication/ handlers/ workflows/ voice/
#   conversation/ mcp/ knowledge/
# ---------------------------------------------------------------------------
import json
import re

import frappe
import requests
from frappe.utils import fmt_money

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
    save_draft,
)
from erp_ai.handlers import (
    handle_count_query,
    handle_create_customer,
    handle_create_item,
    handle_create_supplier,
    handle_print,
)
from erp_ai.handlers.formatters import format_document_view
from erp_ai.intents import detect_intent
from erp_ai.knowledge.erpnext_kb import get_kb_summary, get_knowledge_excerpt
from erp_ai.llm import AI_ALLOWED_MODELS, DEFAULT_MODEL, _allowed_model, ask_ollama
from erp_ai.mcp.server import FrappeMCP
from erp_ai.reports import detect_report
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
    return {"response": ask_ollama(prompt)}


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


def _count(dt, filters=None):
    if not frappe.has_permission(dt, "read"):
        return None
    try:
        return frappe.db.count(dt, filters=filters)
    except Exception:
        try:
            return frappe.db.count(dt)
        except Exception:
            return None


def _run_intent(it):
    kind = it.get("kind", "count")
    try:
        if kind == "bin_sum":
            if not frappe.has_permission("Bin", "read"):
                return {"ok": False}
            # NOTE: DocType-level check only; User Permissions (warehouse/company)
            # are not enforced at the SQL level. For restricted users, consider
            # filtering via frappe.get_all("Bin") with permission_query_conditions.
            n = frappe.db.sql("SELECT COALESCE(SUM(actual_qty),0) FROM tabBin")[0][0]
            return {"ok": True, "answer": f"Total stock: {_num(n)} units."}
        if kind == "si_unpaid":
            if not frappe.has_permission("Sales Invoice", "read"):
                return {"ok": False}
            # NOTE: Same as above — DocType check only, not User Permissions.
            cnt = frappe.db.count("Sales Invoice", {"docstatus": 1, "outstanding_amount": [">", 0]})
            amt = frappe.db.sql("SELECT COALESCE(SUM(outstanding_amount),0) FROM tabSales Invoice WHERE docstatus=1 AND outstanding_amount>0")[0][0]
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
            return _run_intent(it)
    if _COUNT_WORDS.search(q):
        for phrase, dt in sorted(_DATA_WORDS.items(), key=lambda kv: -len(kv[0])):
            if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", q):
                n = _count(dt)
                if n is not None:
                    return {"ok": True, "answer": f"There are {n:,} {_plural(n, phrase)}."}
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
            hits = frappe.get_all(doctype, filters={f: ["like", f"%{name}%"]}, limit_page_length=1, pluck="name")
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
    return {"summary": ask_ollama(prompt)}


@frappe.whitelist()
def draft_email(purpose, recipient=None, doctype=None, name=None):
    """Draft a professional email, optionally grounded on an ERPNext document."""
    ctx = ""
    if doctype and name:
        doc = frappe.get_doc(doctype, name)
        doc.check_permission("read")
        ctx = json.dumps({df.fieldname: getattr(doc, df.fieldname) for df in doc.meta.fields if getattr(doc, df.fieldname, None) not in (None, "")}, default=str)[:4000]
    prompt = f"Draft a professional business email. Purpose: {purpose}. Recipient: {recipient or 'Customer'}. Context: {ctx}. Include a Subject line. Keep it under 150 words."
    return {"email": ask_ollama(prompt)}


# ---------------------------------------------------------------------------
# Desk assistant with memory
# ---------------------------------------------------------------------------
@frappe.whitelist()
def ask(prompt, session=None, model=None):
    """Desk AI assistant with saved memory + Frappe-aware context."""
    if not prompt:
        frappe.throw("prompt is required")
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
    full_prompt = f"{system}\n\nConversation history:\n{mem}\n\nUser: {prompt}\nAssistant:"
    reply = None
    data = _data_answer(prompt)
    if data.get("ok"):
        reply = data["answer"]
    if not reply:
        reply = ask_ollama(full_prompt, model)
    frappe.get_doc({"doctype": "AI Chat Message", "user": user, "session_id": session, "role": "user", "content": prompt}).insert()
    frappe.get_doc({"doctype": "AI Chat Message", "user": user, "session_id": session, "role": "assistant", "content": reply}).insert()
    return {"response": reply, "session": session}


@frappe.whitelist()
def ask_with_doc(doctype, name, prompt, session=None):
    """Like ask() but injects the current document fields."""
    if not prompt:
        frappe.throw("prompt is required")
    session = session or frappe.generate_hash(length=10)
    user = frappe.session.user
    doc = _resolve(doctype, name)
    doc.check_permission("read")
    fields = {df.fieldname: getattr(doc, df.fieldname) for df in doc.meta.fields if getattr(doc, df.fieldname, None) not in (None, "")}
    data = json.dumps(fields, default=str)[:4000]
    full_prompt = f"You are an ERP assistant. The user is looking at {doctype} '{name}'.\nDocument data:\n{data}\n\nUser question: {prompt}\nAnswer:"
    reply = ask_ollama(full_prompt)
    frappe.get_doc({"doctype": "AI Chat Message", "user": user, "session_id": session, "role": "user", "content": prompt}).insert()
    frappe.get_doc({"doctype": "AI Chat Message", "user": user, "session_id": session, "role": "assistant", "content": reply}).insert()
    return {"response": reply, "session": session}


# ---------------------------------------------------------------------------
# Voice endpoints
# ---------------------------------------------------------------------------
@frappe.whitelist()
def voice_to_text_endpoint(audio, fmt="webm"):
    """Convert audio (base64) to text."""
    import base64
    audio_bytes = base64.b64decode(audio) if audio else None
    return voice_to_text(audio_bytes, fmt)


@frappe.whitelist()
def text_to_speech_endpoint(text, lang="en"):
    """Convert text to speech audio URL."""
    return text_to_speech(text, lang)


# ---------------------------------------------------------------------------
# Enhanced AI assistant with MCP tool access (ask_v2)
# ---------------------------------------------------------------------------
@frappe.whitelist()
def ask_v2(prompt, session=None, model=None):
    """Enhanced AI assistant with MCP tool access."""
    if not prompt:
        frappe.throw("prompt is required")
    session = session or frappe.generate_hash(length=10)
    user = frappe.session.user
    frappe.get_doc({"doctype": "AI Chat Message", "user": user, "session_id": session, "role": "user", "content": prompt}).insert()
    reply = _process_with_mcp(prompt, session, user, model)
    frappe.get_doc({"doctype": "AI Chat Message", "user": user, "session_id": session, "role": "assistant", "content": reply}).insert()
    return {"response": reply, "session": session}


def _process_with_mcp(prompt, session, user, model):
    """Process prompt using MCP tools."""
    pl = prompt.lower().strip()
    mcp = FrappeMCP()

    # Check for illegal operations first
    illegal = check_illegal_operation(prompt)
    if illegal:
        return "🚫 " + illegal

    # Confirm / submit
    if pl in ["submit", "finalize", "jama", "jama kar"]:
        return _handle_submit(session, user, mcp)

    # Cancel / reject
    if pl in ["no", "nah", "nahi", "na", "cancel", "radh kar", "delete"]:
        return _handle_cancel(session, user, mcp)

    # Yes / confirm
    if pl in ["yes", "yeah", "haan", "han", "ok", "okay", "sure", "bilkul", "thik hai", "confirm"]:
        return _handle_confirm(session, user, mcp, prompt)

    # Guided conversation answer
    _g_state = load_guided(session, user)
    if _g_state and _g_state.get("pending_field"):
        return guided_answer(session, user, prompt)

    # Active guided session with new data
    if _g_state and _g_state.get("doctype"):
        _g_dt = _g_state.get("doctype")
        _g_data = dict(_g_state.get("data") or {})
        _g_new = _extract_fields_for(_g_dt, prompt)
        _g_changed = False
        for _k, _v in _g_new.items():
            if _v not in (None, "") and _g_data.get(_k) != _v:
                _g_data[_k] = _v
                _g_changed = True
        if _g_changed:
            return guided_start(session, user, _g_dt, _g_data)
        return guided_ready_again(session, user)

    # Report detection
    report = detect_report(prompt)
    if report:
        return _handle_report(report, mcp)

    # Intent detection
    intent = detect_intent(prompt)
    if intent:
        doctype, action = intent
        if action == "create":
            return _handle_create_intent(doctype, prompt, session, user, mcp)
        elif action == "view":
            return _handle_view_intent(prompt, mcp)
        elif action == "print":
            return handle_print(prompt, mcp)
        elif action == "report":
            return _handle_report((None, {"doctype": doctype, "label": doctype + " Report"}), mcp)

    # Shipment patterns — parse first, preview, require explicit confirmation
    # before any master data (supplier/items) or receipt is created.
    if re.search(r"\b(arriv|aa gaya|aagya|mil gaya|resiv|reciv|shipment)", pl):
        result = handle_shipment_nl(prompt, mcp)
        if not result.get("ok"):
            return result.get("message", result.get("error", "Could not record shipment."))
        data = result.get("data") or {}
        preview = []
        preview.append("- Supplier: " + (data.get("supplier") or "?"))
        preview.append("- Vehicle: " + (data.get("vehicle_no") or "n/a"))
        for it in data.get("items", []):
            preview.append("- %s x %s" % (it.get("qty", "?"),
                                          it.get("item_code") or it.get("item_name")))
        preview.append("- Warehouse: " + (data.get("warehouse") or "default"))
        # Persist the parsed-but-unconfirmed intent as an auditable draft so the
        # confirmation step (user says "yes") finalizes it through the same
        # draft/confirm/audit path used by the workflow endpoint.
        draft_id = save_shipment_draft(session, user, data)
        if not draft_id:
            return "❌ Could not save shipment draft. Please try again."
        return ("📦 Shipment parsed. Please review:\n" + "\n".join(preview) +
                "\n\nReply **yes** to record this receipt, or tell me what to change.")

    # Stock issue patterns
    if re.search(r"\b(issue|transfer|jari|dena)\b.*\b(stock|maal|saman|item)\b", pl):
        result = handle_issue_nl(prompt, mcp)
        if result.get("ok"):
            return f"✅ Stock Issue: {result.get('name')}\n{result.get('next', '')}"
        return result.get("message", result.get("error", "Could not issue stock."))

    # Count queries
    count_reply = handle_count_query(prompt, mcp)
    if count_reply:
        return count_reply

    # Fall back to LLM
    return _fallback_to_llm(prompt, session, user, model)


def _handle_submit(session, user, mcp):
    from erp_ai.rbac import check_permission
    _doc_msg = frappe.db.get_all("AI Chat Message",
        filters={"session_id": session or "", "role": "assistant", "content": ["like", "[DOC_CREATED]%"], "user": user},
        fields=["content"], order_by="creation desc", limit=1)
    if _doc_msg:
        _parts = _doc_msg[0].content.replace("[DOC_CREATED]|", "").split("|")
        if len(_parts) >= 2:
            err = check_permission(user, _parts[0], "submit")
            if err:
                return "🚫 " + err
            _result = mcp.call_tool("submit_document", {"doctype": _parts[0], "name": _parts[1]})
            if "error" in _result:
                return "❌ Could not submit: " + _result["error"]
            return f"✅ {_parts[0]} {_parts[1]} submitted!"
    return "Nothing to submit. Create something first."


def _handle_cancel(session, user, mcp):
    clear_guided(session, user)
    # Discard any pending AI Assistant Action draft that has not been confirmed.
    _draft = get_draft(session)
    if _draft and isinstance(_draft, dict):
        frappe.get_doc({"doctype": "AI Chat Message", "user": user, "session_id": session or "",
                        "role": "user", "content": "[DRAFT_CLEARED]"}).insert()
        # No direct commit here — framework commits at the request boundary
        return "❌ %s draft cancelled. What else?" % _draft.get("target_doctype", "draft")
    return "🛑 Cancelled. Is there anything else?"


def _handle_confirm(session, user, mcp, prompt):
    # Conversational "yes/confirm" now goes through the centralized,
    # auditable draft engine. Any pending shipment preview that was created via
    # the workflow endpoint is already stored as an AI Assistant Action draft,
    # not as a chat marker, so it is handled by the same confirm path below.
    _g_state = load_guided(session, user)
    if _g_state and _g_state.get("pending_field"):
        if _g_state.get("pending_field") in OPTIONAL_FOLLOWUPS.get(_g_state.get("doctype"), []):
            return guided_answer(session, user, "skip")
        return guided_answer(session, user, prompt)
    _result = confirm_draft(session=session, user=user)
    if not isinstance(_result, dict):
        return "❌ Draft confirmation returned an unexpected response."
    if "error" in _result:
        return "❌ Could not confirm: " + _result["error"]
    if "name" not in _result:
        return "❌ Draft confirmed, but no result returned."
    _doctype = _result.get("doctype", "Document")
    _name = _result.get("name", "?")
    _print = _result.get("print_url", "")
    _print_hint = "\n🖨️ Print: " + _print if _print else ""
    frappe.get_doc({"doctype": "AI Chat Message", "user": user, "session_id": session, "role": "assistant",
                    "content": "[DOC_CREATED]|" + _doctype + "|" + _name}).insert()
    # confirm_draft committed at its own workflow boundary — no direct commit here
    return "✅ {_doctype} {_name} created!{_print_hint}\nSay 'submit' to finalize.".format(
        _doctype=_doctype, _name=_name, _print_hint=_print_hint)


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
    from erp_ai.rbac import check_permission
    # Try to extract doctype from the prompt for RBAC
    _doc_match = re.search(r"\b(show|view|details|dekho|dikhhao)\s+(?:of\s+)?(?:item\s+|invoice\s+|customer\s+)?([A-Z][A-Z0-9\-]{2,20})", prompt, re.I)
    if _doc_match:
        _doc_name = _doc_match.group(2).upper()
        for _dt in ["Item", "Customer", "Supplier", "Sales Invoice", "Purchase Invoice"]:
            if frappe.db.exists(_dt, _doc_name):
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


def _fallback_to_llm(prompt, session, user, model):
    system = (
        f"You are the AI assistant of SPI's ERPNext system. "
        f"You can create documents, check stock, answer questions about ERP data. "
        f"The user is {frappe.utils.get_fullname(user)} ({user}). Be helpful and concise."
    )
    return ask_ollama(system + "\n\nUser: " + prompt + "\nAssistant:", model)


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
        "warehouse": data.get("warehouse", ""),
        "remarks": data.get("remarks", ""),
    }

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
    from erp_ai.draft_workflow import confirm_draft

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

    This is the public cancel boundary. It delegates to the existing
    ``erp_ai.draft_workflow`` cancel path when present; otherwise it falls back
    to a minimal, safe, user-bound cancellation that only writes through the
    auditable action DocType.
    """
    import frappe

    try:
        from erp_ai.draft_workflow import cancel_draft

        cancel_result = cancel_draft(
            session=frappe.session.session_id,
            action_id=action_id,
            user=user,
        )
        if isinstance(cancel_result, dict):
            return cancel_result
    except Exception:
        pass

    # Fallback: minimal user-bound cancellation via the action DocType only.

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
    """Create the AI Assistant Hub workspace.

    Requires System Manager role — workspaces and pages are privileged setup objects.
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Only System Manager can set up the workspace", frappe.PermissionError)
    try:
        if not frappe.db.exists("Page", "ai-assistant"):
            frappe.get_doc({"doctype": "Page", "page_name": "ai-assistant", "module": "ERP AI", "standard": "Yes", "title": "AI Assistant"}).insert()
        if frappe.db.exists("Workspace", {"label": "AI Assistant Hub"}):
            ws = frappe.get_doc("Workspace", "AI Assistant Hub")
            ws.content = json.dumps([{"id": "ai_welcome", "type": "header", "data": {"text": "AI Assistant Hub", "col": 12}}])
            ws.save()
            frappe.db.commit()
            return ws.name
        ws = frappe.new_doc("Workspace")
        ws.label = "AI Assistant Hub"
        ws.title = "AI Assistant Hub"
        ws.module = "ERP AI"
        ws.public = 1
        ws.insert()
        frappe.db.commit()
        return ws.name
    except Exception:
        import traceback
        traceback.print_exc()
        return None


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
    from erp_ai.diagnostics import health_check
    return health_check()


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
            "duplication_check": True,
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
    from erp_ai.safety import check_illegal_operation

    if not file_url:
        frappe.throw("file_url is required")
    # Only operate on Frappe-managed files
    if not file_url.startswith(("/files/", "/private/files/")):
        return {"error": "Only Frappe-managed uploads are supported (use a /files/ URL)"}
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
