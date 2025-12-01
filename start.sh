#!/bin/sh
# Fix line endings just in case
sed -i 's/\r$//' "$0"

echo "Starting application..."
echo "Current directory: $(pwd)"
echo "Listing frontend/dist:"
ls -la frontend/dist || echo "frontend/dist NOT FOUND"

# Default to 8080 if PORT is not set
PORT="${PORT:-8080}"
echo "Using PORT: $PORT"

# Run uvicorn
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
