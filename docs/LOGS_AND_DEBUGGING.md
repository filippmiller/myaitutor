# Logs and Debugging Inventory

This document lists where logs and debug artifacts live and how to view them.

## Production Logs (Railway)

Runtime logs (stdout/stderr):
- CLI: `railway logs`
- Filter last lines: `railway logs --lines 200`
- Build logs: `railway logs --build --lines 200`

These are the authoritative logs in production because the app runs on Railway.

## Voice Lesson Debug Logging

Backend toggle:
- `GET /api/admin/debug-settings`
- `POST /api/admin/debug-settings` with `{ "voice_logging_enabled": true }`

When enabled:
- OpenAI traffic is written to `static/openai_logs/lesson_<lesson_session_id>.jsonl`
- The student UI shows a debug console (WebSocket "debug" messages)

Note: The Railway filesystem is ephemeral; download logs if you need to keep them.

## Prompt Snapshots

Prompt snapshots (system prompt + greeting trigger):
- Files: `static/prompts/lesson_<lesson_session_id>_prompt.json`
- Admin API: `GET /api/admin/lesson-prompts` (optionally filtered by `user_id`)

These are written on every lesson start to help audit the prompt content.

## OpenAI Traffic Logs (Per Lesson)

Files:
- `static/openai_logs/lesson_<lesson_session_id>.jsonl`

Admin API:
- List available logs: `GET /api/admin/lesson-logs`
- Read a specific lesson: `GET /api/admin/lesson-logs?lesson_session_id=<id>`

## Frontend Diagnostics

- Browser console for UI/network errors.
- Student debug console shows WebSocket traffic when debug logging is enabled.

## Local Development Logs

- `uvicorn` output in the terminal running the backend.
- `uvicorn.log` exists in repo root if you run with file logging.

