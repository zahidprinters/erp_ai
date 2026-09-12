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
    return cands[-1]


ALLOWED_AUDIO_FORMATS = frozenset({"webm", "wav", "mp3", "ogg", "m4a", "flac"})


def voice_to_text(audio_bytes: bytes, fmt: str = "webm") -> Dict[str, Any]:
    """Convert audio bytes to text using local Whisper."""
    import frappe
    if not audio_bytes:
        return {"error": "No audio provided"}

    if fmt not in ALLOWED_AUDIO_FORMATS:
        return {"error": "Unsupported audio format: %s" % fmt}

    home = _ai_home()
    tmp = os.path.join(home, "tmp")
    os.makedirs(tmp, exist_ok=True)
    # Unique temp files per call to avoid collisions between concurrent users
    token = frappe.generate_hash(length=8)
    raw_path = os.path.join(tmp, "voice_in_%s.%s" % (token, fmt))
    wav_path = os.path.join(tmp, "voice_out_%s.wav" % token)
    with open(raw_path, "wb") as f:
        f.write(audio_bytes)

    ffmpeg_result = subprocess.run(["ffmpeg", "-y", "-i", raw_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path], capture_output=True)
    if ffmpeg_result.returncode != 0:
        return {"error": "Audio conversion failed: %s" % ffmpeg_result.stderr.decode("utf-8", errors="replace")[:200]}
    whisper = os.path.join(home, "whisper.cpp/build/bin/whisper-cli")
    model = os.path.join(home, "models/ggml-tiny.bin")
    if not (os.path.exists(whisper) and os.path.exists(model)):
        return {"error": "Whisper runtime not provisioned — run voice/setup_voice.sh"}
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = os.path.dirname(whisper) + ":" + env.get("LD_LIBRARY_PATH", "")
    p = subprocess.run([whisper, "-m", model, "-f", wav_path, "-nt", "-np"], capture_output=True, text=True, env=env)
    text = " ".join(l.strip() for l in p.stdout.splitlines() if l.strip()).strip()
    # Clean up temp files
    for p in (raw_path, wav_path):
        try:
            os.remove(p)
        except OSError:
            pass
    return {"text": text or "(no speech detected)"}


def text_to_speech(text: str, lang: str = "en") -> Dict[str, Any]:
    """Convert text to speech using local Piper TTS."""
    import shutil

    import frappe
    if not text:
        return {"error": "No text provided"}

    home = _ai_home()
    if lang == "ur":
        model = os.path.join(home, "models/ur_PK-fasih-medium.onnx")
    else:
        model = os.path.join(home, "models/en_US-lessac-medium.onnx")

    if not os.path.exists(model):
        return {"error": "Voice model not found: %s" % model}

    filename = "tts_%s.wav" % frappe.generate_hash(length=8)
    output_path = os.path.join("/tmp", filename)

    try:
        process = subprocess.run(
            [os.path.join(home, "piper/piper"), "--model", model, "--output_file", output_path],
            input=text.encode("utf-8"), capture_output=True, timeout=30)
        if process.returncode != 0:
            return {"error": "TTS failed: %s" % process.stderr.decode()}
        public_path = frappe.utils.get_site_path("public", "files", "tts", filename)
        os.makedirs(os.path.dirname(public_path), exist_ok=True)
        shutil.move(output_path, public_path)
        return {"url": "/files/tts/" + filename, "text": text[:100]}
    except Exception as e:
        return {"error": str(e)}

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

