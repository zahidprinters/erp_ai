import json

import base64
import os
import re
import subprocess

import frappe
import requests
from frappe.utils import fmt_money

from erp_ai.mcp.server import FrappeMCP
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:1.5b"


def _ollama(prompt, model=None, timeout=180):
    """Call local Ollama and return the generated text."""
    model = model or frappe.conf.get("ai_model") or DEFAULT_MODEL
    r = requests.post(
        OLLAMA_URL,
        json={"model": model, "prompt": prompt, "stream": False},
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
                        "text": "💬 Live AI chat is loading below...",
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
    """Process prompt using MCP tools."""
    prompt_lower = prompt.lower().strip()
    
    # Intent detection and tool calling
    mcp = FrappeMCP()
    
    # Create item
    if any(kw in prompt_lower for kw in ["create item", "add item", "new item", "item banaiye", "item create"]):
        return _handle_create_item(prompt, mcp)
    
    # Create invoice
    if any(kw in prompt_lower for kw in ["create invoice", "add invoice", "new invoice", "invoice banaiye", "bill banaiye"]):
        return _handle_create_invoice(prompt, mcp)
    
    # Create customer
    if any(kw in prompt_lower for kw in ["create customer", "add customer", "new customer", "customer banaiye", "client banaiye"]):
        return _handle_create_customer(prompt, mcp)
    
    # Create supplier
    if any(kw in prompt_lower for kw in ["create supplier", "add supplier", "new supplier", "supplier banaiye", "vendor banaiye"]):
        return _handle_create_supplier(prompt, mcp)
    
    # Print document
    if any(kw in prompt_lower for kw in ["print", "pdf", "receipt", "challan"]):
        return _handle_print(prompt, mcp)
    
    # Count queries
    if any(kw in prompt_lower for kw in ["how many", "count of", "number of", "kitne", "total"]):
        return _handle_count_query(prompt, mcp)
    
    # List queries
    if any(kw in prompt_lower for kw in ["list", "show me", "dikhaiye", "all", "sab"]):
        return _handle_list_query(prompt, mcp)
    
    # Search queries
    if any(kw in prompt_lower for kw in ["search", "find", "dhundho", "lookup"]):
        return _handle_search_query(prompt, mcp)
    
    # Default: try data router first, then Ollama with MCP context
    return _handle_general_query(prompt, session, user, model, mcp)


def _handle_create_item(prompt, mcp):
    """Extract item details from prompt and create."""
    import re
    # Try to extract item name, code, group, price
    name_match = re.search(r'(?:named|name|called|ka naam)\s+["\']?([^"\',.]+)', prompt, re.I)
    group_match = re.search(r'(?:group|category|category)\s+["\']?([^"\',.]+)', prompt, re.I)
    price_match = re.search(r'(?:price|rate|cost|keemat)\s+(\d+)', prompt, re.I)
    
    item_name = name_match.group(1).strip() if name_match else None
    item_group = group_match.group(1).strip() if group_match else "Products"
    standard_rate = float(price_match.group(1)) if price_match else 0
    
    if not item_name:
        return "To create an item, please provide: item name, group (optional), price (optional). Example: 'Create item named Steel Rod in group Raw Materials price 100'"
    
    data = {
        "doctype": "Item",
        "item_name": item_name,
        "item_code": item_name.replace(" ", "-").upper(),
        "item_group": item_group,
        "stock_uom": "Nos",
        "standard_rate": standard_rate,
        "is_stock_item": 1
    }
    result = mcp.call_tool("create_document", {"doctype": "Item", "data": data})
    if "error" in result:
        return f"Error: {result['error']}"
    return result.get("message", "Item created")


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
    """Handle list/show me queries."""
    prompt_lower = prompt.lower()
    
    if "item" in prompt_lower or "product" in prompt_lower:
        result = mcp.call_tool("query_doctype", {"doctype": "Item", "filters": {"disabled": 0}, "fields": ["name", "item_name", "standard_rate"], "limit": 10})
        items = result.get("records", [])
        if not items:
            return "No items found."
        lines = [f"- {i.get('item_name', i['name'])} (Rate: {i.get('standard_rate', 0)})" for i in items[:5]]
        return f"Here are some items (showing 5 of {result['count']}):\n" + "\n".join(lines)
    
    if "customer" in prompt_lower:
        result = mcp.call_tool("query_doctype", {"doctype": "Customer", "fields": ["name", "customer_name"], "limit": 10})
        records = result.get("records", [])
        if not records:
            return "No customers found."
        lines = [f"- {r.get('customer_name', r['name'])}" for r in records[:5]]
        return f"Here are some customers (showing 5 of {result['count']}):\n" + "\n".join(lines)
    
    return "I can list: items, customers, suppliers, invoices. Please specify what you want to see."


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


def _handle_general_query(prompt, session, user, model, mcp):
    """Handle general queries with Ollama + MCP context."""
    apps = ", ".join(frappe.get_installed_apps())
    roles = ", ".join(frappe.get_roles())
    fullname = frappe.utils.get_fullname(user)
    
    # Get conversation history
    history = frappe.get_all(
        "AI Chat Message",
        filters={"session_id": session, "user": user},
        order_by="creation desc",
        limit_page_length=8,
        fields=["role", "content"],
    )
    hist_text = "\n".join(f"{m.role}: {m.content}" for m in reversed(history))[:3000]
    
    # Build enhanced system prompt with MCP capabilities
    system = (
        f"You are the built-in AI assistant of SPI's ERPNext system, running on "
        f"Frappe Framework v15. Installed apps: {apps}. "
        f"The current user is {fullname} ({user}), roles: {roles}. "
        f"You have FULL ACCESS to the ERP system. You can:\n"
        f"- Query any data (items, customers, invoices, stock, etc.)\n"
        f"- Create new documents (items, invoices, customers, suppliers)\n"
        f"- Update existing documents\n"
        f"- Print documents (generate PDFs)\n"
        f"- Search across all documents\n\n"
        f"Adapt your answer to this user: give administrators technical detail; "
        f"give operators short, simple, step-by-step guidance. "
        f"Be brief, practical and accurate. Always provide real numbers and data."
    )
    
    full_prompt = f"{system}\n\nConversation so far:\n{hist_text}\n\nUser: {prompt}\nAssistant:"
    
    # Try data router first
    data = _data_answer(prompt)
    if data["ok"]:
        return data["answer"]
    
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
