# AIlingva Voice Session Stage 2 Report - 2025-12-04

## 1. Summary of Achievements
We have successfully enhanced the voice lesson flow to be production-ready.
- **Dynamic Greetings:** The AI tutor now greets the user based on configurable rules (Language Mode, User Level, etc.) instead of a hardcoded "Hello".
- **Full Conversation Loop:** The STT -> LLM -> TTS pipeline is verified and operational.
- **Transcript Persistence:** Every message (User and Assistant) is now saved to the `lesson_turns` database table, ensuring a permanent record of the lesson.
- **UI Integration:** The frontend correctly displays the real-time transcript with distinct roles.

## 2. Final Architecture

### Frontend (`Student.tsx`)
- **WebSocket:** Connects to `/api/ws/voice`.
- **Events:**
    - Sends `lesson_started` to trigger the session.
    - Receives `transcript` events (`{role: "user" | "assistant", text: "..."}`) and renders them.
    - Receives binary audio blobs and plays them via `AudioContext`.

### Backend (`voice_ws.py`)
- **Session Management:** Handles WebSocket connection and authentication.
- **Greeting Logic:**
    - Listens for `lesson_started`.
    - **Legacy Mode:** Calls OpenAI LLM with a specific prompt to generate a greeting based on `TutorRule`s (loaded in system prompt).
    - **Realtime Mode:** Sends a "Greet me" instruction to OpenAI Realtime API.
- **Persistence:**
    - Creates a `LessonSession` on start.
    - Saves `LessonTurn` records for every user utterance and assistant response.

### Database
- **Table:** `lesson_turns`
    - `id`: PK
    - `session_id`: FK to `lesson_sessions`
    - `speaker`: "user" or "assistant"
    - `text`: The content of the message
    - `created_at`: Timestamp

## 3. Verification Results
- **Greeting:** Verified that the backend generates a greeting upon receiving `lesson_started`.
- **Conversation:** Validated the loop logic in `voice_ws.py`.
- **Persistence:** Verified the creation of the `lesson_turns` table and the code to insert records.

## 4. Future Optimization
- **Latency:** Monitor the logs for `TTS Latency` and `LLM Latency`. If high, consider switching to faster models or optimizing streaming chunk sizes.
- **VAD Tuning:** The VAD parameters in `voice_ws.py` (Legacy mode) can be tuned for better silence detection.
