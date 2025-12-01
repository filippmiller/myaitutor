# Voice Connection Debugging Guide

## What Changed

Added comprehensive logging to both frontend and backend to diagnose WebSocket connection issues.

## Frontend Logging (Browser Console)

When you click "Start Live Lesson", you'll now see detailed logs with emojis:

### Connection Flow:
1. 🚀 `[START LESSON] Initiating...` - Button clicked
2. 🎤 `[MICROPHONE] Requesting access...` - Asking for mic permission
3. ✅ `[MICROPHONE] Access granted` - User allowed mic
4. 🔌 `[WEBSOCKET] Creating connection to: ws://...` - WebSocket URL
5. ⏳ `[STATE] Connection status: Connecting...` - Status update
6. ✅ `[WEBSOCKET] Connection OPENED` - WebSocket connected
7. 🎙️ `[STATE] Connection status: Connected, Recording started`
8. 🎬 `[RECORDER] MediaRecorder created`
9. ▶️ `[RECORDER] Started (250ms chunks)`

### During Conversation:
- 📤 `[AUDIO] Sending chunk: X bytes` - Audio being sent to server
- 📨 `[WEBSOCKET] Received text message: {...}` - Server response (transcript)
- 💬 `[TRANSCRIPT] role: text` - Transcript message
- 📨 `[WEBSOCKET] Received binary message (audio)` - AI audio response
- 🔊 `[AUDIO] Playing AI response`

### On Disconnect:
- ❌ `[WEBSOCKET] Connection CLOSED - Code: XXXX, Reason: ...`
- 🛑 `[STATE] Connection status: Disconnected, Recording stopped`

### On Error:
- 💥 `[WEBSOCKET] ERROR: ...`
- ⚠️ `[STATE] Connection status: Error`

## Backend Logging (Terminal)

The backend now logs with emojis too:

### On Connection Attempt:
```
================================================================================
🔌 [WEBSOCKET] New connection attempt
✅ [WEBSOCKET] Connection accepted
🔑 [AUTH] Token found: True/False
✅ [AUTH] User authenticated: email@example.com
✅ [SETTINGS] API keys present - Deepgram: True, OpenAI: True
✅ [SESSION] Lesson session created: 123
✅ [DEEPGRAM] SDK available
Initializing Deepgram...
Starting Deepgram connection...
Deepgram connected, listening...
```

### On Error:
- ❌ `[AUTH] Authentication failed - closing connection`
- ❌ `[SETTINGS] Missing API keys`
- ❌ `[DEEPGRAM] SDK not available`

## Health Check Endpoint

You can test prerequisites before even attempting connection:

```bash
curl http://localhost:8000/api/voice-lesson/health
```

Response:
```json
{
  "deepgram_available": true,
  "deepgram_client": true,
  "settings_exist": true,
  "deepgram_key_set": true,
  "openai_key_set": true
}
```

## How to Debug

1. **Open browser DevTools** (F12)
2. Go to **Console** tab
3. Clear the console
4. Click **"Start Live Lesson"**
5. **Watch the logs** - they'll tell you exactly where it's failing

### Common Issues to Look For:

#### If you see "Connecting..." then immediate disconnect:
- Check the `CLOSED` log - it will show the **error code and reason**
- Common codes:
  - `1008` - Unauthorized (session expired or missing)
  - `1011` - Server error (check backend logs)

#### If microphone fails:
- You'll see `💥 [ERROR] Failed to start lesson`
- Browser may have blocked microphone access

#### If no logs appear at all:
- Frontend build might not have updated - refresh the page (Ctrl+F5)

## Testing Steps

1. Check health endpoint: `/api/voice-lesson/health`
2. Open browser console before clicking button
3. Click "Start Live Lesson"
4. Read the logs from top to bottom
5. Share the logs if you need help diagnosing
