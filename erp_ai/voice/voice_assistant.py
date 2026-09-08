#!/usr/bin/env python3
"""ERPNext Voice Assistant: mic -> Whisper -> Ollama -> Piper -> speaker.

Portable: all paths derive from $AI_HOME (default ~/ai).
Run `voice/setup_voice.sh` once to provision the runtime.

Usage:
  voice_assistant.py            # English loop (mic, 6s per turn)
  voice_assistant.py ur         # Urdu voice loop
  voice_assistant.py --text "Hi"# one-shot: text -> AI -> speech (no mic)
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

BASE = os.environ.get("AI_HOME", os.path.join(os.path.expanduser("~"), "ai"))
WHISPER = f"{BASE}/whisper.cpp/build/bin/whisper-cli"
PIPER = f"{BASE}/piper/piper"
LLM = os.environ.get("AI_MODEL", "qwen2.5:1.5b")
ERP_SITE = os.environ.get("ERP_SITE", "localhost")
ERP_TOKEN_FILE = f"{BASE}/.erp_token"
REC = f"{BASE}/tmp/rec.wav"
REPLY_WAV = f"{BASE}/tmp/reply.wav"

lang = "en"
oneshot = None
args = sys.argv[1:]
if args and args[0] == "--text":
    oneshot = args[1] if len(args) > 1 else "Hello"
else:
    lang = args[0] if args else "en"

stt_model = f"{BASE}/models/ggml-tiny.bin"
tts_model = (
    f"{BASE}/models/en_US-lessac-medium.onnx"
    if lang == "en"
    else f"{BASE}/models/ur_PK-fasih-medium.onnx"
)
os.makedirs(f"{BASE}/tmp", exist_ok=True)


def ask_llm(text):
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps({"model": LLM, "prompt": text, "stream": False}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)["response"].strip()


def speak(text, out=REPLY_WAV):
    p = subprocess.run(
        [PIPER, "-m", tts_model, "-f", out], input=text.encode(), capture_output=True
    )
    return p.returncode == 0


def transcribe(wav):
    p = subprocess.run(
        [WHISPER, "-m", stt_model, "-f", wav, "-nt", "-np"],
        capture_output=True,
        text=True,
    )
    lines = [l.strip() for l in p.stdout.splitlines() if l.strip()]
    return " ".join(lines).strip()


def play(wav):
    subprocess.run(["aplay", wav], capture_output=True)


def erp_query(text):
    """Route ERP questions (e.g. 'customer spi traders') to the erp_ai API."""
    m = re.search(r"customer\s+(.{2,60})", text, re.I) or re.search(
        r"کسٹمر\s+(.{2,60})", text
    )
    if not m:
        return None
    name = m.group(1).strip().strip("?.,!").strip()
    try:
        token = open(ERP_TOKEN_FILE).read().strip()
        qs = urllib.parse.urlencode({"doctype": "Customer", "name": name})
        headers = {"Authorization": f"token {token}"}
        if ERP_SITE != "localhost":
            headers["Host"] = ERP_SITE
        req = urllib.request.Request(
            f"http://localhost/api/method/erp_ai.api.summarize_doc?{qs}",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.load(r)["message"]["summary"]
    except Exception as e:
        print(f"(erp lookup failed: {e})")
        return None


def answer_and_speak(text):
    print("🤖 thinking...")
    reply = erp_query(text) or ask_llm(text)
    print(f"🤖 AI: {reply[:300]}")
    if speak(reply):
        play(REPLY_WAV)
    else:
        print("(tts failed)")


if oneshot:
    answer_and_speak(oneshot)
    sys.exit(0)

print(f"🎤 ERP Voice Assistant [{lang}] — press Ctrl+C to stop")
print("Speak after 'listening...' (6 seconds per turn)\n")
try:
    while True:
        print("🎤 listening...")
        subprocess.run(
            ["arecord", "-D", "default", "-f", "S16_LE", "-r", "16000", "-d", "6", REC],
            capture_output=True,
        )
        text = transcribe(REC)
        print(f"📝 You: {text or '(silence)'}")
        if not text:
            continue
        answer_and_speak(text)
except KeyboardInterrupt:
    print("\n👋 Assistant stopped.")
