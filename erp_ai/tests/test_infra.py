# ---------------------------------------------------------------------------
# Tests for infrastructure utilities: barcode checksums, attachment
# validation, idempotency key generation. Database-free (no frappe import).
# ---------------------------------------------------------------------------

import pytest

from erp_ai.attachments import ALLOWED_BASE_DIR, MAX_FILE_SIZE_MB, _sniff_mime, validate_file
from erp_ai.barcode import _ean13_checksum, _upc_checksum, validate_barcode_format
from erp_ai.idempotency import generate_idempotency_key


# --- Barcode checksums ---
def test_ean13_valid_checksum():
    # 9780201379624 is the ISBN-13 for "The C Programming Language" —
    # a valid EAN-13 (weights 1,3,1,3... -> check digit 4)
    assert _ean13_checksum("9780201379624") is True


def test_ean13_invalid_checksum():
    # Same 12 digits, wrong check digit (5 instead of 4)
    assert _ean13_checksum("9780201379625") is False


def test_ean13_wrong_length():
    assert _ean13_checksum("890123456789") is False
    assert _ean13_checksum("89012345678951") is False


def test_ean13_nondigit():
    assert _ean13_checksum("abc1234567890") is False


def test_upc_valid_checksum():
    # 036000291452 is a well-known valid UPC-A
    assert _upc_checksum("036000291452") is True


def test_upc_invalid_checksum():
    assert _upc_checksum("036000291453") is False


def test_validate_ean13_format():
    assert validate_barcode_format("9780201379624", "ean13") is True
    assert validate_barcode_format("9780201379625", "ean13") is False


def test_validate_upc_format():
    assert validate_barcode_format("036000291452", "upc") is True
    assert validate_barcode_format("036000291453", "upc") is False


def test_validate_code128_format():
    assert validate_barcode_format("ITEM-001", "code128") is True
    assert validate_barcode_format("", "code128") is False


# --- Attachment validation ---
def test_validate_file_rejects_negative_size():
    err = validate_file("a.pdf", -1)
    assert err == "Invalid file size"


def test_validate_file_rejects_oversized():
    err = validate_file("a.pdf", MAX_FILE_SIZE_MB * 1024 * 1024 + 1)
    assert err is not None and "too large" in err


def test_validate_file_rejects_unknown_extension():
    err = validate_file("evil.sh", 100)
    assert err is not None and "not allowed" in err


def test_validate_file_rejects_mime_mismatch():
    err = validate_file("a.pdf", 100, mime_type="text/html")
    assert err is not None and "MIME" in err


def test_validate_file_accepts_valid_png():
    err = validate_file("scan.png", 100, mime_type="image/png",
                        content_head=b"\x89PNG\r\n\x1a\n\x00\x00")
    assert err is None


def test_validate_file_rejects_spoofed_extension():
    # A shell script renamed to .pdf must fail signature sniffing
    err = validate_file("evil.pdf", 100, mime_type="application/pdf",
                        content_head=b"#!/bin/sh\nrm -rf /\x00")
    assert err is not None and "signature" in err


def test_validate_file_rejects_unknown_content():
    # 0xFF/0xFE are never valid UTF-8 lead bytes -> not a recognized file type
    err = validate_file("a.txt", 10, content_head=b"\xff\xfe\xfd\xfc\x00")
    assert err is not None


def test_sniff_mime_detects_pdf():
    assert _sniff_mime(b"%PDF-1.7\n") == "application/pdf"


def test_sniff_mime_detects_txt():
    assert _sniff_mime(b"hello world plain text") == "text/plain"


def test_extract_text_refuses_outside_dir():
    from erp_ai.attachments import extract_text_from_file
    res = extract_text_from_file("/etc/passwd")
    assert res.get("error") and "allowed directory" in res["error"]


def test_cleanup_temp_files_safe():
    # No crash when dir missing; returns 0
    import os

    from erp_ai.attachments import cleanup_temp_files
    if not os.path.isdir(ALLOWED_BASE_DIR):
        assert cleanup_temp_files() == 0


