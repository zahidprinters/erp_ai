import json

import base64
import os
import re
import subprocess

import frappe
import requests
from frappe.utils import fmt_money

from erp_ai.mcp.server import FrappeMCP
from erp_ai.knowledge.erpnext_kb import get_knowledge_excerpt, get_kb_summary
from erp_ai.draft_workflow import (detect_intent, extract_item_fields, extract_invoice_fields,
    extract_party_fields, get_missing_fields, get_missing_labels, generate_preview,
    save_draft, get_draft, create_document_from_draft, DOCTYPE_SCHEMAS)
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:1.5b"


def _ollama(prompt, model=None, timeout=180, num_predict=220):
    """Call local Ollama (fast: capped output, warm model)."""
    model = model or frappe.conf.get("ai_model") or DEFAULT_MODEL
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": -1,
            "options": {
                "num_predict": num_predict,
                "temperature": 0.4,
                "num_ctx": 4096,
            },
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return (r.json().get("response") or "").strip()
@frappe.whitelist()
def chat(prompt, model=None):
    """Simple AI chat.

    HTTP: /api/method/erp_ai.api.chat?prompt=Hello
    CLI : bench --site spi.local execute erp_ai.api.chat --kwargs "{'prompt':'Hello'}"
    """
    if not prompt:
        frappe.throw("prompt is required")
    return {"response": _ollama(prompt)}


# ---------------------------------------------------------------------------
# ERP data questions — deterministic router (answers with real numbers)
# ---------------------------------------------------------------------------
_DATA_WORDS = {
    "delivery note": "Delivery Note", "delivery notes": "Delivery Note",
    "purchase receipt": "Purchase Receipt", "purchase receipts": "Purchase Receipt",
    "material request": "Material Request", "material requests": "Material Request",
    "purchase invoice": "Purchase Invoice", "purchase invoices": "Purchase Invoice",
    "sales invoice": "Sales Invoice", "sales invoices": "Sales Invoice",
    "sales order": "Sales Order", "sales orders": "Sales Order",
    "purchase order": "Purchase Order", "purchase orders": "Purchase Order",
    "item group": "Item Group", "item groups": "Item Group",
    "customer group": "Customer Group", "customer groups": "Customer Group",
    "territory": "Territory", "territories": "Territory",
    "warehouse": "Warehouse", "warehouses": "Warehouse",
    "customer": "Customer", "customers": "Customer", "client": "Customer", "clients": "Customer",
    "supplier": "Supplier", "suppliers": "Supplier", "vendor": "Supplier", "vendors": "Supplier",
    "user": "User", "users": "User",
    "item": "Item", "items": "Item", "product": "Item", "products": "Item",
    "lead": "Lead", "leads": "Lead",
    "opportunity": "Opportunity", "opportunities": "Opportunity",
    "employee": "Employee", "employees": "Employee",
    "stock entry": "Stock Entry", "stock entries": "Stock Entry",
}
_COUNT_WORDS = re.compile(r"\b(how many|how much|number of|number of|no\.of|count of|total)\b", re.I)

_DATA_INTENTS = [
    {
        "name": "stock_total",
        "kind": "bin_sum",
        "re": re.compile(
            r"\b(how much stock|total stock|total quantity|total inventory|inventory quantity|"
            r"stock in (the )?inventory|overall stock|stock we have)\b",
            re.I,
        ),
    },
    {
        "name": "item_count",
        "kind": "count",
        "re": re.compile(
            r"\b(how many items|number of items|items? in (the )?inventory|total items|"
            r"item count|how many products|number of products)\b",
            re.I,
        ),
        "dt": "Item", "filters": {"disabled": 0}, "label": "active items",
    },
    {
        "name": "so_open",
        "kind": "count",
        "re": re.compile(
            r"\b((open|pending|unfulfilled) sales orders?|(how many|number of) (open|pending) sales orders?)\b",
            re.I,
        ),
        "dt": "Sales Order", "filters": {"docstatus": 1}, "label": "open (submitted) sales orders",
    },
    {
        "name": "si_unpaid",
        "kind": "si_unpaid",
        "re": re.compile(r"\b(unpaid|outstanding|pending|overdue) invoices?\b", re.I),
    },
]


def _num(v):
    try:
        v = float(v)
        if v == int(v):
            return f"{int(v):,}"
        return f"{v:,.2f}"
    except Exception:
        return str(v)


def _plural(n, word):
    """Best-effort singular for n == 1 (assumes plural form passed in)."""
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
            n = frappe.db.sql("SELECT COALESCE(SUM(actual_qty),0) FROM `tabBin`")[0][0]
            return {"ok": True, "answer": f"Total stock across all warehouses: {_num(n)} units."}
        if kind == "si_unpaid":
            if not (frappe.has_permission("Sales Invoice", "read") and frappe.has_permission("Sales Invoice", "read")):
                return {"ok": False}
            cnt = frappe.db.count(
                "Sales Invoice", {"docstatus": 1, "outstanding_amount": [">", 0]}
            )
            amt = frappe.db.sql(
                "SELECT COALESCE(SUM(outstanding_amount),0) FROM `tabSales Invoice` "
                "WHERE docstatus=1 AND outstanding_amount>0"
            )[0][0]
            try:
                cur = frappe.db.get_single_value("Global Defaults", "default_currency")
                money = fmt_money(amt, currency=cur)
            except Exception:
                money = _num(amt)
            return {"ok": True, "answer": f"{cnt:,} unpaid sales {_plural(cnt, 'invoices')}, total outstanding: {money}."}
        dt, label = it["dt"], it.get("label", it["dt"])
        n = _count(dt, it.get("filters"))
        if n is None:
            return {"ok": False}
        return {"ok": True, "answer": f"We have {n:,} {_plural(n, label)} in the system."}
    except Exception:
        return {"ok": False}


def _data_answer(prompt):
    if not prompt:
        return {"ok": False}
    q = re.sub(r"[?\\.\\,!;:]", " ", prompt.lower())
    for it in _DATA_INTENTS:
        if it["re"].search(q):
            return _run_intent(it)
    if _COUNT_WORDS.search(q):
        for phrase, dt in sorted(_DATA_WORDS.items(), key=lambda kv: -len(kv[0])):
            if re.search(r"(?<!\\w)" + re.escape(phrase) + r"(?!\\w)", q):
                n = _count(dt)
                if n is not None:
                    return {"ok": True, "answer": f"There {'is' if n == 1 else 'are'} {n:,} {_plural(n, phrase)} in the system."}
    return {"ok": False}


@frappe.whitelist()
def data_answer(prompt):
    """Deterministic ERP data answers:(counts, quantities, totals).

    Great for questions likes 'how many items', 'total stock', 'unpaid invoices'.
    Returns {"ok": true, "answer": "..."} or {"ok": false} (fallback to AI_.
    """
    return _data_answer(prompt)


def _resolve(doctype, name):
    """Exact lookup first, then case/partial-tolerant title search."""
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
            hits = frappe.get_all(
                doctype,
                filters={f: ["like", f"%{name}%"]},
                limit_page_length=1,
                pluck="name",
            )
            if hits:
                return frappe.get_doc(doctype, hits[0])
        raise


@frappe.whitelist()
def summarize_doc(doctype, name):
    """AI summary of any ERPNext document in 3 bullet points."""
    doc = _resolve(doctype, name)
    doc.check_permission("read")
    fields = {
        df.fieldname: getattr(doc, df.fieldname)
        for df in doc.meta.fields
        if getattr(doc, df.fieldname, None) not in (None, "")
    }
    data = json.dumps(fields, default=str)[:6000]
    prompt = (
        f"You are an ERP assistant. Summarize this ERPNext {doctype} "
        f"in 3 short bullet points:\n{data}"
    )
    return {"summary": _ollama(prompt)}


@frappe.whitelist()
def draft_email(purpose, recipient=None, doctype=None, name=None):
    """Draft a professional email, optionally grounded on an ERPNext document."""
    ctx = ""
    if doctype and name:
        doc = frappe.get_doc(doctype, name)
        doc.check_permission("read")
        ctx = json.dumps(
            {
                df.fieldname: getattr(doc, df.fieldname)
                for df in doc.meta.fields
                if getattr(doc, df.fieldname, None) not in (None, "")
            },
            default=str,
        )[:4000]
    prompt = (
        f"Draft a professional business email. Purpose: {purpose}. "
        f"Recipient: {recipient or 'Customer'}. Context data: {ctx}. "
        "Include a Subject line. Keep it under 150 words."
    )
    return {"email": _ollama(prompt)}


def make_token(user="Administrator"):
    """CLI-only dev helper: (re)generate an API token pair and print it.

    bench --site spi.local execute erp_ai.api.make_token --args "['Administrator']"
    """
    u = frappe.get_doc("User", user)
    u.api_key = frappe.generate_hash(length=15)
    secret = frappe.generate_hash(length=15)
    u.api_secret = secret
    u.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"{u.api_key}:{secret}")


