#!/usr/bin/env bash
set -e

echo "[CodLenz] Starting Ollama server in background..."
ollama serve > /tmp/ollama.log 2>&1 &

echo "[CodLenz] Waiting for Ollama to become available..."
until curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; do
    sleep 1
done

echo "[CodLenz] Checking models..."
if ! ollama list | grep -q "gemma3:4b"; then
    echo "[CodLenz] Downloading gemma3:4b (this may take a few minutes on first run)..."
    ollama pull gemma3:4b || {
        echo "[CodLenz] Gemma pull failed, falling back to qwen2.5:3b..."
        ollama pull qwen2.5:3b
    }
fi

echo "[CodLenz] Starting demo server on port 7860..."
exec python -m codelens.cli serve --port 7860