# --- Attachment path containment and private upload dir (audit point 15) ---
def test_is_within_rejects_sibling_prefix_directory(tmp_path):
    import os

    from erp_ai.attachments import _is_within
    base = tmp_path / "uploads"
    sibling = tmp_path / "uploads_evil"
    base.mkdir()
    sibling.mkdir()
    assert _is_within(str(base), str(base / "scan.png")) is True
    # A plain str.startswith() check wrongly accepts this sibling directory.
    assert str(sibling / "scan.png").startswith(str(base))
    assert _is_within(str(base), str(sibling / "scan.png")) is False


def test_safe_path_neutralizes_traversal(tmp_path):
    import os

    from erp_ai.attachments import _is_within, _safe_path
    base = str(tmp_path / "uploads")
    resolved = _safe_path(base, "../../etc/passwd")
    assert resolved and _is_within(base, resolved)
    assert os.path.basename(resolved) == "passwd"
    assert _safe_path(base, ".hidden.pdf") is None
    assert _safe_path(base, "") is None


def test_upload_dir_is_private(tmp_path):
    import os

    from erp_ai.attachments import _ensure_base_dir
    base = tmp_path / "uploads"
    base.mkdir(mode=0o755)
    assert _ensure_base_dir(str(base)) is True
    assert os.stat(str(base)).st_mode & 0o077 == 0, "upload dir must be 0700"


def test_upload_dir_refuses_foreign_owner(tmp_path, monkeypatch):
    import os

    from erp_ai.attachments import _ensure_base_dir
    base = tmp_path / "uploads"
    base.mkdir()
    monkeypatch.setattr(os, "getuid", lambda: os.stat(str(base)).st_uid + 1)
    assert _ensure_base_dir(str(base)) is False


# --- Voice hardening (audit point 16) ---
def test_voice_subprocesses_are_bounded():
    """Every subprocess call in the voice stack must pass ``timeout=``."""
    import ast
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[1] / "voice" / "__init__.py"
    tree = ast.parse(src.read_text())
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute) and n.func.attr == "run"
        and isinstance(n.func.value, ast.Name) and n.func.value.id == "subprocess"
    ]
    assert calls, "expected subprocess.run calls in the voice module"
    for call in calls:
        assert any(k.arg == "timeout" for k in call.keywords), \
            "unbounded subprocess.run at line %s" % call.lineno


def _stub_frappe(monkeypatch):
    import sys
    import types
    monkeypatch.setitem(sys.modules, "frappe", types.SimpleNamespace(
        generate_hash=lambda length=8: "deadbeef"))


def test_voice_rejects_oversized_audio(monkeypatch, tmp_path):
    import os

    _stub_frappe(monkeypatch)
    monkeypatch.setenv("AI_HOME", str(tmp_path))

    from erp_ai.voice import MAX_AUDIO_BYTES, voice_to_text
    res = voice_to_text(b"x" * (MAX_AUDIO_BYTES + 1), "wav")
    assert "too large" in res["error"]
    # Rejected before any temp file is written.
    assert not os.path.exists(os.path.join(str(tmp_path), "tmp"))


def test_voice_rejects_bad_format_without_touching_disk(monkeypatch, tmp_path):
    import os

    _stub_frappe(monkeypatch)
    monkeypatch.setenv("AI_HOME", str(tmp_path))

    from erp_ai.voice import voice_to_text
    assert "Unsupported audio format" in voice_to_text(b"abc", "exe")["error"]
    assert not os.path.exists(os.path.join(str(tmp_path), "tmp"))


def test_voice_timeout_cleans_up_temp_files(monkeypatch, tmp_path):
    """A hung decoder must not hang the worker and must not leak the upload."""
    import os
    import subprocess as sp

    _stub_frappe(monkeypatch)
    monkeypatch.setenv("AI_HOME", str(tmp_path))

    # Make the runtime look provisioned so the run reaches transcription.
    (tmp_path / "whisper.cpp/build/bin").mkdir(parents=True)
    (tmp_path / "whisper.cpp/build/bin/whisper-cli").write_bytes(b"")
    (tmp_path / "models").mkdir()
    (tmp_path / "models/ggml-tiny.bin").write_bytes(b"")

    def fake_run(cmd, **kwargs):
        assert kwargs.get("timeout") is not None, "unbounded subprocess: %s" % cmd[0]
        if cmd[0].endswith("whisper-cli"):
            raise sp.TimeoutExpired(cmd, kwargs["timeout"])
        return sp.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(sp, "run", fake_run)

    from erp_ai.voice import voice_to_text
    res = voice_to_text(b"RIFF\x00\x00\x00\x00WAVEfmt ", "wav")
    assert "timed out" in res["error"]
    # `finally` cleanup removed both the raw upload and the converted wav.
    assert os.listdir(tmp_path / "tmp") == []