@frappe.whitelist()
def ask(prompt, session=None, model=None):
    """Desk AI assistant with saved memory + Frappe-aware context.

    - Stores every exchange in 'AI Chat Message' (reviewable, auditable)
    - Injects the installed apps list (incl. custom apps) into the context
    - Keeps the last 8 messages of the session as conversation memory
    """
    if not prompt:
        frappe.throw("prompt is required")
    session = session or frappe.generate_hash(length=10)
    user = frappe.session.user

    apps = ", ".join(frappe.get_installed_apps())
    roles = ", ".join(frappe.get_roles())
    fullname = frappe.utils.get_fullname(user)
    system = (
        f"You are the built-in AI assistant of SPI's ERPNext system, running on "
        f"Frappe Framework v15. Installed apps: {apps}. "
        f"The current user is {fullname} ({user}), roles: {roles}. "
        "Adapt your answer to this user: give administrators technical detail; "
        "give operators (accounts, purchase, store, transport, production) short, "
        "simple, step-by-step guidance for their own department. "
        "You help staff use ERPNext, explain Frappe framework concepts, and answer "
        "questions about the company's custom apps. Be brief, practical and accurate. "
        "If asked how many records/items exist and you don't have the exact number, "
        "reply: 'Let me check — try: how many items / how many customers / total stock / unpaid invoices.'"
    )

    history = frappe.get_all(
        "AI Chat Message",
        filters={"session_id": session, "user": user},
        order_by="creation desc",
        limit_page_length=8,
        fields=["role", "content"],
    )
    hist_text = "\n".join(f"{m.role}: {m.content}" for m in reversed(history))[:3000]

    full_prompt = f"{system}\n\nConversation so far:\n{hist_text}\n\nUser: {prompt}\nAssistant:"
    data = _data_answer(prompt)
    if data["ok"]:
        reply = data["answer"]
    else:
        reply = _ollama(full_prompt, model)

    frappe.get_doc(
        {
            "doctype": "AI Chat Message",
            "user": user,
            "session_id": session,
            "role": "user",
            "content": prompt,
        }
    ).insert(ignore_permissions=True)
    frappe.get_doc(
        {
            "doctype": "AI Chat Message",
            "user": user,
            "session_id": session,
            "role": "assistant",
            "content": reply,
        }
    ).insert(ignore_permissions=True)

    return {"response": reply, "session": session}


def _doc_context(doctype, name):
    doc = _resolve(doctype, name)
    doc.check_permission("read")
    return json.dumps(
        {
            df.fieldname: getattr(doc, df.fieldname)
            for df in doc.meta.fields
            if getattr(doc, df.fieldname, None) not in (None, "")
        },
        default=str,
    )[:4000]


@frappe.whitelist()
def ask_with_doc(doctype, name, prompt=None, session=None):
    """Ask the AI about a specific document (used by the "Ask AI" form button).

    The current document's fields are injected into the AI context so it can
    answer about THIS record. History is still per-user.
    """
    session = session or frappe.generate_hash(length=10)
    user = frappe.session.user
    apps = ", ".join(frappe.get_installed_apps())
    roles = ", ".join(frappe.get_roles())
    fullname = frappe.utils.get_fullname(user)

    ctx = _doc_context(doctype, name)
    question = prompt or f"Give me a useful summary and working tips for this {doctype}."

    system = (
        f"You are the built-in AI assistant of SPI's ERPNext (Frappe v15). "
        f"Installed apps: {apps}. User: {fullname} ({user}), roles: {roles}. "
        f"#CURRENT DOCUMENT: {doctype} '{name}'\n{ctx}\n\n"
        f"#USER ASKS (about the document above):\n{question}\nAssistant:"
    )
    reply = _ollama(system)

    frappe.get_doc(
        {
            "doctype": "AI Chat Message",
            "user": user,
            "session_id": session,
            "role": "user",
            "content": f"[{doctype} {name}] {question}",
        }
    ).insert(ignore_permissions=True)
    frappe.get_doc(
        {
            "doctype": "AI Chat Message",
            "user": user,
            "session_id": session,
            "role": "assistant",
            "content": reply,
        }
    ).insert(ignore_permissions=True)

    return {"response": reply, "session": session}


def setup_workspace(**kwargs):
    """Create the AI Assistant Hub workspace with an embedded live chat panel and quick-question links.

    Run: bench --site spi.local execute erp_ai.api.setup_workspace
        Safe to re-run — updates existing workspace in place.
    """
    try:
        _ws_content = json.dumps(
            [
                {
                    "id": "ai_welcome",
                    "type": "header",
                    "data": {"text": "🤖 AI Assistant Hub", "col": 12},
                },
                {
                    "id": "ai_text",
                    "type": "paragraph",
                    "data": {
                        "text": "Ask anything about ERPNext, Frappe framework, your custom apps or ERP data. Chat with your private AI assistant — ask about counts, customers, or how-to steps. Voice input supported (🎤 button in chat).",
                        "col": 12,
                    },
                },
                {
                    "id": "ai_placeholder",
                    "type": "paragraph",
                    "data": {
                        "text": "💬 Live AI chat is loading below... (ask by typing or 🎤 voice)",
                        "col": 12,
                    },
                },
                {
                    "id": "ai_help_header",
                    "type": "header",
                    "data": {"text": "❓ How to use the AI Assistant", "col": 12},
                },
                {
                    "id": "ai_help_basics",
                    "type": "paragraph",
                    "data": {
                        "text": "📊 DATA QUERIES — ask anything about your ERP data: \u2018How many items?\u2019 \u2022 \u2018How many customers?\u2019 \u2022 \u2018Total stock?\u2019 \u2022 \u2018Unpaid invoices?\u2019 \u2022 \u2018Show me all items\u2019 \u2022 \u2018Search for pump springs\u2019 — the AI answers with REAL numbers from your database.",
                        "col": 12,
                    },
                },
                {
                    "id": "ai_help_workflows",
                    "type": "paragraph",
                    "data": {
                        "text": "📦 WORKFLOWS — create documents in plain language: \u2018Spring shipment arrived from ABC Traders, vehicle LEA-4521, 500 pcs pump springs\u2019 (records goods receipt) \u2022 \u2018Issue 10 pump springs to Engr Ali in Production\u2019 (stock issue) \u2022 \u2018Make invoice for ABC Traders, 2 pump springs @ 500\u2019 (sales invoice + print link) \u2022 \u2018Create item named Steel Rod price 100\u2019 \u2022 \u2018Create customer named XYZ Corp\u2019. The AI asks for any missing details, creates documents as DRAFT for your review, and gives print/PDF links.",
                        "col": 12,
                    },
                },
                {
                    "id": "ai_help_setup",
                    "type": "paragraph",
                    "data": {
                        "text": "🛠 SETUP & GUIDANCE — ask how-to questions: \u2018How do I set up a new warehouse?\u2019 \u2022 \u2018What do I need to make a sales invoice?\u2019 \u2022 \u2018How does the manufacturing BOM work?\u2019 \u2022 \u2018Help me set up a new ERP system\u2019 \u2022 \u2018What taxes apply in Pakistan?\u2019 — full ERPNext knowledge built in.",
                        "col": 12,
                    },
                },
                {
                    "id": "ai_help_voice",
                    "type": "paragraph",
                    "data": {
                        "text": "🎤 VOICE — click 🎤 in the chat, speak, stop — your words are typed into the input (needs HTTPS). 🔊/🔇 button toggles spoken answers (Piper TTS, English & Urdu). Voice works on https://spi.local or localhost.",
                        "col": 12,
                    },
                },
                {
                    "id": "ai_help_docs",
                    "type": "paragraph",
                    "data": {
                        "text": "📚 FULL DOCS: see README.md in the erp_ai app folder for complete API reference, setup, troubleshooting and debugging guide.",
                        "col": 12,
                    },
                },
            ]
        )

        # Ensure the AI Assistant page exists
        if not frappe.db.exists("Page", "ai-assistant"):
            frappe.get_doc({
                "doctype": "Page",
                "page_name": "ai-assistant",
                "module": "ERP AI",
                "standard": "Yes",
                "title": "AI Assistant",
            }).insert(ignore_permissions=True)
            print("Page ai-assistant created")

        # Create or update the workspace
        if frappe.db.exists("Workspace", {"label": "AI Assistant Hub"}):
            ws = frappe.get_doc("Workspace", "AI Assistant Hub")
            ws.content = _ws_content
            ws.label_orientation = "Left"
            # re-add shortcut if missing
            if not ws.shortcuts or not any(s.link_to == "ai-assistant" for s in ws.shortcuts):
                ws.append("shortcuts", {"label": "Open AI Chat", "link_to": "ai-assistant", "type": "Page"})
            ws.save(ignore_permissions=True)
            frappe.db.commit()
            print("Workspace updated with embedded chat")
            return ws.name

        ws = frappe.new_doc("Workspace")
        ws.label = "AI Assistant Hub"
        ws.title = "AI Assistant Hub"
        ws.module = "ERP AI"
        ws.public = 1
        ws.sequence_id = 1
        ws.label_orientation = "Left"
        ws.content = _ws_content
        ws.append("shortcuts", {"label": "Open AI Chat", "link_to": "ai-assistant", "type": "Page"})
        ws.insert(ignore_permissions=True)
        frappe.db.commit()
        print("Workspace created:", ws.name)
        return ws.name
    except Exception:
        import traceback
        traceback.print_exc()
        return None




def _ai_home():
    """Resolve the voice-stack runtime root, preferring an existing whisper build.

    The bench/gunicorn worker may not share the shell's $HOME, so try several
    candidate paths and return the first that actually contains whisper-cli.
    """
    env = os.environ.get("AI_HOME")
    cands = []
    if env:
        cands.append(env)
    cands += [
        os.path.join(os.path.expanduser("~"), "ai"),
        "/home/erpnext/ai",
    ]
    for p in cands:
        if p and os.path.exists(os.path.join(p, "whisper.cpp", "build", "bin", "whisper-cli")):
            return p
    return cands[0] or "/home/erpnext/ai"


