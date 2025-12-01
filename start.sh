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

echo "Running diagnostic check..."
python -c "try: import deepgram; print(f'Deepgram dir: {dir(deepgram)}'); from deepgram import DeepgramClient; print('DeepgramClient imported'); except Exception as e: print(f'Diagnostic Error: {e}'); import traceback; traceback.print_exc()"

# Run uvicorn
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
