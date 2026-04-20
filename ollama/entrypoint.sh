#!/bin/sh
# Start Ollama server, wait for readiness, then pull both models if not cached.

set -e

TAILORING_MODEL="${OLLAMA_MODEL:-llama3.1:8b}"
SCORING_MODEL="${OLLAMA_SCORING_MODEL:-llama3.2:3b}"

echo "[entrypoint] Starting Ollama server..."
ollama serve &
SERVER_PID=$!

echo "[entrypoint] Waiting for Ollama server to be ready..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 2
done
echo "[entrypoint] Ollama server is ready."

for MODEL in "$TAILORING_MODEL" "$SCORING_MODEL"; do
    if ollama list | grep -q "^${MODEL}"; then
        echo "[entrypoint] Model '${MODEL}' already cached, skipping pull."
    else
        echo "[entrypoint] Pulling model '${MODEL}'..."
        ollama pull "${MODEL}"
        echo "[entrypoint] Model '${MODEL}' pulled successfully."
    fi
done

echo "[entrypoint] Ollama is ready."
wait $SERVER_PID