@frappe.whitelist()
def voice_to_text(audio, fmt="webm"):
    """Transcribe a short browser-recorded clip with whisper.cpp.

    Expects base64-encoded audio bytes (WebM/OGG/WAV). Converts to 16kHz WAV
    with ffmpeg, runs whisper tiny, returns the transcript text.
    """
    if not audio:
        frappe.throw("No audio received")
    try:
        raw = base64.b64decode(audio)
    except Exception:
        frappe.throw("Invalid audio payload")

    home = _ai_home()
    tmp = f"{home}/tmp"
    os.makedirs(tmp, exist_ok=True)
    raw_path = f"{tmp}/voice_in.{fmt}"
    wav_path = f"{tmp}/voice_out.wav"
    with open(raw_path, "wb") as f:
        f.write(raw)

    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path],
        capture_output=True,
    )
    whisper = f"{home}/whisper.cpp/build/bin/whisper-cli"
    model = f"{home}/models/ggml-tiny.bin"
    if not (os.path.exists(whisper) and os.path.exists(model)):
        frappe.throw("Whisper runtime not provisioned — run voice/setup_voice.sh")
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = os.path.dirname(whisper) + ":" + env.get("LD_LIBRARY_PATH", "")
    p = subprocess.run(
        [whisper, "-m", model, "-f", wav_path, "-nt", "-np"],
        capture_output=True,
        text=True,
        env=env,
    )
    text = " ".join(l.strip() for l in p.stdout.splitlines() if l.strip()).strip()
    return {"text": text or "(no speech detected)"}





@frappe.whitelist()
def ask_v2(prompt, session=None, model=None):
    """Enhanced AI assistant with MCP tool access.
    
    Can:
    - Answer questions about ERP data (counts, lists, specific records)
    - Create new documents (items, invoices, customers, etc.)
    - Update existing documents
    - Print documents (get PDF URL)
    - Search across documents
    - Understand natural language and determine intent
    """
    if not prompt:
        frappe.throw("prompt is required")
    session = session or frappe.generate_hash(length=10)
    user = frappe.session.user
    
    # Save user message
    frappe.get_doc({
        "doctype": "AI Chat Message",
        "user": user,
        "session_id": session,
        "role": "user",
        "content": prompt,
    }).insert(ignore_permissions=True)
    
    # Process with MCP
    reply = _process_with_mcp(prompt, session, user, model)
    
    # Save assistant response
    frappe.get_doc({
        "doctype": "AI Chat Message",
        "user": user,
        "session_id": session,
        "role": "assistant",
        "content": reply,
    }).insert(ignore_permissions=True)
    
    return {"response": reply, "session": session}


