#!/bin/sh
# Start Ollama server in the background, wait for it to be ready,
# then pull the configured model if not already cached.

set -e

MODEL="${OLLAMA_MODEL:-llama3.1:8b}"

echo "[entrypoint] Starting Ollama server..."
ollama serve &
SERVER_PID=$!

# Wait until the server is accepting connections
echo "[entrypoint] Waiting for Ollama server to be ready..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 2
done
echo "[entrypoint] Ollama server is ready."

# Pull the model if it's not already present
if ollama list | grep -q "^${MODEL}"; then
    echo "[entrypoint] Model '${MODEL}' already cached, skipping pull."
else
    echo "[entrypoint] Pulling model '${MODEL}' (this may take several minutes on first run)..."
    ollama pull "${MODEL}"
    echo "[entrypoint] Model '${MODEL}' pulled successfully."
fi

echo "[entrypoint] Ollama is ready and serving '${MODEL}'."

# Keep the container alive by waiting on the server process
wait $SERVER_PID
