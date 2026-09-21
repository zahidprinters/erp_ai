# ---------------------------------------------------------------------------
# Voice interface — speech-to-text and text-to-speech.
#
# Single responsibility: convert between spoken audio and text.
# Uses local Whisper (STT) and Piper (TTS). No ERP logic.
# ---------------------------------------------------------------------------
import os
import subprocess
from typing import Any, Dict


def _ai_home():
	"""Resolve the voice-stack runtime root."""
	env = os.environ.get("AI_HOME")
	cands = []
	if env:
		cands.append(env)
	cands += [os.path.join(os.path.expanduser("~"), "ai"), "/home/erpnext/ai"]
	for c in cands:
		whisper = os.path.join(c, "whisper.cpp/build/bin/whisper-cli")
		if os.path.exists(whisper):
			return c
	# An explicitly configured root wins over the hardcoded guess: the previous
	# fallback silently wrote temp files under /home/erpnext/ai even when
	# AI_HOME pointed somewhere else (and often un-creatable).
	return env or cands[-1]


ALLOWED_AUDIO_FORMATS = frozenset({"webm", "wav", "mp3", "ogg", "m4a", "flac"})

# Hard bounds (audit point 16). A wedged decoder or an oversized upload must not
# hang a worker or exhaust the disk, so every subprocess is bounded and every
# input has a ceiling.
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # matches the attachment intake cap
MAX_TTS_CHARS = 1000
FFMPEG_TIMEOUT = 30
WHISPER_TIMEOUT = 120
TTS_TIMEOUT = 30

# Phase 2.1 — per-stage timeout budget for the voice round trip.
# A voice call completes or fails within a bounded time: every subprocess
# stage has its own ceiling (above), the pre/post-conversion stages are
# trivial, and the LLM stage in the combined path shares the Phase 1.1
# discipline (settings timeout clamped to OLLAMA_TIMEOUT_CEILING).
STAGE_BUDGET = {
	"convert": FFMPEG_TIMEOUT,
	"stt": WHISPER_TIMEOUT,
	"tts": TTS_TIMEOUT,
}


def voice_stage_budget() -> Dict[str, int]:
	"""Return the per-stage timeout budget (seconds) for the voice path."""
	return dict(STAGE_BUDGET)


def voice_runtime_available() -> Dict[str, Any]:
	"""Report whether the local voice runtime (STT + TTS) is provisioned.

	Lets endpoints say "voice is unavailable: <what's missing>" instead of
	failing mid-subprocess with a decoder error. Never raises, never runs a
	subprocess — pure filesystem checks.
	"""
	home = _ai_home()
	whisper_bin = os.path.join(home, "whisper.cpp/build/bin/whisper-cli")
	whisper_model = os.path.join(home, "models/ggml-tiny.bin")
	piper_bin = os.path.join(home, "piper/piper")
	tts_model_en = os.path.join(home, "models/en_US-lessac-medium.onnx")

	missing = []
	if not os.path.exists(whisper_bin):
		missing.append("whisper.cpp runtime (whisper-cli)")
	if not os.path.exists(whisper_model):
		missing.append("whisper model (ggml-tiny.bin)")
	if not os.path.exists(piper_bin):
		missing.append("piper runtime")
	if not os.path.exists(tts_model_en):
		missing.append("piper voice model (en_US-lessac-medium.onnx)")
	import shutil as _shutil

	if not _shutil.which("ffmpeg"):
		missing.append("ffmpeg on PATH")
	return {"ok": not missing, "missing": missing, "home": home}


def _private_tmp_dir(home):
	"""Create and lock down the voice working directory.

	Uploaded audio and synthesised speech are private data: they were written to
	a default-permission directory (and TTS straight into world-writable
	``/tmp``), so any local user could read them.
	"""
	tmp = os.path.join(home, "tmp")
	os.makedirs(tmp, exist_ok=True)
	try:
		os.chmod(tmp, 0o700)
	except OSError:
		pass
	return tmp