def _process_with_mcp(prompt, session, user, model):
    """Process prompt using MCP tools - intent detection + real DB actions."""
    pl = prompt.lower().strip()
    import re as _re
    mcp = FrappeMCP()

    # ---------- CONFIRM / YES (proceed with pending action) ----------
    if pl in ['submit', 'finalize', 'jama kar', 'jama', 'submit kar', 'final']:
        # ===== SUBMIT a previously created document =====
        _doc_msg = frappe.db.get_all("AI Chat Message",
            filters={"session_id": session or "", "role": "assistant", "content": ["like", "[DOC_CREATED]%"]},
            fields=["content"], order_by="creation desc", limit=1)
        if _doc_msg:
            _parts = _doc_msg[0].content.replace("[DOC_CREATED]|", "").split("|")
            if len(_parts) >= 2:
                _doctype = _parts[0]
                _docname = _parts[1]
                _result = mcp.call_tool("submit_document", {"doctype": _doctype, "name": _docname})
                if "error" in _result:
                    return f"❌ Could not submit: {_result['error']}"
                return f"✅ {_doctype} **{_docname}** submitted successfully!"
        return "Nothing to submit. Create something first."

    if pl in ['no', 'nah', 'nahi', 'na', 'cancel', 'radh kar', 'radh', 'delete', 'mitaao']:
        # ===== REJECT: Clear active draft =====
        _doctype, _ = get_draft(session)
        if _doctype:
            # Clear the draft by inserting a marker
            frappe.get_doc({
                "doctype": "AI Chat Message", "user": frappe.session.user,
                "session_id": session or "", "role": "user",
                "content": "[DRAFT_CLEARED]"
            }).insert(ignore_permissions=True)
            frappe.db.commit()
            return f"❌ {_doctype} draft cancelled. What would you like to do instead?"
        return "Nothing to cancel. What would you like to do?"

    if pl in ['yes', 'yeah', 'yep', 'haan', 'han', 'ok', 'okay', 'sure', 'bilkul', 'thik hai', 'confirm']:
        # ===== DRAFT WORKFLOW: Confirm & create document =====
        _doctype, _draft_data = get_draft(session)
        if _doctype:
            _result = create_document_from_draft(_doctype, _draft_data, mcp)
            if "error" in _result:
                if _result.get("duplicate"):
                    return f"⚠️ {_result['error']}. Use a different name."
                return f"❌ Could not create {_doctype}: {_result['error']}"
            # Success!
            _name = _result.get("name", "?")
            _extra = ""
            if _result.get("stock_entry"):
                _extra = f" + Stock Entry {_result['stock_entry']} (DRAFT)"
            _print = _result.get("print_url", "")
            _print_hint = f"\n🖨️ Print: {_print}" if _print else ""
            # Store doc reference for submit handler
            frappe.get_doc({
                "doctype": "AI Chat Message", "user": frappe.session.user,
                "session_id": session or "", "role": "assistant",
                "content": f"[DOC_CREATED]|{_doctype}|{_name}"
            }).insert(ignore_permissions=True)
            frappe.db.commit()
            return (f"✅ {_doctype} created: **{_name}** (Draft){_extra}\n"
                    f"   Say '**submit**' to finalize, or tell me what to change.{_print_hint}")
        # ===== LEGACY: Pending item update (price/stock) =====
        _pending = frappe.db.get_all("AI Chat Message",
            filters={"session_id": session or "", "role": "user", "content": ["like", "[PENDING]%"]},
            fields=["content"], order_by="creation desc", limit=1)
        if _pending:
            _parts = _pending[0].content.replace("[PENDING]|", "").split("|")
            if len(_parts) >= 3:
                _item_code = _parts[0].strip()
                _price_val = _parts[1].strip()
                _qty_val = _parts[2].strip()
                _item = frappe.db.get_value("Item", _item_code, ["name", "item_name", "standard_rate"], as_dict=True)
                if _item:
                    _actions_done = []
                    if _price_val and _price_val != "0":
                        _new_rate = float(_price_val)
                        if _new_rate != _item.standard_rate:
                            frappe.db.set_value("Item", _item.name, "standard_rate", _new_rate)
                            _actions_done.append(f"price updated to {_new_rate:,.0f}")
                    if _qty_val and _qty_val != "0":
                        _add_qty = float(_qty_val)
                        _t_wh = "Stores - SPI" if frappe.db.exists("Warehouse", "Stores - SPI") else "Stores"
                        _se = mcp.call_tool("create_document", {"doctype": "Stock Entry", "data": {
                            "doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
                            "company": frappe.defaults.get_global_default("company"),
                            "items": [{"item_code": _item.name, "qty": _add_qty, "t_warehouse": _t_wh, "basic_rate": _item.standard_rate}]}})
                        if "error" not in _se:
                            _actions_done.append(f"stock +{_add_qty:,.0f} added (Stock Entry {_se.get('name')} - DRAFT)")
                    if _actions_done:
                        frappe.db.commit()
                        return f"✅ Updated {_item.item_name}: {', '.join(_actions_done)}."
                    else:
                        return f"No changes needed for {_item.item_name}."
        return "Nothing to confirm. Please tell me what you'd like to do."

    # ---------- MODIFY a draft (if active) ----------
    _existing_doctype, _existing_draft = get_draft(session)
    if _existing_doctype:
        # User is providing more info or modifying the active draft
        _updated, _changed = False, False
        # Try to extract updates based on doctype
        if _existing_doctype == "Item":
            _new_data = extract_item_fields(prompt)
            for k, v in _new_data.items():
                if v is not None and v != "" and v != 0:
                    _existing_draft[k] = v
                    _changed = True
        elif _existing_doctype in ("Sales Invoice", "Purchase Invoice"):
            _new_data = extract_invoice_fields(prompt)
            for k, v in _new_data.items():
                if v is not None and v != "":
                    _existing_draft[k] = v
                    _changed = True
        elif _existing_doctype == "Customer":
            _new_data = extract_party_fields(prompt, "customer")
            for k, v in _new_data.items():
                if v is not None and v != "":
                    _existing_draft[k] = v
                    _changed = True
        elif _existing_doctype == "Supplier":
            _new_data = extract_party_fields(prompt, "supplier")
            for k, v in _new_data.items():
                if v is not None and v != "":
                    _existing_draft[k] = v
                    _changed = True
        if _changed:
            save_draft(session, _existing_doctype, _existing_draft)
            _missing = get_missing_fields(_existing_doctype, _existing_draft)
            _preview = generate_preview(_existing_doctype, _existing_draft)
            if _missing:
                _labels = get_missing_labels(_existing_doctype, _missing)
                return (f"{_preview}\n\n"
                        f"📝 Still need: {', '.join(_labels)}\n"
                        f"   Or say '**confirm**' to save with what we have.")
            return (f"{_preview}\n\n"
                    f"✅ All details ready! Say '**confirm**' to save, or tell me what to change.")
        # No changes detected — fall through to new intent detection

    # ---------- NEW INTENT DETECTION (with draft workflow) ----------
    _intent = detect_intent(prompt)
    if _intent:
        # Extract fields based on intent
        _data = {}
        if _intent == "Item":
            _data = extract_item_fields(prompt)
        elif _intent in ("Sales Invoice", "Purchase Invoice"):
            _invoice_data = extract_invoice_fields(prompt)
            if _intent == "Purchase Invoice" and "customer" in _invoice_data:
                _invoice_data["supplier"] = _invoice_data.pop("customer")
            _data = _invoice_data
        elif _intent == "Customer":
            _data = extract_party_fields(prompt, "customer")
        elif _intent == "Supplier":
            _data = extract_party_fields(prompt, "supplier")
        # Check for missing required fields
        _missing = get_missing_fields(_intent, _data)
        # Save draft
        save_draft(session, _intent, _data)
        # Show preview + ask for missing
        _preview = generate_preview(_intent, _data)
        if _missing:
            _labels = get_missing_labels(_intent, _missing)
            return (f"{_preview}\n\n"
                    f"📝 I need: {', '.join(_labels)}\n"
                    f"   Example: {DOCTYPE_SCHEMAS.get(_intent, {}).get('examples', '')}\n"
                    f"   Or say '**confirm**' to save with defaults.")
        return (f"{_preview}\n\n"
                f"✅ Ready! Say '**confirm**' to save, or tell me what to change.")

    # ---------- CREATE INTENTS (legacy fallback → draft workflow) ----------
    # These patterns catch cases the new intent detector might miss
    _add_price = _re.search(r'\b(add|create|banao|banaiye)\b.{1,40}?\b(price|rate|keemat)\b', pl)
    _add_stock = _re.search(r'\b(add|create|banao|banaiye)\b.{1,40}?\b(received|reciv|resiv|stock|qty|quantity|unit|milay|mile|aa gaya|aagya)\b', pl)
    if any(kw in pl for kw in ["create item", "add item", "add a item", "add a itm", "add a new item", "new item", "new itm",
                                "item banaiye", "item create", "item add", "item banao",
                                "nyaa item", "item shuru"]) or _re.search(r'\b(add|create|nyaa banao)\b.*\b(item|product|itm)\b', pl) or _add_price or _add_stock:
        # Use draft workflow for items too
        _data = extract_item_fields(prompt)
        if _data.get("item_name"):
            save_draft(session, "Item", _data)
            _missing = get_missing_fields("Item", _data)
            _preview = generate_preview("Item", _data)
            if _missing:
                _labels = get_missing_labels("Item", _missing)
                return (f"{_preview}\n\n📝 I need: {', '.join(_labels)}\n   Or say '**confirm**' to save with defaults.")
            return (f"{_preview}\n\n✅ Ready! Say '**confirm**' to save, or tell me what to change.")
        return ("To create an item I need at least a name. Please reply with: "
                "'Add item <name>, group <group>, price <price>, opening stock <qty>'.")

    if any(kw in pl for kw in ["create invoice", "add invoice", "add a invoice", "new invoice",
                                "invoice banaiye", "bill banaiye", "invoice banao", "invoice create"]):
        _data = extract_invoice_fields(prompt)
        save_draft(session, "Sales Invoice", _data)
        _missing = get_missing_fields("Sales Invoice", _data)
        _preview = generate_preview("Sales Invoice", _data)
        if _missing:
            _labels = get_missing_labels("Sales Invoice", _missing)
            return (f"{_preview}\n\n📝 I need: {', '.join(_labels)}\n   Example: 'for ABC Traders, 2 pump springs @ 500'")
        return (f"{_preview}\n\n✅ Ready! Say '**confirm**' to save, or tell me what to change.")

    if any(kw in pl for kw in ["create customer", "add customer", "new customer", "customer banaiye",
                                "client banaiye", "customer banao", "customer add"]):
        _data = extract_party_fields(prompt, "customer")
        save_draft(session, "Customer", _data)
        _missing = get_missing_fields("Customer", _data)
        _preview = generate_preview("Customer", _data)
        if _missing:
            _labels = get_missing_labels("Customer", _missing)
            return (f"{_preview}\n\n📝 I need: {', '.join(_labels)}")
        return (f"{_preview}\n\n✅ Ready! Say '**confirm**' to save, or tell me what to change.")

    if any(kw in pl for kw in ["create supplier", "add supplier", "new supplier", "supplier banaiye",
                                "vendor banaiye", "supplier banao", "supplier add"]):
        _data = extract_party_fields(prompt, "supplier")
        save_draft(session, "Supplier", _data)
        _missing = get_missing_fields("Supplier", _data)
        _preview = generate_preview("Supplier", _data)
        if _missing:
            _labels = get_missing_labels("Supplier", _missing)
            return (f"{_preview}\n\n📝 I need: {', '.join(_labels)}")
        return (f"{_preview}\n\n✅ Ready! Say '**confirm**' to save, or tell me what to change.")

    # ---------- VIEW DOCUMENT DETAILS ----------
    if _re.search(r'\b(show|view|details|info|dekho|dikhhao|kya hai)\b', pl):
        # Try to find a document name
        _doc_match = _re.search(r'\b(show|view|details|info|dekho|dikhhao)\s+(?:of\s+)?(?:item\s+|invoice\s+|customer\s+|supplier\s+)?([A-Z][A-Z0-9\-]{2,20})', pl, re.I)
        if _doc_match:
            _doc_name = _doc_match.group(2).upper()
            # Try to find in each doctype
            for _dt in ["Item", "Customer", "Supplier", "Sales Invoice", "Purchase Invoice", "Stock Entry"]:
                if frappe.db.exists(_dt, _doc_name):
                    _doc = mcp.call_tool("get_document", {"doctype": _dt, "name": _doc_name})
                    if "error" not in _doc:
                        return _format_document_view(_dt, _doc)
            # Try partial match
            for _dt in ["Item", "Customer", "Supplier", "Sales Invoice", "Purchase Invoice"]:
                _found = mcp.call_tool("query_doctype", {"doctype": _dt, "filters": {"name": ["like", f"%{_doc_name}%"]}, "fields": ["name"], "limit": 1})
                if _found.get("count", 0) > 0:
                    _name = _found["records"][0]["name"]
                    _doc = mcp.call_tool("get_document", {"doctype": _dt, "name": _name})
                    if "error" not in _doc:
                        return _format_document_view(_dt, _doc)
            return f"Document '{_doc_name}' not found. Check the name and try again."

    # ---------- CHECK STOCK ----------
    if _re.search(r'\b(stock|qty|quantity|how many|kitne|kitna|mila|haye)\b', pl):
        _item_match = _re.search(r'\b(stock|qty|quantity|how many|kitne|kitna)\s+(?:of\s+)?([A-Za-z][A-Za-z0-9 ]{2,40}?)(?:\?|\s|$)', pl, re.I)
        if _item_match:
            _item_name = _item_match.group(2).strip()
            _found = mcp.call_tool("search_documents", {"query": _item_name, "doctype": "Item", "limit": 3})
            _results = _found.get("results", [])
            if _results:
                _item_code = _results[0]["name"]
                _item = mcp.call_tool("query_doctype", {"doctype": "Item", "filters": {"name": _item_code}, "fields": ["item_name", "item_group", "standard_rate"], "limit": 1})
                if _item.get("count", 0) > 0:
                    _item_info = _item["records"][0]
                    _bin = mcp.call_tool("query_doctype", {"doctype": "Bin", "filters": {"item_code": _item_code}, "fields": ["warehouse", "actual_qty"], "limit": 20})
                    _bins = _bin.get("records", [])
                    _total = sum(b.get("actual_qty", 0) or 0 for b in _bins)
                    _lines = [f"📦 {_item_info.get('item_name', _item_code)} | Stock: **{_total:,.0f}** | Rate: {_item_info.get('standard_rate', 0):,.0f}"]
                    if _bins:
                        _lines.append("  Warehouses:")
                        for b in _bins:
                            _lines.append(f"    - {b.get('warehouse', '')}: {b.get('actual_qty', 0):,.0f}")
                    return "\n".join(_lines)
            return f"Item '{_item_name}' not found. Check the name or add it first."

    # ---------- PRINT ----------
    if _re.search(r'\b(print|pdf|receipt|challan|print kar)[a-z ]*(invoice|bill|delivery|receipt|order|note|voucher)', pl) or \
       (any(kw in pl for kw in ["print", "pdf"]) and any(kw in pl for kw in ["invoice", "bill", "order", "receipt", "delivery note"])):
        return _handle_print(prompt, mcp)

    # ---------- WORKFLOWS ----------
    if any(kw in pl for kw in ["shipment", "goods received", "goods arrived", "consignment",
                                "material received", "samad kii", "aagai", "aagya", "grn",
                                "mal aa gaya", "stock add kar"]):
        return _handle_shipment_nl(prompt, mcp)

    if any(kw in pl for kw in ["issue stock", "issue material", "material issue", "issue to",
                                "transfer stock", "jari karein", "department ko dein", "consume",
                                "issue kar", "nikal kar dein", "stock transfer"]):
        return _handle_issue_nl(prompt, mcp)

    if any(kw in pl for kw in ["make invoice", "banaiye invoice", "generate invoice", "invoice bana",
                                "bill customer", "customer ko bill kar", "bill banao"]):
        return _handle_invoice_nl(prompt, mcp)

    # ---------- COUNT QUERIES ----------
    if any(kw in pl for kw in ["how many", "count of", "number of", "kitne", "kitna", "how much", "total"]):
        return _handle_count_query(prompt, mcp)

    # ---------- CATALOG / LIST QUERIES (BROAD) ----------
    if any(kw in pl for kw in ["what items", "which items", "items we have", "items list",
                                "list items", "list all items", "show items", "show me items",
                                "kya items", "kaun se items", "all items", "item list",
                                "what products", "show all", "list all", "show me all",
                                "what do we have", "what stock", "stock we have",
                                "what customers", "which customers", "what suppliers",
                                "list customers", "list suppliers", "list invoices",
                                "show customers", "show suppliers", "show invoices"]):
        return _handle_list_query(prompt, mcp)

    # ---------- SEARCH ----------
    if any(kw in pl for kw in ["search", "find", "dhundho", "lookup", "dhundo", "search kar"]):
        return _handle_search_query(prompt, mcp)

    # ---------- DATA-y FALLBACK ----------
    # If user asks about specific entities with a question, try data router first
    return _handle_general_query(prompt, session, user, model, mcp)


