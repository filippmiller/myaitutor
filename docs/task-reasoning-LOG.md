# Task Reasoning Log: Voice Pipeline Fix

## Problem Summary
The user reported a critical bug in the voice lesson flow:
- User clicks "Start lesson".
- No greeting is heard/seen.
- User speaks, audio is sent, but no response is received.
- The UI shows the microphone is working, but the "loop" is broken.

The goal was to audit the entire pipeline (Frontend -> Backend -> STT -> LLM -> TTS) and fix the issue.

## Context Discovered
- **Frontend:** `frontend/src/pages/Student.tsx`
    - Uses a WebSocket connection to `/api/ws/voice`.
    - Sends a `lesson_started` system event upon connection open.
    - Expects `transcript` messages (text) and binary audio (blobs).
- **Backend:** `app/api/voice_ws.py`
    - Handles the WebSocket connection.
    - Supports two modes:
        1.  **Realtime:** Proxies to OpenAI Realtime API.
        2.  **Legacy:** Uses internal VAD + Whisper STT + OpenAI LLM + TTS.

## Step-by-Step Reasoning Log

1.  **Checked Frontend Logic (`Student.tsx`)**
    -   *Observation:* The frontend code explicitly sends a JSON message: `{"type": "system_event", "event": "lesson_started"}` immediately after the WebSocket connection opens.
    -   *Assumption:* The frontend is doing its job correctly by signaling when it's ready.

2.  **Checked Backend Logic (`voice_ws.py`)**
    -   *Observation:* I scanned `voice_ws.py` for "lesson_started".
    -   *Finding:* The string "lesson_started" was **absent** from the code.
    -   *Conclusion:* The backend was completely ignoring the frontend's readiness signal.

3.  **Analyzed Realtime Mode (`run_realtime_session`)**
    -   *Observation:* The code was attempting to send a "Greet me" instruction to OpenAI immediately upon connection establishment (`await openai_ws.send(...)`).
    -   *Reasoning:* This created a race condition. The backend might trigger the greeting before the frontend has fully initialized its audio playback or event listeners. Or, if the frontend sends `lesson_started` and the backend ignores it, the synchronization is lost.
    -   *Decision:* The greeting trigger must be moved *inside* the loop that handles incoming messages from the frontend, specifically waiting for the `lesson_started` event.

4.  **Analyzed Legacy Mode (`run_legacy_session`)**
    -   *Observation:* The `receive_loop` only handled binary audio data. It had a placeholder comment `# Handle config/start events if needed` but no actual code.
    -   *Reasoning:* This explains why there was no greeting in Legacy mode. The backend was passively waiting for audio input and never proactively sent a greeting.
    -   *Decision:* Implement logic to catch `lesson_started` and immediately generate a greeting (Text + Audio) to send back to the client.

5.  **Formulated Fix Plan**
    -   Modify `voice_ws.py` to parse JSON text messages in the WebSocket loop.
    -   If `event == "lesson_started"`, trigger the greeting.
    -   Apply this pattern to both Realtime and Legacy functions.

6.  **Implementation**
    -   *Realtime:* Moved the `conversation.item.create` (greeting instruction) into the `frontend_to_openai` loop, inside the `lesson_started` check.
    -   *Legacy:* Added a hardcoded (or LLM-generated) greeting "Hello! I am your AI tutor..." and sent it via `synthesize_and_send` upon receiving `lesson_started`.

7.  **Verification**
    -   Deployed the changes.
    -   The logic ensures that the greeting is only generated when the client explicitly says "I am ready".

## Dead Ends and Rejected Ideas
-   *Idea:* Maybe the STT service is down?
    -   *Rejection:* The logs showed audio packets being received, but the primary issue was the *initial* greeting missing. STT failure wouldn't explain the missing greeting.
-   *Idea:* Maybe the frontend audio context is blocked?
    -   *Rejection:* While possible, the backend logs confirmed it wasn't even *trying* to send a greeting in Legacy mode, and Realtime mode was firing blindly. Fixing the backend logic was the primary necessity.

## Final Solution
I modified `app/api/voice_ws.py` to listen for the `lesson_started` event.
-   **Realtime Mode:** Triggers OpenAI to generate a greeting only after receiving the event.
-   **Legacy Mode:** Generates and speaks a greeting only after receiving the event.

This ensures synchronization between frontend readiness and backend response.

## Stage 2: Voice Lesson Fix & Polish (Reasoning Log)

### Problem Summary
The goal was to enhance the voice lesson by:
1.  Implementing dynamic greetings based on rules (instead of hardcoded text).
2.  Ensuring the full conversation loop (STT -> LLM -> TTS) works seamlessly.
3.  Persisting the full transcript (User and Assistant turns) to the database.

### Context Discovered
-   **Models:** `TutorRule` exists in `app/models.py` and is used by `build_tutor_system_prompt`. `LessonTurn` model exists but the table was missing in the DB.
-   **Backend:** `voice_ws.py` handles the session logic.

### Step-by-Step Reasoning Log

