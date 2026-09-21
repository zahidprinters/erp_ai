# ---------------------------------------------------------------------------
# Attachment & OCR utilities — handle file uploads and text extraction.
#
# Supports: image OCR (tesseract), PDF text extraction, file validation.
# Used for: invoice scanning, receipt OCR, document attachments.
# ---------------------------------------------------------------------------
import os
from typing import Any, Dict, Optional

ALLOWED_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "gif", "webp", "bmp", "pdf", "txt"})
ALLOWED_MIME_TYPES = frozenset(
	{
		"image/png",
		"image/jpeg",
		"image/gif",
		"image/webp",
		"image/bmp",
		"application/pdf",
		"text/plain",
	}
)
MAX_FILE_SIZE_MB = 10
ALLOWED_BASE_DIR = "/tmp/erp_ai_uploads"

# Magic-byte signatures for MIME sniffing (not just filename extension).
_MAGIC_SIGNATURES = (
	(b"\x89PNG\r\n\x1a\n", "image/png"),
	(b"\xff\xd8\xff", "image/jpeg"),
	(b"GIF87a", "image/gif"),
	(b"GIF89a", "image/gif"),
	(b"RIFF", "image/webp"),  # WEBP frames start with RIFF....WEBP
	(b"BM", "image/bmp"),
	(b"%PDF-", "application/pdf"),
)


def _sniff_mime(head: bytes) -> Optional[str]:
	"""Detect MIME type from file magic bytes (first 16 bytes)."""
	for sig, mime in _MAGIC_SIGNATURES:
		if head.startswith(sig):
			if mime == "image/webp":
				return mime if head[8:12] == b"WEBP" else None
			return mime
	if not head:
		return None
	try:
		head.decode("utf-8")
		return "text/plain"
	except UnicodeDecodeError:
		return None


def validate_file(
	filename: str, size_bytes: int, mime_type: str = None, content_head: bytes = None
) -> Optional[str]:
	"""Validate file type, size, MIME, and magic-byte signature.

	Returns error message or None.
	"""
	if not filename:
		return "No filename provided"
	if size_bytes < 0:
		return "Invalid file size"
	if size_bytes > MAX_FILE_SIZE_MB * 1024 * 1024:
		return "File too large: %.1f MB (max %d MB)" % (size_bytes / (1024 * 1024), MAX_FILE_SIZE_MB)
	ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
	if ext not in ALLOWED_EXTENSIONS:
		return "File type not allowed: .%s (allowed: %s)" % (ext, ", ".join(sorted(ALLOWED_EXTENSIONS)))
	if mime_type and mime_type not in ALLOWED_MIME_TYPES:
		return "MIME type not allowed: %s" % mime_type
	# Sniff magic bytes so filename spoofing (.pdf renamed from a shell script) fails.
	if content_head is not None:
		sniffed = _sniff_mime(content_head[:16])
		if sniffed is None:
			return "File content is not a recognized image/PDF/text file"
		umime = (mime_type or "").lower()
		if umime and sniffed != umime:
			return "MIME type %s does not match file signature %s" % (umime, sniffed)
	return None


def _is_within(base_dir: str, path: str) -> bool:
	"""Canonical containment check: is ``path`` inside ``base_dir``?

	The previous string ``startswith`` comparison treats the sibling directory
	``/tmp/erp_ai_uploads_evil`` as being inside ``/tmp/erp_ai_uploads``.
	"""
	base_real = os.path.realpath(base_dir)
	try:
		return os.path.commonpath([base_real, os.path.realpath(path)]) == base_real
	except ValueError:
		# Mixed absolute/relative paths or different drives -> not contained.
		return False


def _ensure_base_dir(base_dir: str) -> bool:
	"""Create the upload dir private to this process user. Returns False if unsafe.

	``/tmp`` is world-writable, so the directory must not be readable by other
	local users; and if it already exists owned by somebody else they could read
	our uploads or have pre-created a symlink for us to write through, so we
	refuse to use it.
	"""
	try:
		os.makedirs(base_dir, mode=0o700, exist_ok=True)
		st = os.stat(base_dir)
		if st.st_uid != os.getuid():
			return False
		if st.st_mode & 0o077:
			os.chmod(base_dir, 0o700)
		return True
	except OSError:
		return False