def _handle_create_item(prompt, mcp, session=None):
    """Extract item details from prompt (EN/UR) and create the item."""
    import re as _re
    p = prompt
    pl = p.lower()

    def grab(patterns, stop='[,.;]|(?:price|rate|group|category|stock|qty|for|in|with|and)'):
        for pat in patterns:
            m = _re.search(pat, p, _re.I)
            if m and m.group(1).strip():
                return m.group(1).strip().rstrip(',').strip()
        return None

    # Guard: require at least one data keyword (price/stock/group/received)
    _has_data = any(kw in pl for kw in ['price', 'rate', 'cost', 'keemat', 'group', 'category',
        'stock', 'qty', 'quantity', 'opening', 'received', 'reciv', 'resiv', 'resived',
        'recd', 'rcvd', 'milay', 'mile', 'unit', 'pcs', 'dozen'])
    if not _has_data:
        return ("To create an item I need at least a name and some details. Please reply with: "
                "'Add item <name>, group <group>, price <price>, opening stock <qty>. "
                "Example: 'Add item Pump Spring, group Raw Material, price 500, opening stock 100'")

    item_name = grab([
        r'(?:named|name|called|ka naam|naam)[:]?\s*([^,;.]+?)(?:\s+(?:group|category|price|rate|cost|keemat|py|stock|qty|quantity|opening|received|reciv|resiv|for|with|in)\b|,|;|$)',
        r'(?:add|create|banao|banaiye)\s*(?:a\s+|new\s+)?(?:item|product)[:\-]?\s*([A-Za-z][A-Za-z0-9 .&\-]{2,40}?)(?=\s+(?:group|category|price|rate|cost|keemat|py|stock|qty|quantity|opening|received|reciv|resiv|for|with|in)\b|,|;|$)',
        # "add wall fans 220v price is 450" -> name = "wall fans 220v"
        r'(?:add|create|banao|banaiye)\s+([A-Za-z][A-Za-z0-9 .&\-]{2,40}?)(?=\s+(?:group|category|price|rate|cost|keemat|py|stock|qty|quantity|opening|received|reciv|resiv|unit|for|with|in)\b|,|;|$)',
        r'(?:item|product)[:]?\s*([A-Za-z][A-Za-z0-9 .&\-]{2,40}?)(?=\s+(?:group|category|price|rate|cost|keemat|py|stock|qty|quantity|opening|received|reciv|resiv|for|with|in)\b|,|;|$)',
        r'\b([A-Za-z][A-Za-z0-9 .&\-]{2,40}(?:fan|relay|switch|cable|pipe|motor|sensor|breaker|contactor|transformer|inverter|rectifier|capacitor|resistor|inductor|diode|transistor|pcb|board|module|assembly|kit|set|pack|box|bag|roll|coil|sheet|plate|bar|tube|hose|belt|gear|coupling|flange|nipple|elbow|tee|reducer|bush|washer|clip|clamp|bracket|frame|cover|cap|plug|socket|pin|jack|connector|terminal|ferrule|lug|hook|ring|chain|sling|shackle|thimble|swage|anchor|bolt|screw|stud|nut|pin|cotter|key|bushing|seal|o-ring|gasket|packing|fitting|duct|tray|conduit|beam|channel|angle|strip|foil|tape|film|insulation|sleeving|boot|grommet|spacer|standoff|receptacle|contact|block|rail|din|busbar|cleat|hanger|saddle|roller|guide|track|conveyor|sprocket|pulley|rack|pinion|actuator|cylinder|servo|stepper|hydraulic|pneumatic|gauge|transmitter|plc|hmi|vfd|fuse|power|supply|ups|battery|charger|converter|filter|reactor|potentiometer|thermocouple|thermistor|load|cell|pressure|flow|level|proximity|photoelectric|encoder|tachometer|vibration|position|limit|pushbutton|selector|pilot|light|horn|siren|stack|beacon|signal|junction|outlet|device|ballast|driver|led|fluorescent|halogen))\b',
    ])

    item_group = grab([
        r'(?:group|category)[:]?\s*([^,;.]+?)(?:\s*(?:price|rate|cost|keemat|py|stock|qty|quantity|opening)\b|$)',
        r'grp[:]?\s*([^,\.]+)',
        r'\b(raw[ -]?material[s]?|finished goods|spare part[s]?|services|products?)\b'
    ]) or "Products"

    price = None
    m = _re.search(r'(?:price|rate|cost|keemat|py)\s*(?:is|=|:|ki hai|hai|he)\s*([0-9][0-9,.]*)', p, _re.I) or \
            _re.search(r'(?:price|rate|cost|keemat|py)[:=]?\s*([0-9][0-9,.]*)', p, _re.I) or \
            _re.search(r'(?:price|rate|cost|keemat|py)\s+([0-9][0-9, ]*)', p, _re.I)
    if m:
        try:
            price = float(m.group(1).replace(',', '').strip())
        except Exception:
            price = None

    qty = None
    m = _re.search(r'(?:qty|quantity|opening|stock|received|reciv|resiv|resived|recd|rcvd|milay|mile|aa gaya|aagya)[:]?\s*([0-9][0-9,.]*)', p, _re.I)
    if not m:
        m = _re.search(r'([0-9][0-9,.]*)\s*(?:units?|pcs?|pcs|dozen|pair|set|pack|box|bag|roll|coil|sheet|plate|bar|tube|piece[s]?)', p, _re.I)
    if m:
        try:
            qty = float(m.group(1).replace(',', ''))
        except Exception:
            qty = None

    uom = grab([r'(?:uom|unit)[:]\s*([A-Za-z]{1,4})']) or "Nos"

    if not item_name:
        return ("To create an item I need at least a name. Please reply with the details,"
                " e.g.: 'Add item Pump Spring, group Raw Material, price 500, opening stock 100 in Stores'.\n"
                "Or: 'Create item named Steel Rod in group Raw Materials price 100'")

    # Check for duplicate
    _existing = frappe.db.get_value("Item", {"item_name": item_name}, ["name", "item_group", "standard_rate"], as_dict=True)
    if not _existing:
        _existing = frappe.db.get_value("Item", {"item_code": item_name.upper()}, ["name", "item_group", "standard_rate"], as_dict=True)
    if _existing:
        _existing_stock = 0
        _bin = frappe.db.get_all("Bin", filters={"item_code": _existing.name}, fields=["actual_qty", "warehouse"])
        if _bin:
            _existing_stock = sum(b.actual_qty or 0 for b in _bin)
        _actions = []
        if price is not None and price != _existing.standard_rate:
            _actions.append(f"update price from {_existing.standard_rate:,.0f} to {price:,.0f}")
        if qty:
            _actions.append(f"add {qty:,.0f} units to stock (current: {_existing_stock:,.0f})")
        if _actions:
            # Store pending action for yes handler
            frappe.get_doc({"doctype": "AI Chat Message", "user": frappe.session.user,
                "session_id": session or "", "role": "user",
                "content": f"[PENDING]|{_existing.name}|{price or 0}|{qty or 0}"
            }).insert(ignore_permissions=True)
            frappe.db.commit()
            return (f"Item '{item_name}' already exists ({_existing.name}).\n"
                    f"  Current: Group={_existing.item_group}, Rate={_existing.standard_rate:,.0f}, Stock={_existing_stock:,.0f}\n"
                    f"  I can: {', '.join(_actions)}.\n"
                    f"  Reply 'yes' to proceed, or 'cancel' to abort.")
        else:
            return (f"Item '{item_name}' already exists ({_existing.name}).\n"
                    f"  Group={_existing.item_group}, Rate={_existing.standard_rate:,.0f}, Stock={_existing_stock:,.0f}\n"
                    f"  Nothing to update. Specify a new price or stock to add.")

    code = item_name.replace(" ", "-").upper()
    # Auto-create item group if it doesn't exist
    if not frappe.db.exists("Item Group", item_group) or frappe.db.get_value("Item Group", item_group) is None:
        try:
            frappe.get_doc({"doctype": "Item Group", "item_group_name": item_group}).insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception:
            pass
    data = {"doctype": "Item", "item_code": code, "item_name": item_name,
            "item_group": item_group, "stock_uom": uom, "is_stock_item": 1,
            "standard_rate": price or 0}
    result = mcp.call_tool("create_document", {"doctype": "Item", "data": data})
    if "error" in result:
        # try again with a code based on time to avoid duplicate
        code = code + "-" + frappe.generate_hash(length=4).upper()
        data["item_code"] = code
        result = mcp.call_tool("create_document", {"doctype": "Item", "data": data})
        if "error" in result:
            return "Could not create item: " + result["error"]

    extra = []
    if qty:
        # record opening stock via Stock Reconciliation or Stock Entry Material Receipt
        se = mcp.call_tool("create_document", {"doctype": "Stock Entry", "data": {
            "doctype": "Stock Entry", "stock_entry_type": "Material Receipt", "purpose": "Material Receipt",
            "company": frappe.defaults.get_global_default("company"),
            "items": [{"item_code": code, "qty": qty, "t_warehouse": "Stores - SPI" if frappe.db.exists("Warehouse", "Stores - SPI") else "Stores", "basic_rate": price or 0}]}})
        if "error" not in se:
            extra.append(f"Opening stock {qty:g} added (Stock Entry {se.get('name')} - DRAFT, submit to confirm)")

    return (f"✅ Item created: {item_name} ({code})\n"
            f"  Group: {item_group} | UOM: {uom} | Price: {price or 0:,.0f}\n"
            + ("\n".join("- " + x for x in extra) + "\n" if extra else "")
            + "Say 'save' or 'submit' to finalize.")


