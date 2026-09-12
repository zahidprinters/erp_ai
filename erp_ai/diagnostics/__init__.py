# ---------------------------------------------------------------------------
# App health check — comprehensive system diagnostic.
# Verifies that the AI app and all dependencies are configured correctly.
# ---------------------------------------------------------------------------
import importlib
import os
from typing import Any, Dict


def health_check() -> Dict[str, Any]:
    """Run a comprehensive health check."""
    results = {"status": "healthy", "checks": [], "warnings": [], "errors": []}

    _check_python_deps(results)
    _check_ollama(results)
    _check_frappe_context(results)
    _check_doctypes(results)
    _check_voice_stack(results)
    _check_mcp_tools(results)
    _check_module_integrity(results)
    _check_config(results)

    if results["errors"]:
        results["status"] = "error"
    elif results["warnings"]:
        results["status"] = "warning"

    return results


def _add_check(results, name, ok, message):
    results["checks"].append({"name": name, "ok": ok, "message": message})
    if not ok:
        results["warnings"].append(message)


def _check_python_deps(results):
    deps = [("requests", "HTTP client"), ("frappe", "Frappe framework")]
    for pkg, desc in deps:
        try:
            mod = importlib.import_module(pkg)
            ver = getattr(mod, "__version__", "installed")
            _add_check(results, "dep:" + pkg, True, "%s: %s" % (pkg, ver))
        except ImportError:
            _add_check(results, "dep:" + pkg, False, "%s not installed (%s)" % (pkg, desc))
            results["errors"].append("Missing: " + pkg)


def _check_ollama(results):
    import requests
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            models = r.json().get("models", [])
            names = [m.get("name", "?") for m in models]
            _add_check(results, "ollama", True, "Running, %d model(s): %s" % (len(names), ", ".join(names[:5])))
        else:
            _add_check(results, "ollama", False, "HTTP %d" % r.status_code)
    except requests.ConnectionError:
        _add_check(results, "ollama", False, "Not reachable at localhost:11434")
        results["errors"].append("Ollama not running")
    except Exception as e:
        _add_check(results, "ollama", False, "Error: %s" % str(e))


def _check_frappe_context(results):
    import frappe
    try:
        _add_check(results, "frappe_user", True, "User: %s" % frappe.session.user)
    except Exception as e:
        _add_check(results, "frappe_user", False, "Error: %s" % str(e))
    try:
        _add_check(results, "frappe_site", True, "Site: %s" % frappe.local.site)
    except Exception:
        _add_check(results, "frappe_site", False, "No site context")


def _check_doctypes(results):
    import frappe
    for dt in ["AI Chat Message", "AI Assistant Action"]:
        try:
            if frappe.db.exists("DocType", dt):
                _add_check(results, "doctype:" + dt, True, "%s: %d records" % (dt, frappe.db.count(dt)))
            else:
                _add_check(results, "doctype:" + dt, False, "Not installed")
                results["errors"].append("Missing DocType: " + dt)
        except Exception as e:
            _add_check(results, "doctype:" + dt, False, "Error: %s" % str(e))


def _check_voice_stack(results):
    home = os.environ.get("AI_HOME", os.path.join(os.path.expanduser("~"), "ai"))
    whisper = os.path.join(home, "whisper.cpp/build/bin/whisper-cli")
    piper = os.path.join(home, "piper/piper")
    _add_check(results, "voice_whisper", os.path.exists(whisper),
               "Whisper CLI " + ("found" if os.path.exists(whisper) else "not found (optional)"))
    _add_check(results, "voice_piper", os.path.exists(piper),
               "Piper TTS " + ("found" if os.path.exists(piper) else "not found (optional)"))


def _check_mcp_tools(results):
    try:
        from erp_ai.mcp.server import ALLOWED_DOCTYPES, FrappeMCP
        mcp = FrappeMCP()
        _add_check(results, "mcp_tools", True, "%d tools, %d doctypes" % (len(mcp.tools), len(ALLOWED_DOCTYPES)))
    except Exception as e:
        _add_check(results, "mcp_tools", False, "Error: %s" % str(e))
        results["errors"].append("MCP not accessible")


def _check_module_integrity(results):
    import frappe
    for mod in ["erp_ai.llm", "erp_ai.schema", "erp_ai.intents", "erp_ai.safety",
                "erp_ai.questions", "erp_ai.validators", "erp_ai.reports",
                "erp_ai.duplication", "erp_ai.handlers", "erp_ai.voice", "erp_ai.voice.toggle"]:
        try:
            importlib.import_module(mod)
            _add_check(results, "mod:" + mod, True, "OK")
        except ImportError as e:
            _add_check(results, "mod:" + mod, False, "Error: %s" % str(e))
            results["errors"].append("Module: " + mod)


def _check_config(results):
    import frappe
    ai_model = frappe.conf.get("ai_model")
    _add_check(results, "config:ai_model", bool(ai_model),
               "Model: %s" % (ai_model or "default (qwen2.5:1.5b)"))
