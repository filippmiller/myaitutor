# Deployment Troubleshooting Report

## Overview
This document details the current state of the deployment of the AIlingva application to Railway, highlighting successes, failures, and the specific technical blockers encountered.

## Current Status
**Status:** FAILED / CRASH LOOP
**Platform:** Railway
**Error:** The application fails to bind to the correct port and/or fails to serve the frontend assets.

## Successes
1.  **Codebase Readiness:**
    *   Full-stack application (FastAPI + React) is implemented.
    *   Database models (SQLModel) and migrations are set up.
    *   Authentication and Progress tracking features are complete.
2.  **Configuration:**
    *   `Dockerfile` created to manage the build environment (Python + Node.js).
    *   `start.sh` script created to handle startup logic.
    *   Dependencies (`requirements.txt`) updated.

## Failures & Chronology

### 1. Initial Deployment Crashes
*   **Issue:** `No start command was found`.
*   **Attempted Fix:** Added `Procfile` with `web: uvicorn ...`.
*   **Outcome:** Resolved, but led to next error.

### 2. Missing Dependencies
*   **Issue:** `ImportError: email-validator is not installed`.
*   **Attempted Fix:** Added `email-validator` to `requirements.txt`.
*   **Outcome:** Resolved.

### 3. Static Directory Missing
*   **Issue:** `RuntimeError: Directory 'static' does not exist`.
*   **Reason:** Empty directories are ignored by Git.
*   **Attempted Fix:** Added code to create directory on startup and added `.gitkeep`.
*   **Outcome:** Resolved.

### 4. Frontend Build Not Found
*   **Issue:** The application started but logged: `Frontend build not found. Run 'npm run build'`.
*   **Reason:** The `Dockerfile` order was incorrect. It built the frontend, but then `COPY . .` overwrote the build artifacts with the local (unbuilt) directory.
*   **Attempted Fix:** Reordered `Dockerfile` to `COPY . .` *before* running `npm run build`.
*   **Outcome:** The build step now executes in the correct order, theoretically producing `frontend/dist`.

### 5. Port Binding Error (The Loop)
*   **Issue:** `Error: Invalid value for '--port': '$PORT' is not a valid integer.`
*   **Context:** Railway injects a `PORT` environment variable. Uvicorn needs this to bind.
*   **Attempted Fixes:**
    *   Changed `CMD` to shell form: `CMD uvicorn ... $PORT`.
    *   Created `start.sh` to explicitly handle the variable: `PORT="${PORT:-8080}"`.
    *   Updated `Dockerfile` to run `start.sh`.
    *   Fixed Windows line endings (`CRLF`) in `start.sh` using `sed`.
*   **Current State:** The error persists in the logs. This suggests that either:
    *   The `start.sh` script is not being executed as expected.
    *   The `$PORT` variable is not being passed correctly to the container's shell environment.
    *   There is a syntax error in how the command is defined in the Dockerfile/Procfile.

## The Specific Problem: Frontend Build & Startup
The user suspects the frontend is not being built. Here is the analysis:

1.  **Build Location:**
    *   The `Dockerfile` runs `npm run build` inside `/app/frontend`.
    *   Vite is configured to output to `dist`.
    *   Expected artifact location: `/app/frontend/dist`.

2.  **Serving Logic (`app/main.py`):**
    *   The Python app checks `if os.path.exists("frontend/dist")`.
    *   If found, it mounts it as a StaticFiles directory.
    *   If **NOT** found, it prints "Frontend build not found".

3.  **Why it might be failing:**
    *   If the application crashes immediately due to the **Port Error** (see #5), it never gets to the point of serving the frontend.
    *   If the Docker build context is somehow excluding `frontend/dist` (e.g., via `.dockerignore` incorrectly), it wouldn't exist.
    *   **Hypothesis:** The critical blocker is the **Port Error**. The app crashes on startup before it can even try to serve the frontend. The "Frontend build not found" error seen earlier was likely due to the overwrite issue (Failure #4), which was fixed, but we can't verify the fix because the app won't start.

## Code Examples

**Current `Dockerfile`:**
```dockerfile
FROM python:3.11-slim
# ... install node ...
WORKDIR /app
COPY . .
RUN pip install ...
WORKDIR /app/frontend
RUN npm install && npm run build
WORKDIR /app
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh
CMD ["./start.sh"]
```

**Current `start.sh`:**
```bash
#!/bin/sh
sed -i 's/\r$//' "$0"
echo "Listing frontend/dist:"
ls -la frontend/dist || echo "frontend/dist NOT FOUND"
PORT="${PORT:-8080}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
```

**Recommendation for "Smart Friend":**
Check why the `PORT` variable isn't expanding. It behaves as if the literal string `"$PORT"` is being passed to uvicorn instead of the numeric value. This often happens with `CMD ["exec", "form"]` vs `CMD shell form`, or if the shell itself isn't processing the expansion.