def _handle_create_invoice(prompt, mcp):
    """Extract invoice details and create."""
    import re
    customer_match = re.search(r'(?:customer|client|ke liye)\s+["\']?([^"\',.]+)', prompt, re.I)
    customer = customer_match.group(1).strip() if customer_match else None
    
    if not customer:
        return "To create an invoice, please provide: customer name. Example: 'Create invoice for customer SPI Traders'"
    
    # Check if customer exists
    cust_check = mcp.call_tool("query_doctype", {"doctype": "Customer", "filters": {"name": customer}})
    if cust_check.get("count", 0) == 0:
        return f"Customer '{customer}' not found. Please create the customer first."
    
    data = {
        "doctype": "Sales Invoice",
        "customer": customer,
        "company": frappe.defaults.get_global_default("company"),
        "items": []
    }
    result = mcp.call_tool("create_document", {"doctype": "Sales Invoice", "data": data})
    if "error" in result:
        return f"Error: {result['error']}"
    return result.get("message", "Invoice created")


def _handle_create_customer(prompt, mcp):
    """Extract customer details and create."""
    import re
    name_match = re.search(r'(?:named|name|called|ka naam)\s+["\']?([^"\',.]+)', prompt, re.I)
    name = name_match.group(1).strip() if name_match else None
    
    if not name:
        return "Please provide customer name. Example: 'Create customer named ABC Traders'"
    
    data = {
        "doctype": "Customer",
        "customer_name": name,
        "customer_type": "Company",
        "customer_group": "All Customer Groups",
        "territory": "All Territories"
    }
    result = mcp.call_tool("create_document", {"doctype": "Customer", "data": data})
    if "error" in result:
        return f"Error: {result['error']}"
    return result.get("message", "Customer created")


def _handle_create_supplier(prompt, mcp):
    """Extract supplier details and create."""
    import re
    name_match = re.search(r'(?:named|name|called|ka naam)\s+["\']?([^"\',.]+)', prompt, re.I)
    name = name_match.group(1).strip() if name_match else None
    
    if not name:
        return "Please provide supplier name. Example: 'Create supplier named XYZ Corp'"
    
    data = {
        "doctype": "Supplier",
        "supplier_name": name,
        "supplier_type": "Company",
        "supplier_group": "All Supplier Groups"
    }
    result = mcp.call_tool("create_document", {"doctype": "Supplier", "data": data})
    if "error" in result:
        return f"Error: {result['error']}"
    return result.get("message", "Supplier created")


def _handle_print(prompt, mcp):
    """Handle print requests."""
    import re
    # Try to extract doctype and name
    inv_match = re.search(r'(?:invoice|bill)\s+(\S+)', prompt, re.I)
    if inv_match:
        name = inv_match.group(1)
        result = mcp.call_tool("print_document", {"doctype": "Sales Invoice", "name": name})
        if "error" in result:
            return f"Error: {result['error']}"
        return result.get("message", "Print ready")
    
    return "To print, please specify: 'print invoice INV-001' or 'print receipt'"


def _handle_count_query(prompt, mcp):
    """Handle count/how many queries."""
    prompt_lower = prompt.lower()
    
    if "item" in prompt_lower or "product" in prompt_lower:
        result = mcp.call_tool("query_doctype", {"doctype": "Item", "filters": {"disabled": 0}, "fields": ["name"], "limit": 1000})
        count = result.get("count", 0)
        return f"We have {count} active items in the system."
    
    if "customer" in prompt_lower or "client" in prompt_lower:
        result = mcp.call_tool("query_doctype", {"doctype": "Customer", "fields": ["name"], "limit": 1000})
        count = result.get("count", 0)
        return f"There are {count} customers in the system."
    
    if "supplier" in prompt_lower or "vendor" in prompt_lower:
        result = mcp.call_tool("query_doctype", {"doctype": "Supplier", "fields": ["name"], "limit": 1000})
        count = result.get("count", 0)
        return f"There are {count} suppliers in the system."
    
    if "invoice" in prompt_lower:
        if "unpaid" in prompt_lower or "pending" in prompt_lower or "outstanding" in prompt_lower:
            result = mcp.call_tool("query_doctype", {"doctype": "Sales Invoice", "filters": {"status": "Unpaid"}, "fields": ["name", "grand_total"], "limit": 100})
            invoices = result.get("records", [])
            total = sum(i.get("grand_total", 0) for i in invoices)
            return f"There are {result.get('count', 0)} unpaid invoices totaling {fmt_money(total)}."
        result = mcp.call_tool("query_doctype", {"doctype": "Sales Invoice", "fields": ["name"], "limit": 1000})
        return f"There are {result.get('count', 0)} invoices in the system."
    
    if "stock" in prompt_lower or "inventory" in prompt_lower:
        result = mcp.call_tool("query_doctype", {"doctype": "Bin", "fields": ["actual_qty"], "limit": 10000})
        total_qty = sum(r.get("actual_qty", 0) for r in result.get("records", []))
        return f"Total stock across all warehouses: {total_qty:,.0f} units."
    
    return "I can count: items, customers, suppliers, invoices, stock. Please specify what you want to count."


def _handle_list_query(prompt, mcp):
    """Handle list/show/what-items queries with REAL data + stock quantities."""
    pl = prompt.lower()

    if "item" in pl or "product" in pl or "stock" in pl or "inventory" in pl:
        result = mcp.call_tool("query_doctype", {"doctype": "Item", "filters": {"disabled": 0},
                                                 "fields": ["name", "item_name", "item_group", "standard_rate"], "limit": 50})
        items = result.get("records", [])
        if not items:
            return "No items found in the system."
        # enrich with actual stock from Bin/Stock Ledger
        lines = []
        for i in items[:12]:
            bin_recs = mcp.call_tool("query_doctype", {"doctype": "Bin", "filters": {"item_code": i["name"]},
                                                       "fields": ["actual_qty", "warehouse"], "limit": 20})
            bins = bin_recs.get("records", [])
            if bins:
                qty = sum(b.get("actual_qty", 0) or 0 for b in bins)
                whs = ", ".join(b.get("warehouse", "") for b in bins[:3])
                lines.append(f"- {i.get('item_name', i['name'])} ({i.get('item_group', '')}) | Stock: {qty:,.0f} | Rate: {i.get('standard_rate', 0):,.0f} | {whs}")
            else:
                lines.append(f"- {i.get('item_name', i['name'])} ({i.get('item_group', '')}) | Rate: {i.get('standard_rate', 0):,.0f}")
        total = len(items)
        shown = len(lines)
        return f"We have {total} items. (showing {shown}):\n" + "\n".join(lines)

    if "customer" in pl or "client" in pl:
        result = mcp.call_tool("query_doctype", {"doctype": "Customer", "fields": ["name", "customer_name"], "limit": 50})
        records = result.get("records", [])
        if not records:
            return "No customers found."
        lines = [f"- {r.get('customer_name', r['name'])}" for r in records[:10]]
        return f"We have {result.get('count', 0)} customers (showing {len(lines)}):\n" + "\n".join(lines)

    if "supplier" in pl or "vendor" in pl:
        result = mcp.call_tool("query_doctype", {"doctype": "Supplier", "fields": ["name", "supplier_name"], "limit": 50})
        records = result.get("records", [])
        if not records:
            return "No suppliers found."
        lines = [f"- {r.get('supplier_name', r['name'])}" for r in records[:10]]
        return f"We have {result.get('count', 0)} suppliers (showing {len(lines)}):\n" + "\n".join(lines)

    if "invoice" in pl or "bill" in pl:
        result = mcp.call_tool("query_doctype", {"doctype": "Sales Invoice", "fields": ["name", "customer", "grand_total", "status"], "limit": 20})
        records = result.get("records", [])
        if not records:
            return "No sales invoices found."
        lines = [f"- {r['name']} | {r.get('customer', '')} | {r.get('grand_total', 0):,.0f} | {r.get('status', '')}" for r in records[:10]]
        return f"We have {result.get('count', 0)} sales invoices (showing {len(lines)}):\n" + "\n".join(lines)

    return "I can show: items (with stock), customers, suppliers, invoices. Try: 'what items we have' or 'list customers'."


def _handle_search_query(prompt, mcp):
    """Handle search queries."""
    import re
    query_match = re.search(r'(?:search|find|dhundho)\s+(?:for\s+)?["\']?([^"\']+)', prompt, re.I)
    query = query_match.group(1).strip() if query_match else prompt
    
    result = mcp.call_tool("search_documents", {"query": query, "limit": 10})
    records = result.get("results", [])
    if not records:
        return f"No results found for '{query}'."
    lines = [f"- {r['doctype']}: {r['name']}" for r in records[:5]]
    return f"Search results for '{query}':\n" + "\n".join(lines)



def _format_document_view(doctype, doc):
    """Format a document dict into a readable view."""
    lines = [f"📄 {doctype}: **{doc.get('name', '?')}**"]
    lines.append(f"  Status: {doc.get('docstatus', 0)} (0=Draft, 1=Submitted, 2=Cancelled)")
    if doctype == "Item":
        lines.append(f"  Name: {doc.get('item_name', '')}")
        lines.append(f"  Group: {doc.get('item_group', '')}")
        lines.append(f"  Price: {doc.get('standard_rate', 0):,.0f}")
        lines.append(f"  UOM: {doc.get('stock_uom', '')}")
    elif doctype in ("Sales Invoice", "Purchase Invoice"):
        _party = doc.get('customer', doc.get('supplier', ''))
        lines.append(f"  {'Customer' if 'Sales' in doctype else 'Supplier'}: {_party}")
        lines.append(f"  Grand Total: {doc.get('grand_total', 0):,.0f}")
        lines.append(f"  Status: {doc.get('status', '')}")
        if doc.get('items'):
            lines.append("  Items:")
            for it in doc['items'][:5]:
                lines.append(f"    - {it.get('item_code', '')} | {it.get('qty', 0):g} × {it.get('rate', 0):,.0f}")
    elif doctype == "Customer":
        lines.append(f"  Name: {doc.get('customer_name', '')}")
        lines.append(f"  Group: {doc.get('customer_group', '')}")
        lines.append(f"  Mobile: {doc.get('mobile_no', '')}")
    elif doctype == "Supplier":
        lines.append(f"  Name: {doc.get('supplier_name', '')}")
        lines.append(f"  Group: {doc.get('supplier_group', '')}")
        lines.append(f"  Mobile: {doc.get('mobile_no', '')}")
    return "\n".join(lines)