def _safe_path(base_dir: str, filename: str) -> Optional[str]:
	"""Resolve a safe file path, preventing directory traversal."""
	if not _ensure_base_dir(base_dir):
		return None
	safe_name = os.path.basename(filename)
	if not safe_name or safe_name.startswith("."):
		return None
	base_real = os.path.realpath(base_dir)
	full_path = os.path.realpath(os.path.join(base_real, safe_name))
	if not _is_within(base_real, full_path):
		return None
	return full_path


def _require_allowed_path(file_path: str) -> Optional[str]:
	"""Return an error message if the path escapes ALLOWED_BASE_DIR, else None."""
	real_path = os.path.realpath(file_path)
	if not _is_within(ALLOWED_BASE_DIR, real_path):
		return "File path not in allowed directory"
	if not os.path.exists(real_path) or not os.path.isfile(real_path):
		return "File not found: %s" % file_path
	return None


def extract_text_from_image(image_path: str) -> Dict[str, Any]:
	"""Extract text from an image using tesseract OCR."""
	import subprocess

	err = _require_allowed_path(image_path)
	if err:
		return {"error": err}
	try:
		result = subprocess.run(
			["tesseract", image_path, "stdout", "--psm", "6"], capture_output=True, text=True, timeout=60
		)
		if result.returncode != 0:
			return {"error": "OCR failed: %s" % result.stderr[:200]}
		return {"text": result.stdout.strip(), "confidence": "medium"}
	except FileNotFoundError:
		return {"error": "tesseract not installed — apt install tesseract-ocr"}
	except subprocess.TimeoutExpired:
		return {"error": "OCR timed out (60s)"}


def extract_text_from_pdf(pdf_path: str) -> Dict[str, Any]:
	"""Extract text from a PDF file."""
	err = _require_allowed_path(pdf_path)
	if err:
		return {"error": err}
	try:
		import subprocess

		result = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True, timeout=30)
		if result.returncode != 0:
			return {"error": "PDF extraction failed"}
		return {"text": result.stdout.strip()}
	except FileNotFoundError:
		return {"error": "pdftotext not installed — apt install poppler-utils"}


def extract_text_from_file(file_path: str) -> Dict[str, Any]:
	"""Extract text from a file based on its extension. Uses safe paths only."""
	# One gate for every extractor: this duplicated the containment check that
	# _require_allowed_path already performs.
	err = _require_allowed_path(file_path)
	if err:
		return {"error": err}
	ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
	if ext == "pdf":
		return extract_text_from_pdf(file_path)
	if ext in ("png", "jpg", "jpeg", "gif", "webp", "bmp"):
		return extract_text_from_image(file_path)
	if ext == "txt":
		try:
			with open(file_path, "r", encoding="utf-8", errors="replace") as f:
				return {"text": f.read()}
		except Exception as e:
			return {"error": str(e)}
	return {"error": "Unsupported file type: %s" % ext}


def cleanup_temp_files(max_age_seconds: int = 3600) -> int:
	"""Delete uploaded temp files older than max_age_seconds. Returns count removed."""
	removed = 0
	if not os.path.isdir(ALLOWED_BASE_DIR):
		return 0
	import time

	cutoff = time.time() - max_age_seconds
	for name in os.listdir(ALLOWED_BASE_DIR):
		full = os.path.join(ALLOWED_BASE_DIR, name)
		if os.path.isfile(full) and os.path.getmtime(full) < cutoff:
			try:
				os.remove(full)
				removed += 1
			except OSError:
				pass
	return removed


def parse_invoice_from_text(text: str) -> Dict[str, Any]:
	"""Parse extracted text for invoice-related fields."""
	import re

	result = {}
	m = re.search(r"(?:invoice|bill)\s*(?:no|number|#)?[:\s]*([A-Z0-9-]+)", text, re.I)
	if m:
		result["invoice_number"] = m.group(1)
	m = re.search(r"(?:date)[:\s]*(\d{4}-\d{2}-\d{2})", text, re.I)
	if m:
		result["date"] = m.group(1)
	m = re.search(r"(?:total|amount|grand total)[:\s]*[Rs\.]?\s*([0-9,.]+)", text, re.I)
	if m:
		result["total"] = float(m.group(1).replace(",", ""))
	return result
