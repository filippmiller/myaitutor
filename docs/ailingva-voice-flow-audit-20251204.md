# AIlingva Voice Flow Audit - 2025-12-04

## 1. Executive Summary
A critical bug preventing the voice lesson from starting (no greeting, no response) was identified and fixed. The root cause was a synchronization issue where the backend ignored the `lesson_started` event sent by the frontend. The fix ensures the backend waits for this event before triggering the initial greeting, guaranteeing that the frontend is ready to receive and play the audio.

## 2. Voice Pipeline Architecture

The voice lesson flow follows this pipeline:

1.  **Frontend (`Student.tsx`)**:
    - Connects to WebSocket (`/api/ws/voice`).
    - Sends `{"type": "config", ...}`.
    - Sends `{"type": "system_event", "event": "lesson_started"}` when ready.
    - Captures microphone audio and sends WebM chunks.
    - Plays received audio (TTS) and displays transcripts.

2.  **Backend (`voice_ws.py`)**:
    - **Realtime Session (OpenAI)**:
        - Proxies audio/text between Frontend and OpenAI Realtime API.
        - **Fix:** Listens for `lesson_started` to trigger the initial "Greet me" instruction to OpenAI.
    - **Legacy Session (Whisper + LLM + TTS)**:
        - Buffers audio -> VAD -> Whisper STT.
        - Sends text to OpenAI LLM (Chat Completion).
        - Synthesizes reply via OpenAI TTS or Yandex.
        - **Fix:** Listens for `lesson_started` to generate and send a static/dynamic greeting.

## 3. The Bug
- **Symptoms:** User clicks "Start", connection opens, but no greeting is heard. User speaks, audio is sent, but no reply comes back (or it's lost).
- **Root Cause:**
    - The frontend sends `lesson_started` to signal it's ready.
    - The backend **ignored** this event.
    - **Realtime:** It tried to greet immediately upon connection, potentially before the frontend was fully ready or subscribed, leading to a race condition or lost message.
    - **Legacy:** It had **no logic** to trigger a greeting at all, passively waiting for user input.

## 4. The Fix
- **File:** `app/api/voice_ws.py`
- **Changes:**
    - **`run_realtime_session`**: Removed the immediate greeting trigger. Added logic to intercept `lesson_started` JSON message and *then* send the greeting instruction to OpenAI.
    - **`run_legacy_session`**: Added logic to intercept `lesson_started` JSON message and immediately generate a greeting (text + audio) to send back to the client.

## 5. Debugging Tips
- **Logs:** Check Railway logs for "Received lesson_started".
    - Realtime: `Realtime: Received lesson_started. Triggering greeting...`
    - Legacy: `Legacy: Received lesson_started. Generating greeting...`
- **Frontend:** Check Browser Console for:
    - `✅ [WEBSOCKET] Connection OPENED`
    - `📨 [WEBSOCKET] Received: { type: 'transcript', ... }` (Text)
    - `🔊 [AUDIO] Received ... bytes` (Audio)
- **Common Failures:**
    - If "Connection OPENED" but no greeting: Backend didn't receive or process `lesson_started`.
    - If "Received transcript" but no sound: Audio decoding/playback issue in frontend (check `AudioContext`).