def _handle_shipment_nl(prompt, mcp):
    import json as _json
    """Parse natural language shipment text and create receipt workflow."""
    import re
    text = prompt
    # Extract supplier: after 'from' or 'supplier'
    supplier = None
    m = re.search(r'(?:from|supplier|vendor)\s+([A-Za-z0-9 .&-]{2,40}?)(?:,|\.|vehicle|arriv|$)', text, re.I)
    if m:
        supplier = m.group(1).strip()
    # Extract vehicle
    vehicle = None
    m = re.search(r'(?:vehicle|truck|van|no\.|number)\s*[:\-]?\s*([A-Z]{2,4}[- ][0-9]{3,4})', text, re.I)
    if m:
        vehicle = m.group(1).strip()
    # Extract items with qty: '500 pcs spring', 'pump springs 500'
    items = []
    items = []
    # Pattern: "500 pcs pump springs" or "500 pump springs"
    for m in re.finditer(r'([0-9][0-9,.]*)\s*(?:pcs|pieces|nos|units|kg|boxes|sets)?\s+([A-Za-z][A-Za-z0-9 -]{2,40}?)(?=\s+(?:arriv|from|to|in|,|\.)|,|\.|$)', text, re.I):
        name = m.group(2).strip()
        try:
            q = float(m.group(1).replace(',', ''))
        except (ValueError, TypeError):
            q = None
        if name and q:
            items.append({"item_name": name, "qty": q})
    # Fallback: bare item names without qty
    if not items:
        for m in re.finditer(r'\b((?:pump\s+)?springs?|bolts?|nuts?|bearings?|gaskets?|seals?|valves?|pumps?)\b', text, re.I):
            items.append({"item_name": m.group(1).strip(), "qty": None})
            items.append({"item_name": name, "qty": q})
    
    missing = []
    if not supplier: missing.append('supplier (who sent it?)')
    if not items: missing.append('items + quantities (what arrived & how many?)')
    
    if missing:
        return ("I can record this shipment for you. Please provide:\n" +
                "\n".join("- " + x for x in missing) +
                "\n\nAlso tell me (optional): vehicle number, which store (Raw Material Store / Technical Store / Finished Goods), rate/price, and any remarks.\n\nExample: 'Spring shipment arrived from ABC Traders, vehicle LEA-4521, 500 pcs pump springs to Raw Material Store'")
    
    # Resolve item names to item codes (search DB, fallback to generated code)
    for it in items:
        nm = it.get("item_name", "")
        found = mcp.call_tool("search_documents", {"query": nm, "doctype": "Item", "limit": 1})
        res = found.get("results", [])
        if res:
            it["item_code"] = res[0]["name"]
        else:
            it["item_code"] = nm.replace(" ", "-").upper()

    # Build workflow data
    data = {"supplier": supplier, "vehicle_no": vehicle, "items": items, "remarks": text[:200]}
    result = workflow_shipment_receipt(_json.dumps(data))
    if "error" in result:
        return "Could not record: " + result["error"]
    steps = "\n".join("- " + s for s in result.get("steps", []))
    entry = result.get("entry", {})
    return ("✅ Shipment recorded as DRAFT:\n" + steps +
            "\n\nDocument: " + entry.get("doctype", "") + " " + entry.get("name", "") +
            "\nReview and submit it to add stock. Say 'submit " + entry.get("name", "") + "' to confirm.")


def _handle_issue_nl(prompt, mcp):
    import json as _json
    """Parse natural language stock issue text."""
    import re
    text = prompt
    qty = None
    m = re.search(r'(?:issue|transfer|jari)\s+([0-9,.]+)', text, re.I)
    if m:
        qty = float(m.group(1).replace(',', ''))
    item = None
    m = re.search(r'(?:issue|transfer|jari)[^a-z]*([0-9,.]+)\s*(?:pcs|nos|units|kg)?\s*([A-Za-z][A-Za-z0-9 -]{2,40}?)(?:\s+to\s+|,|\.|$)', text, re.I)
    if m and m.group(2):
        item = m.group(2).strip()
    person = None
    m = re.search(r'(?:to|for)\s+(?:mr\.|mr\s|engr\.|engr\s)?([A-Za-z]+(?:\s[A-Za-z]+)?)', text, re.I)
    if m:
        person = m.group(1).strip()
    
    missing = []
    if not item: missing.append('item name')
    if not qty: missing.append('quantity')
    if not person: missing.append('person/department to issue to')
    
    if missing:
        return ("To issue stock, please provide:\n" + "\n".join("- " + x for x in missing) +
                "\n\nExample: 'Issue 10 pump springs from Raw Material Store to Engr. Ali (Production)'")
    
    # Find item in DB (fuzzy)
    found = mcp.call_tool("search_documents", {"query": item, "doctype": "Item", "limit": 3})
    results = found.get("results", [])
    if not results:
        return "Item '%s' not found in system. Please check the name." % item
    item_code = results[0]["name"]
    
    data = {"item_code": item_code, "qty": qty, "issue_type": "Material Issue",
            "issued_to": person, "remarks": text[:200]}
    result = workflow_stock_issue(_json.dumps(data))
    if "error" in result:
        return "Could not issue: " + result["error"]
    return "✅ Stock Issue created (DRAFT): %s\nPurpose: %s\n%s\nSubmit to confirm the movement." % (
        result.get("name"), result.get("purpose"), result.get("next", ""))


def _handle_invoice_nl(prompt, mcp):
    import json as _json
    """Parse natural language invoice creation."""
    import re
    text = prompt
    customer = None
    m = re.search(r'(?:for|to|customer|client)\s+([A-Za-z0-9 .&-]{2,40}?)(?:,|\.|items?|$|\d)', text, re.I)
    if m:
        customer = m.group(1).strip()
    # items: '2 pump springs @ 500', '10 bolts @ 50'
    items = []
    for m in re.finditer(r'([0-9,.]+)\s*(?:pcs|nos|units)?\s*([A-Za-z][A-Za-z0-9 -]{2,40}?)\s*(?:@|at|rate|price)\s*([0-9,.]+)', text, re.I):
        q = float(m.group(1).replace(',', ''))
        nm = m.group(2).strip()
        r = float(m.group(3).replace(',', ''))
        items.append({"item_name": nm, "qty": q, "rate": r})
    
    missing = []
    if not customer: missing.append('customer name')
    if not items: missing.append('items with qty and rate (e.g., 2 pump springs @ 500)')
    if missing:
        return ("To create an invoice I need:\n" + "\n".join("- " + x for x in missing) +
                "\n\nExample: 'Make invoice for ABC Traders, 2 pump springs @ 500, 10 bolts @ 50'")
    
    # Resolve item codes
    final_items = []
    for it in items:
        found = mcp.call_tool("search_documents", {"query": it["item_name"], "doctype": "Item", "limit": 1})
        res = found.get("results", [])
        code = res[0]["name"] if res else it["item_name"]
        final_items.append({"item_code": code, "qty": it["qty"], "rate": it["rate"]})
    
    data = {"customer": customer, "items": final_items, "update_stock": 1}
    result = workflow_sales_invoice(_json.dumps(data))
    if "error" in result:
        return "Could not create invoice: " + result["error"]
    return ("✅ Sales Invoice DRAFT created: %s\n%s\nPrint PDF: %s" % (
        result.get("name"), result.get("next", ""), result.get("print_url", "")))


def _handle_general_query(prompt, session, user, model, mcp):
    """Handle general queries. FAST: summary KB by default; full KB only for how-to."""
    import re as _re2
    apps = ", ".join(frappe.get_installed_apps())
    roles = ", ".join(frappe.get_roles())
    fullname = frappe.utils.get_fullname(user)
    pl = prompt.lower()

    # Try fast deterministic data router first (0 ms)
    data = _data_answer(prompt)
    if data["ok"]:
        return data["answer"]

    # Conversation history (last 4, trimmed)
    history = frappe.get_all(
        "AI Chat Message",
        filters={"session_id": session, "user": user},
        order_by="creation desc",
        limit_page_length=2,
        fields=["role", "content"],
    )
    hist_text = "\n".join(f"{m.role}: {m.content}" for m in reversed(history))[:600]

    # KB tier: full only for guidance/how-to questions; compact summary otherwise
    guidance = bool(_re2.search(
        r'\b(how (do|to|can|much|does)|kaise|setup|set up|set-up|workflow|explain|guide|steps|'
        r'procedure|process|policy|requirement|what do i need|need to|help me|difference|'
        r'best practice|should i|tax|accounting rule|chart of accounts|create a new erp)\b', pl))

    if guidance:
        kb = get_knowledge_excerpt(9000)
    else:
        kb = get_kb_summary()

    system = (
        f"AI assistant in SPI ERPNext. User {fullname} ({roles}). Brief answers (max 100 words), real numbers. "
        f"Admins: technical. Operators: short steps.\nFACTS: {kb}"
    )

    full_prompt = f"{system}\n\nRecent chat:\n{hist_text}\n\nUser: {prompt}\nAssistant:"
    return _ollama(full_prompt, model)


