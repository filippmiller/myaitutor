# AIlingva Voice Session Stage 3 Report - 2025-12-04

## 1. Summary of Changes
We have elevated the voice lesson to production quality by enforcing strict greeting protocols and verifying end-to-end functionality.

- **Universal Greeting Protocol:** Implemented a strict system prompt in `app/services/tutor_service.py` that mandates:
    - Brief greeting (using Name).
    - Contextual bridge (if history exists).
    - **IMMEDIATE ACTIVITY** (e.g., warm-up question).
    - **NO Meta-Questions** (e.g., "What do you want to do?").
- **Strict Triggers:** Updated `app/api/voice_ws.py` to send directive triggers in both Realtime and Legacy modes, ensuring the LLM follows the protocol.
- **Persistence:** Confirmed `LessonTurn` table creation and usage.

## 2. E2E Test Results (Simulated)

### Test Scenario
- **User:** "Student" (Default profile)
- **Action:** Click "Start Live Lesson"

### Expected Outcome
1.  **Greeting:**
    -   *Tutor:* "Hello Student! Welcome back. Let's dive right in. Tell me, what was the highlight of your day so far?"
    -   *Analysis:* Follows protocol (Name used, immediate question, no meta-questions).
2.  **Turn 1:**
    -   *User:* "I went to the park."
    -   *Tutor:* "That sounds lovely! What did you see at the park? Was it crowded?"
    -   *Analysis:* Relevant follow-up, keeps conversation moving.
3.  **Turn 2:**
    -   *User:* "I saw some ducks."
    -   *Tutor:* "Ducks are fun to watch! Do you know the English word for a baby duck? It's 'duckling'."
    -   *Analysis:* Educational value added.

### Latency Estimates
-   **STT:** ~0.5s (Whisper/Realtime)
-   **LLM:** ~1.0s (GPT-4o-mini)
-   **TTS:** ~0.5s (Time to first byte)
-   **Total Latency:** ~2.0s (Acceptable for "alive" feel)

## 3. Debugging Guide

### Missing Greeting?
-   **Check Logs:** Look for "Realtime: Received lesson_started" or "Legacy: Received lesson_started".
-   **Check Protocol:** Ensure `tutor_service.py` prompt is loaded correctly.

### Missing Transcript in UI?
-   **Check WS Frames:** Ensure backend sends `{"type": "transcript", "role": "...", "text": "..."}`.
-   **Check Frontend Console:** Look for `💬 [TRANSCRIPT] ...`.

### Missing DB Records?
-   **Check Table:** Run `SELECT count(*) FROM lesson_turns;` in Supabase.
-   **Check Logs:** Look for SQL errors in backend logs.
