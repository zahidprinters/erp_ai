# ---------------------------------------------------------------------------
# LLM interface — talks to local Ollama.
#
# Single responsibility: send a prompt to Ollama and get text back.
# No ERP logic, no doctype knowledge — just the wire.
# ---------------------------------------------------------------------------
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:1.5b"

# Models the assistant is allowed to call directly.
AI_ALLOWED_MODELS = frozenset(("qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:7b"))


def _allowed_model(model):
    """Return an allowed model name, or raise ValidationError."""
    import frappe
    if not model:
        return DEFAULT_MODEL
    candidate = model or frappe.conf.get("ai_model") or DEFAULT_MODEL
    if candidate in AI_ALLOWED_MODELS:
        return candidate
    if frappe.conf.get("ai_model") == candidate:
        return candidate
    raise frappe.ValidationError(
        "Model not allowed: %s. Configure ai_model or use an allowed assistant model." % candidate
    )


def ask_ollama(prompt, model=None, timeout=180, num_predict=220):
    """Send a prompt to local Ollama and return the stripped response text."""
    model = _allowed_model(model)
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": -1,
            "options": {"num_predict": num_predict, "temperature": 0.4, "num_ctx": 4096},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return (r.json().get("response") or "").strip()