@frappe.whitelist()
def text_to_speech(text, lang="en"):
    """Convert text to speech and return audio URL."""
    import subprocess
    import tempfile
    import os
    from frappe.utils import get_site_path, get_url
    
    if not text:
        return {"error": "No text provided"}
    
    # Select voice model based on language
    if lang == "ur":
        model = "/home/erpnext/ai/models/ur_PK-fasih-medium.onnx"
    else:
        model = "/home/erpnext/ai/models/en_US-lessac-medium.onnx"
    
    if not os.path.exists(model):
        return {"error": f"Voice model not found: {model}"}
    
    # Generate unique filename
    filename = f"tts_{frappe.generate_hash(length=8)}.wav"
    output_path = os.path.join("/tmp", filename)
    
    try:
        # Run Piper TTS
        process = subprocess.run(
            ["/home/erpnext/ai/piper/piper", "--model", model, "--output_file", output_path],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30
        )
        
        if process.returncode != 0:
            return {"error": f"TTS failed: {process.stderr.decode()}"}
        
        # Move to public folder for serving (shutil works across filesystems)
        import shutil
        public_path = get_site_path("public", "files", "tts", filename)
        os.makedirs(os.path.dirname(public_path), exist_ok=True)
        shutil.move(output_path, public_path)
        
        # Return URL
        audio_url = f"/files/tts/{filename}"
        return {"url": audio_url, "text": text[:100]}
        
    except Exception as e:
        return {"error": str(e)}


@frappe.whitelist()
def ask_v2_with_voice(prompt, session=None, model=None, voice=True):
    """Enhanced AI assistant with optional voice output."""
    if not prompt:
        frappe.throw("prompt is required")
    
    # Get text response
    result = ask_v2(prompt, session, model)
    response_text = result.get("response", "")
    
    # Generate voice if requested
    audio_url = None
    if voice and response_text:
        tts_result = text_to_speech(response_text)
        audio_url = tts_result.get("url")
    
    return {
        "response": response_text,
        "session": result.get("session"),
        "audio_url": audio_url
    }


# ============ WORKFLOW HANDLERS ============

@frappe.whitelist()
def workflow_shipment_receipt(data=None):
    """Record an incoming shipment into inventory.
    data JSON: supplier, vehicle_no, items: [{item_code, qty, rate}], warehouse, remarks
    Creates Supplier/PO if missing (as draft), then Purchase Receipt or Stock Entry.
    """
    import json as _json
    data = _json.loads(data) if isinstance(data, str) else (data or {})
    mcp = FrappeMCP()
    steps = []

    supplier = data.get("supplier")
    if not supplier:
        return {"error": "Supplier name required", "missing": ["supplier"]}

    # Ensure supplier exists (create draft if not)
    exists = mcp.call_tool("query_doctype", {"doctype": "Supplier", "filters": {"supplier_name": supplier}})
    if exists.get("count", 0) == 0:
        created = mcp.call_tool("create_document", {"doctype": "Supplier", "data": {
            "doctype": "Supplier", "supplier_name": supplier, "supplier_type": "Company",
            "supplier_group": "All Supplier Groups"}})
        steps.append("Supplier created: %s" % created.get("name", supplier))

    items = data.get("items") or []
    if not items:
        return {"error": "items required (item_code, qty, rate)", "missing": ["items"]}

    warehouse = data.get("warehouse") or "Stores - SPI" if frappe.db.exists("Warehouse", "Stores - SPI") else (data.get("warehouse") or None)

    # Validate items exist; create if missing
    for it in items:
        ic = it.get("item_code")
        if not ic:
            return {"error": "item_code required in every item", "missing": ["item_code"]}
        found = mcp.call_tool("query_doctype", {"doctype": "Item", "filters": {"name": ic}})
        if found.get("count", 0) == 0:
            created = mcp.call_tool("create_document", {"doctype": "Item", "data": {
                "doctype": "Item", "item_code": ic, "item_name": it.get("item_name", ic),
                "item_group": it.get("item_group", "Raw Material"), "stock_uom": it.get("uom", "Nos"),
                "is_stock_item": 1, "standard_rate": it.get("rate", 0)}})
            steps.append("Item created: %s" % created.get("name", ic))

    remarks = " | ".join(filter(None, ["Vehicle: %s" % data.get("vehicle_no") if data.get("vehicle_no") else None, data.get("remarks", "")]))

    entry = None
    # Prefer Purchase Receipt linked to nothing (direct) -> create as draft
    pr_data = {
        "doctype": "Purchase Receipt",
        "supplier": supplier,
        "company": frappe.defaults.get_global_default("company"),
        "items": [{"item_code": it["item_code"], "qty": it.get("qty", 0),
                   "rate": it.get("rate", 0), "t_warehouse": warehouse} for it in items],
        "remarks": remarks,
    }
    pr = mcp.call_tool("create_document", {"doctype": "Purchase Receipt", "data": pr_data})
    if "error" in pr:
        # Fallback to Stock Entry Material Receipt
        se_data = {
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "purpose": "Material Receipt",
            "company": frappe.defaults.get_global_default("company"),
            "items": [{"item_code": it["item_code"], "qty": it.get("qty", 0),
                       "t_warehouse": warehouse, "basic_rate": it.get("rate", 0)} for it in items],
            "remarks": remarks,
        }
        se = mcp.call_tool("create_document", {"doctype": "Stock Entry", "data": se_data})
        if "error" in se:
            return {"error": se["error"], "steps": steps}
        entry = {"doctype": "Stock Entry", "name": se.get("name"), "status": "Draft"}
        steps.append("Stock Entry (Material Receipt) created: %s" % se.get("name"))
    else:
        entry = {"doctype": "Purchase Receipt", "name": pr.get("name"), "status": "Draft"}
        steps.append("Purchase Receipt created: %s" % pr.get("name"))

    steps.append("Next: submit the document to add stock, then Purchase Invoice for supplier bill, then Payment Entry to pay.")
    return {"success": True, "entry": entry, "steps": steps}


@frappe.whitelist()
def workflow_stock_issue(data=None):
    """Issue/transfer stock to a department or person.
    data JSON: item_code, qty, from_warehouse, to_warehouse(optional), issue_type (Issue/Transfer), issued_to, department, remarks
    """
    import json as _json
    data = _json.loads(data) if isinstance(data, str) else (data or {})
    mcp = FrappeMCP()

    item_code = data.get("item_code")
    qty = data.get("qty")
    from_wh = data.get("from_warehouse")
    if not (item_code and qty and from_wh):
        return {"error": "item_code, qty and from_warehouse required",
                "missing": [k for k in ("item_code", "qty", "from_warehouse") if not data.get(k)]}

    issue_type = data.get("issue_type", "Material Issue")
    purpose = "Material Issue" if issue_type.lower().startswith("issue") else "Material Transfer"
    to_wh = data.get("to_warehouse")
    if purpose == "Material Transfer" and not to_wh:
        return {"error": "to_warehouse required for Material Transfer", "missing": ["to_warehouse"]}

    remarks_parts = []
    if data.get("issued_to"):
        remarks_parts.append("Issued to: %s" % data["issued_to"])
    if data.get("department"):
        remarks_parts.append("Department: %s" % data["department"])
    if data.get("remarks"):
        remarks_parts.append(str(data["remarks"]))

    item_row = {"item_code": item_code, "qty": qty, "s_warehouse": from_wh}
    if to_wh:
        item_row["t_warehouse"] = to_wh

    se_data = {"doctype": "Stock Entry", "stock_entry_type": purpose, "purpose": purpose,
               "company": frappe.defaults.get_global_default("company"),
               "items": [item_row], "remarks": " | ".join(remarks_parts)}
    se = mcp.call_tool("create_document", {"doctype": "Stock Entry", "data": se_data})
    if "error" in se:
        return {"error": se["error"]}
    return {"success": True, "doctype": "Stock Entry", "name": se.get("name"), "purpose": purpose,
            "next": "Submit to move stock. Print: /api/method/frappe.utils.print_format.download_pdf?doctype=Stock%20Entry&name=%s" % se.get("name")}


@frappe.whitelist()
def workflow_sales_invoice(data=None):
    """Create a Sales Invoice (draft) with items. data JSON: customer, items:[{item_code,qty,rate}], update_stock, taxes_template, remarks
    """
    import json as _json
    data = _json.loads(data) if isinstance(data, str) else (data or {})
    mcp = FrappeMCP()
    customer = data.get("customer")
    if not customer:
        return {"error": "customer required", "missing": ["customer"]}

    exists = mcp.call_tool("query_doctype", {"doctype": "Customer", "filters": {"name": customer}})
    if exists.get("count", 0) == 0:
        return {"error": "Customer '%s' not found. Create it first." % customer}

    items = data.get("items") or []
    if not items:
        return {"error": "items required (item_code, qty, rate)", "missing": ["items"]}

    si_data = {
        "doctype": "Sales Invoice",
        "customer": customer,
        "company": frappe.defaults.get_global_default("company"),
        "update_stock": 1 if data.get("update_stock") else 0,
        "items": [{"item_code": it["item_code"], "qty": it.get("qty", 1), "rate": it.get("rate", 0)} for it in items],
    }
    if data.get("taxes_template"):
        si_data["taxes_and_charges"] = data["taxes_template"]
    if data.get("remarks"):
        si_data["remarks"] = data["remarks"]

    si = mcp.call_tool("create_document", {"doctype": "Sales Invoice", "data": si_data})
    if "error" in si:
        return {"error": si["error"]}
    name = si.get("name")
    return {"success": True, "doctype": "Sales Invoice", "name": name, "status": "Draft",
            "next": "Submit to post to accounts, then Payment Entry to receive money.",
            "print_url": "/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%%20Invoice&name=%s&format=Standard" % name}
