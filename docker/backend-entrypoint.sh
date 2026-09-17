#!/bin/bash
set -e

echo "Starting FOS backend..."

# Best-effort: ensure the embedding model is available, but never block startup.
# Pulling runs in the background; a failed or timed-out pull only logs a warning.
OLLAMA_URL="${OLLAMA_BASE_URL:-http://fos-ollama:11434}"
OLLAMA_MODEL="${FOS_OLLAMA_EMBED_MODEL:-nomic-embed-text:latest}"

(
    if curl -fsS --max-time 10 "${OLLAMA_URL}/api/tags" | grep -q "\"${OLLAMA_MODEL}\""; then
        echo "Embedding model '${OLLAMA_MODEL}' already present."
    else
        echo "Pulling embedding model '${OLLAMA_MODEL}' in background (first run may take a few minutes)..."
        curl -fsS --max-time 1800 "${OLLAMA_URL}/api/pull" -d "{\"name\":\"${OLLAMA_MODEL}\"}" \
            && echo "Embedding model '${OLLAMA_MODEL}' pulled successfully." \
            || echo "WARNING: could not pull '${OLLAMA_MODEL}'. Uploads will fail until pulled manually: docker exec fos-ollama ollama pull ${OLLAMA_MODEL}"
    fi
) &

echo "Running database migrations..."
alembic upgrade head || echo "Migration skipped or failed"

echo "Starting Uvicorn server..."
exec uvicorn fos.backend.main:app \
    --host ${FOS_BACKEND_HOST:-0.0.0.0} \
    --port ${FOS_BACKEND_PORT:-8000} \
    --root-path ${FOS_BACKEND_ROOT_PATH:-} \
    --workers ${FOS_UVICORN_WORKERS:-1} \
    --timeout-keep-alive 75
