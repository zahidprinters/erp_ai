#!/usr/bin/env bash
# ERP AI voice stack installer — run once on any Debian/Ubuntu Frappe machine.
# Provisions: build deps, Ollama, whisper.cpp, piper, EN+UR voices, whisper model.
set -e
AI_HOME="${AI_HOME:-$HOME/ai}"
mkdir -p "$AI_HOME/models" "$AI_HOME/tmp"
UA='Mozilla/5.0 (X11; Linux x86_64)'

echo "== [1/6] system packages =="
sudo apt-get update -qq
sudo apt-get install -y build-essential cmake git curl alsa-utils

echo "== [2/6] Ollama (AI engine, CPU) =="
if ! command -v ollama >/dev/null; then
	curl -fsSL https://ollama.com/install.sh | sudo bash
fi
sudo systemctl enable --now ollama || true
sudo -u "$(logname 2>/dev/null || echo root)" ollama pull qwen2.5:1.5b || ollama pull qwen2.5:1.5b || true

echo "== [3/6] whisper.cpp (speech-to-text) =="
if [ ! -x "$AI_HOME/whisper.cpp/build/bin/whisper-cli" ]; then
	rm -rf "$AI_HOME/whisper.cpp"
	git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git "$AI_HOME/whisper.cpp"
	cmake -B "$AI_HOME/whisper.cpp/build" -S "$AI_HOME/whisper.cpp" \
		-DWHISPER_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release
	cmake --build "$AI_HOME/whisper.cpp/build" -j"$(nproc)"
fi

echo "== [4/6] whisper model (tiny, multilingual) ="
if [ ! -f "$AI_HOME/models/ggml-tiny.bin" ]; then
	curl -sL -A "$UA" 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin' \
		-o "$AI_HOME/models/ggml-tiny.bin"
fi

echo "== [5/6] piper TTS + voices (English & Urdu) ="
if [ ! -x "$AI_HOME/piper/piper" ]; then
	curl -sL -A "$UA" 'https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz' \
		-o /tmp/piper.tar.gz
	tar xzf /tmp/piper.tar.gz -C "$AI_HOME"
fi
[ -f "$AI_HOME/models/en_US-lessac-medium.onnx" ] || curl -sL -A "$UA" \
	'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx' \
	-o "$AI_HOME/models/en_US-lessac-medium.onnx"
[ -f "$AI_HOME/models/en_US-lessac-medium.onnx.json" ] || curl -sL -A "$UA" \
	'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json' \
	-o "$AI_HOME/models/en_US-lessac-medium.onnx.json"
if [ ! -f "$AI_HOME/models/ur_PK-fasih-medium.onnx" ]; then
	for q in medium high; do
		if curl -fsL -A "$UA" "https://huggingface.co/rhasspy/piper-voices/resolve/main/ur/ur_PK/fasih/$q/ur_PK-fasih-$q.onnx" \
			-o "$AI_HOME/models/ur_PK-fasih-$q.onnx"; then
			curl -sL -A "$UA" "https://huggingface.co/rhasspy/piper-voices/resolve/main/ur/ur_PK/fasih/$q/ur_PK-fasih-$q.onnx.json" \
				-o "$AI_HOME/models/ur_PK-fasih-$q.onnx.json"
			break
		fi
	done
fi

echo "== [6/6] done =="
echo "Runtime root: $AI_HOME"
echo "Voice assistant: python3 <bench>/apps/erp_ai/erp_ai/voice/voice_assistant.py"
echo "AI model ready: $(ollama list 2>/dev/null | grep -c qwen) qwen model(s)"