def test_voice_temp_dir_is_private(tmp_path):
    import os

    from erp_ai.voice import _private_tmp_dir
    tmp = _private_tmp_dir(str(tmp_path))
    assert os.stat(tmp).st_mode & 0o077 == 0, "voice temp dir must be 0700"


def test_voice_rejects_oversized_tts(monkeypatch, tmp_path):
    _stub_frappe(monkeypatch)
    monkeypatch.setenv("AI_HOME", str(tmp_path))

    from erp_ai.voice import MAX_TTS_CHARS, text_to_speech
    res = text_to_speech("a" * (MAX_TTS_CHARS + 1))
    assert "too long" in res["error"]


# --- Idempotency key generation ---
def test_idempotency_key_deterministic():
    a = generate_idempotency_key("sess-1", "create", "Sales Invoice",
                                 {"customer": "ABC"})
    b = generate_idempotency_key("sess-1", "create", "Sales Invoice",
                                 {"customer": "ABC"})
    assert a == b


def test_idempotency_key_differs_on_data():
    a = generate_idempotency_key("sess-1", "create", "Sales Invoice",
                                 {"customer": "ABC"})
    b = generate_idempotency_key("sess-1", "create", "Sales Invoice",
                                 {"customer": "XYZ"})
    assert a != b


def test_idempotency_key_differs_on_action():
    a = generate_idempotency_key("sess-1", "create", "Sales Invoice", {})
    b = generate_idempotency_key("sess-1", "submit", "Sales Invoice", {})
    assert a != b


def test_idempotency_key_is_24_hex():
    key = generate_idempotency_key("s", "a", "Item", {"x": 1})
    assert len(key) == 24
    int(key, 16)  # raises if not hex


# --- AI Settings runtime enforcement (audit point 14) ---
class _Settings:
    """Minimal AI Settings stand-in: attribute access plus ``.get()``.

    Numeric knobs default like the doctype's field defaults (``ask_llm`` reads
    them as attributes).
    """

    def __init__(self, **fields):
        fields.setdefault("default_temperature", 0.7)
        fields.setdefault("max_tokens", 2048)
        fields.setdefault("timeout_seconds", 120)
        self.__dict__.update(fields)

    def get(self, key, default=None):
        return self.__dict__.get(key, default)


class _ValidationError(Exception):
    pass


def _import_llm(monkeypatch, settings, post=None):
    """Import erp_ai.llm without frappe, with a throw that actually raises.

    The CI "database-free" step has no frappe installed, so the module must be
    imported with a stub; the stub's ``throw`` raises so code paths that rely on
    it failing are testable. ``post`` replaces ``requests.post`` and captures
    ``(url, kwargs)`` per call; without one, any outbound HTTP fails the test
    instead of hitting the network. The module attribute is patched directly so
    an earlier import in the same session (real ``requests`` already bound)
    is covered too.
    """
    import sys
    import types

    stub = types.SimpleNamespace(
        throw=lambda msg="", *a, **k: (_ for _ in ()).throw(_ValidationError(str(msg))),
        session=types.SimpleNamespace(user="tester"),
    )
    monkeypatch.setitem(sys.modules, "frappe", stub)

    def _no_http(url, **kwargs):
        raise AssertionError("unexpected outbound HTTP request to %s" % url)

    requests_stub = types.SimpleNamespace(post=post or _no_http)
    monkeypatch.setitem(sys.modules, "requests", requests_stub)
    import erp_ai.llm as llm
    monkeypatch.setattr(llm, "get_llm_settings", lambda: settings)
    monkeypatch.setattr(llm, "requests", requests_stub)
    return llm


def _fake_response():
    import types
    return types.SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"choices": [{"message": {"content": "ok"}}]},
    )