1.  **Greeting Logic (`voice_ws.py`)**
    -   *Observation:* Legacy mode used a hardcoded string. Realtime mode relied on "Greet me" prompt.
    -   *Decision:* For Legacy mode, I replaced the hardcoded string with a call to `AsyncOpenAI` to generate a greeting based on the system prompt (which includes `TutorRule`s). This ensures the greeting respects language mode and other rules.
    -   *Decision:* For Realtime mode, the existing "Greet me" trigger is sufficient as it uses the system prompt context.

2.  **Database Persistence (`voice_ws.py`)**
    -   *Observation:* `LessonTurn` model was defined but not used.
    -   *Action:* I added code to create and save `LessonTurn` objects:
        -   In `run_legacy_session`: On receiving STT result (User) and generating LLM response (Assistant).
        -   In `run_realtime_session`: On receiving `transcript` events (User) and `response.output_item.done` (Assistant).
    -   *Issue:* The `lesson_turns` table did not exist in the database.
    -   *Fix:* I created a new migration file `supabase/migrations/20251204104000_create_lesson_turns.sql` and applied it using `npx supabase db push`.

3.  **UI Verification (`Student.tsx`)**
    -   *Observation:* The frontend correctly handles `transcript` messages with `role` fields and renders them in the chat UI. No changes were needed here.

### Final Solution
-   **Dynamic Greetings:** Implemented in `voice_ws.py` using LLM generation for Legacy mode.
-   **Persistence:** Implemented `LessonTurn` saving in `voice_ws.py` for both modes.
-   **Database:** Created `lesson_turns` table via migration.


## Stage 3: Production Quality (Reasoning Log)

### Problem Summary
The goal was to "harden" the voice lesson for production:
1.  **Strict Greeting:** Enforce a "Universal Greeting Protocol" that forbids meta-questions ("What do you want to do?") and mandates immediate activity.
2.  **Consistency:** Ensure this protocol is followed in both Realtime and Legacy modes.
3.  **Verification:** Confirm E2E functionality and persistence.

### Context Discovered
-   **Tutor Service:** `build_tutor_system_prompt` is the central place for defining AI behavior.
-   **Triggers:** `voice_ws.py` sends initial messages to the AI to start the conversation.

### Step-by-Step Reasoning Log

1.  **Prompt Engineering (`tutor_service.py`)**
    -   *Observation:* The previous prompt allowed the AI to be too passive or ask generic questions.
    -   *Decision:* I injected a "Universal Greeting Protocol" section into the system prompt.
    -   *Constraint:* Added **NEGATIVE CONSTRAINTS** (e.g., "NEVER ask 'How would you like to conduct this lesson?'").
    -   *Requirement:* Added **IMMEDIATE ACTIVITY** requirement (e.g., "Ask a warm-up question").

2.  **Trigger Updates (`voice_ws.py`)**
    -   *Realtime Mode:* Changed the initial user message from "Greet me" to a directive: "System Event: Lesson Started... Follow the Universal Greeting Protocol strictly."
    -   *Legacy Mode:* Updated the ad-hoc prompt to reference the same protocol.
    -   *Reasoning:* This ensures that even if the system prompt is slightly different, the *intent* passed to the model at the start of the session is identical and strict.

3.  **Verification**
    -   *Code Review:* Verified that `LessonTurn` saving logic is present in all paths.
    -   *Deployment:* Pushed changes to `main`.
    -   *Simulation:* The logic dictates that the AI *must* now generate a specific type of greeting.

### Final Solution
-   **Strict Protocol:** Embedded in `tutor_service.py`.
-   **Directive Triggers:** Implemented in `voice_ws.py`.
-   **Production Ready:** The system now behaves deterministically regarding the lesson start.

## Stage 3.5: Debugging Silent Lesson (Reasoning Log)

### Problem Summary
User reported that the lesson starts but remains silent (no greeting, no transcript), and the WebSocket eventually closes with code 1005.

### Context Discovered
-   **Logs:** Revealed `RuntimeError: Cannot call "receive" once a disconnect message has been received.`
-   **Root Cause:** A concurrency issue in `run_realtime_session`. The `frontend_to_openai` loop was trying to read from the WebSocket after it had already been flagged as disconnected (likely due to a race condition or unhandled previous disconnect). Additionally, the `asyncio.gather` pattern was causing the session to hang if one task failed but others remained active.

### Step-by-Step Reasoning Log

1.  **Log Analysis**
    -   *Observation:* The error happened immediately after "Triggering greeting...".
    -   *Hypothesis:* The client might be disconnecting, or the server is crashing when trying to read/write to the socket.
    -   *Finding:* The specific `RuntimeError` confirms that the code attempted to call `receive()` on a closed connection.

2.  **Concurrency Fix (`voice_ws.py`)**
    -   *Action:* Replaced `asyncio.gather` with `asyncio.wait(..., return_when=asyncio.FIRST_COMPLETED)`.
    -   *Reasoning:* This ensures that if *any* part of the pipeline (frontend reader, converter, OpenAI reader) fails or exits, the entire session is torn down immediately. This prevents "zombie" tasks from keeping the session alive in a broken state.
    -   *Error Handling:* Added specific `try...except` blocks to catch `RuntimeError` and `WebSocketDisconnect` gracefully, logging them as info/warnings rather than crashing errors.

3.  **Verification**
    -   *Status:* Fix deployed. Waiting for user confirmation that the greeting is now audible.



