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