def voice_to_text(audio_bytes: bytes, fmt: str = "webm") -> Dict[str, Any]:
	"""Convert audio bytes to text using local Whisper."""
	import frappe

	if not audio_bytes:
		return {"error": "No audio provided"}

	if fmt not in ALLOWED_AUDIO_FORMATS:
		return {"error": "Unsupported audio format: %s" % fmt}

	if len(audio_bytes) > MAX_AUDIO_BYTES:
		return {"error": "Audio too large: %d bytes (limit %d)" % (len(audio_bytes), MAX_AUDIO_BYTES)}

	home = _ai_home()
	tmp = _private_tmp_dir(home)
	# Unique temp files per call to avoid collisions between concurrent users
	token = frappe.generate_hash(length=8)
	raw_path = os.path.join(tmp, "voice_in_%s.%s" % (token, fmt))
	wav_path = os.path.join(tmp, "voice_out_%s.wav" % token)
	# Cleanup is in a `finally`: it used to run only on the success path, so a
	# failed conversion or an unprovisioned runtime leaked both temp files.
	try:
		with open(raw_path, "wb") as handle:
			handle.write(audio_bytes)

		try:
			ffmpeg_result = subprocess.run(
				["ffmpeg", "-y", "-i", raw_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path],
				capture_output=True,
				timeout=FFMPEG_TIMEOUT,
			)
		except subprocess.TimeoutExpired:
			return {"error": "Audio conversion timed out after %ss" % FFMPEG_TIMEOUT}
		if ffmpeg_result.returncode != 0:
			return {
				"error": "Audio conversion failed: %s"
				% ffmpeg_result.stderr.decode("utf-8", errors="replace")[:200]
			}
		whisper = os.path.join(home, "whisper.cpp/build/bin/whisper-cli")
		model = os.path.join(home, "models/ggml-tiny.bin")
		if not (os.path.exists(whisper) and os.path.exists(model)):
			return {"error": "Whisper runtime not provisioned — run voice/setup_voice.sh"}
		env = dict(os.environ)
		env["LD_LIBRARY_PATH"] = os.path.dirname(whisper) + ":" + env.get("LD_LIBRARY_PATH", "")
		try:
			proc = subprocess.run(
				[whisper, "-m", model, "-f", wav_path, "-nt", "-np"],
				capture_output=True,
				text=True,
				env=env,
				timeout=WHISPER_TIMEOUT,
			)
		except subprocess.TimeoutExpired:
			return {"error": "Transcription timed out after %ss" % WHISPER_TIMEOUT}
		if proc.returncode != 0:
			return {"error": "Transcription failed: %s" % (proc.stderr or "").strip()[:200]}
		text = " ".join(l.strip() for l in proc.stdout.splitlines() if l.strip()).strip()
		return {"text": text or "(no speech detected)"}
	finally:
		# `path`, not `p`: the old loop variable shadowed the subprocess result.
		for path in (raw_path, wav_path):
			try:
				os.remove(path)
			except OSError:
				pass


def text_to_speech(text: str, lang: str = "en") -> Dict[str, Any]:
	"""Convert text to speech using local Piper TTS."""
	import shutil

	import frappe

	if not text:
		return {"error": "No text provided"}

	# Unbounded input meant one long caption could pin a worker inside piper.
	if len(text) > MAX_TTS_CHARS:
		return {"error": "Text too long: %d characters (limit %d)" % (len(text), MAX_TTS_CHARS)}

	home = _ai_home()
	if lang == "ur":
		model = os.path.join(home, "models/ur_PK-fasih-medium.onnx")
	else:
		model = os.path.join(home, "models/en_US-lessac-medium.onnx")

	if not os.path.exists(model):
		return {"error": "Voice model not found: %s" % model}

	filename = "tts_%s.wav" % frappe.generate_hash(length=8)
	# Private working directory: the file used to be written straight into
	# world-readable /tmp and was left behind whenever piper failed.
	output_path = os.path.join(_private_tmp_dir(home), filename)

	try:
		process = subprocess.run(
			[os.path.join(home, "piper/piper"), "--model", model, "--output_file", output_path],
			input=text.encode("utf-8"),
			capture_output=True,
			timeout=TTS_TIMEOUT,
		)
		if process.returncode != 0:
			return {"error": "TTS failed: %s" % process.stderr.decode()}
		public_path = frappe.utils.get_site_path("public", "files", "tts", filename)
		os.makedirs(os.path.dirname(public_path), exist_ok=True)
		shutil.move(output_path, public_path)
		return {"url": "/files/tts/" + filename, "text": text[:100]}
	except subprocess.TimeoutExpired:
		return {"error": "TTS timed out after %ss" % TTS_TIMEOUT}
	except Exception as e:
		return {"error": str(e)}
	finally:
		# A no-op once shutil.move has taken the file; removes a failed run's wav.
		try:
			os.remove(output_path)
		except OSError:
			pass


# ---------------------------------------------------------------------------
# Emergency voice stop surface
# ---------------------------------------------------------------------------
# Production voice paths (for example a future streaming TTS helper) can poll
# ``_voice_kill_requested()`` and abort as soon as it becomes true. ``interrupt_voice``
# is the public API for forcing that interrupt, and it also attempts to terminate
# any tracked TTS subprocess if one is currently known.


class _VoiceState:
	"""Minimal mutable voice state so the emergency-stop flag is inspectable."""


_VOICE_STATE = _VoiceState()
_VOICE_STATE._kill_requested = False
_VOICE_STATE._tts_proc = None


def interrupt_voice():
	"""Request immediate interruption of any in-flight voice operation.

	This is the public emergency-stop surface for voice. It sets a kill-requested
	flag and attempts to terminate a tracked subprocess if one is currently known.
	Any long-running voice helper should poll ``_voice_kill_requested()`` and abort
	when it becomes true.
	"""
	import signal

	_set_kill_requested(True)
	proc = getattr(_VOICE_STATE, "_tts_proc", None)
	if proc is not None and proc.poll() is None:
		try:
			proc.send_signal(signal.SIGTERM)
		except Exception:
			pass


def _voice_kill_requested():
	"""Current kill-requested state for voice operations."""
	return getattr(_VOICE_STATE, "_kill_requested", False)


def _set_kill_requested(value):
	_VOICE_STATE._kill_requested = bool(value)