def test_clean_provider_name_resolves_stored_option_keys(monkeypatch):
    llm = _import_llm(monkeypatch, _Settings())
    clean_provider_name = llm.clean_provider_name

    # Bare key — the doctype's stored/default spelling
    assert clean_provider_name("ollama") == "Ollama (Local)"
    assert clean_provider_name("openrouter") == "OpenRouter"
    # Full stored Select value
    assert clean_provider_name("ollama|Ollama (Local - Free)") == "Ollama (Local)"
    assert clean_provider_name("openrouter|OpenRouter (Cloud - Pay per use)") == "OpenRouter"
    # PROVIDERS key round-trips
    assert clean_provider_name("OpenRouter") == "OpenRouter"


def test_default_site_configuration_is_valid_and_local(monkeypatch):
    """The shipped default (llm_provider='ollama') must stay valid."""
    settings = _Settings(llm_provider="ollama", default_llm_model="qwen2.5:1.5b")
    llm = _import_llm(monkeypatch, settings)

    assert llm.validate_deployment_settings(settings) is None
    assert llm.get_provider_config("ollama")["base_url"].startswith("http://localhost:11434")


def test_get_provider_config_throws_on_unknown_provider(monkeypatch):
    settings = _Settings(llm_provider="bogus")
    llm = _import_llm(monkeypatch, settings)

    with pytest.raises(Exception, match="Unknown LLM provider"):
        llm.get_provider_config("bogus")


def test_ask_llm_sends_form_configured_key_and_model(monkeypatch):
    """The settings form's api_key/llm_model must reach the wire.

    The runtime used to read only llm_api_key/llm_base_url — the operator's
    form-entered key was ignored and calls went out unauthenticated.
    """
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, kwargs=kwargs)
        return _fake_response()

    settings = _Settings(
        llm_provider="openrouter", api_key="sk-form-key",
        llm_model="openrouter|gpt-4o-mini", default_llm_model="",
    )
    llm = _import_llm(monkeypatch, settings, post=fake_post)

    assert llm.ask_llm("hi") == "ok"
    assert captured["url"] == llm.PROVIDERS["OpenRouter"]["base_url"]
    assert captured["kwargs"]["headers"]["Authorization"] == "Bearer sk-form-key"
    # OpenRouter's model_format prefixes the vendor: stored `openrouter|gpt-4o-mini`
    # must go out as the OpenRouter slug `openai/gpt-4o-mini`.
    assert captured["kwargs"]["json"]["model"] == "openai/gpt-4o-mini"


def test_ask_llm_uses_custom_endpoint_and_legacy_key(monkeypatch):
    settings = _Settings(
        llm_provider="custom", custom_api_base_url="http://10.0.0.5:8000/v1/chat/completions",
        llm_api_key="legacy-key", default_llm_model="my-model",
    )
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, kwargs=kwargs)
        return _fake_response()

    llm = _import_llm(monkeypatch, settings, post=fake_post)

    assert llm.ask_llm("hi") == "ok"
    assert captured["url"] == "http://10.0.0.5:8000/v1/chat/completions"
    assert captured["kwargs"]["headers"]["Authorization"] == "Bearer legacy-key"
    assert captured["kwargs"]["json"]["model"] == "my-model"


def test_validate_deployment_settings_blocks_release_blockers(monkeypatch):
    llm = _import_llm(monkeypatch, _Settings())

    # Hosted provider without a key — the assistant cannot authenticate
    err = llm.validate_deployment_settings(_Settings(llm_provider="openai"))
    assert err and "API key" in err

    # Custom endpoint without a base URL
    err = llm.validate_deployment_settings(_Settings(llm_provider="custom"))
    assert err and "base URL" in err

    # Unknown provider stored in the DB
    err = llm.validate_deployment_settings(_Settings(llm_provider="skynet"))
    assert err and "Unknown LLM provider" in err

    # Non-numeric / non-positive runtime knobs
    err = llm.validate_deployment_settings(_Settings(llm_provider="ollama", timeout_seconds="soon"))
    assert err and "whole number" in err
    err = llm.validate_deployment_settings(_Settings(llm_provider="ollama", max_tokens=0))
    assert err and "at least 1" in err

    # Complete configuration passes
    assert llm.validate_deployment_settings(
        _Settings(llm_provider="ollama", timeout_seconds=120, max_tokens=2048)) is None
