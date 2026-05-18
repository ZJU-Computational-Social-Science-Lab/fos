#!/bin/bash
set -e

echo "Starting FOS backend..."

# Run database migrations
echo "Running database migrations..."
alembic upgrade head || echo "Migration skipped or failed"

# Start the application
echo "Starting Uvicorn server..."
exec uvicorn fos.backend.main:app \
    --host ${FOS_BACKEND_HOST:-0.0.0.0} \
    --port ${FOS_BACKEND_PORT:-8000} \
    --root-path ${FOS_BACKEND_ROOT_PATH:-}
