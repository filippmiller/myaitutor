# AIlingva Session Notes - January 15, 2026

## Session Overview

**Date:** 2026-01-15
**Participants:** Filipp Miller (User), Claude Opus 4.5 (AI Assistant)
**Focus:** Bug fixes, performance improvements, and feature additions for the AI English tutoring platform

---

## Issues Identified and Fixed

### 1. PROFILE_UPDATE Markers Being Voiced

**Problem:** During the onboarding/intro flow, the tutor was outputting `[PROFILE_UPDATE] {"tutor_name": "Варя"}` markers that were being spoken aloud by the OpenAI Realtime API TTS.

**Root Cause:** The Realtime API generates audio directly from model output - there's no separate text-to-speech step. Any text the model outputs gets vocalized.

**Solution Implemented:**
- Added **function calling** to the Realtime API session (`voice_ws.py:477-523`)
- Created `update_profile` function tool with parameters:
  - `tutor_name`, `student_name`, `addressing_mode`
  - `english_level_scale_1_10`, `goals`, `topics_interest`
  - `correction_style`, `intro_completed`
- Model now calls the function silently instead of outputting text markers
- Handler at `voice_ws.py:1050-1098` processes function calls and updates profile

**Files Changed:**
- `app/api/voice_ws.py` - Added function tool definition and handler
- `app/services/prompt_builder.py` - Updated FIRST_LESSON_INTRO to use function calls

**Code Reference:**
```python
# voice_ws.py:477-523
profile_update_tool = {
    "type": "function",
    "name": "update_profile",
    "description": "Save student profile information collected during the intro...",
    "parameters": {...}
}
```

---

### 2. Lesson Restart After Pause/Resume

**Problem:** When user clicked "Resume Lesson", the lesson restarted from scratch with "Hello Filipp Miller! Welcome to your first English lesson" instead of continuing where they left off.

**Root Cause:** The `should_run_intro_session()` function didn't consider the `is_resume` flag, so it triggered intro mode even when resuming a paused intro lesson.

**Solution Implemented:**
- Added `is_resume` check in greeting logic at `voice_ws.py:694-717`
- Three greeting paths now exist:
  1. `intro_mode && is_resume` → "RESUMING Onboarding" greeting with pause summary
  2. `intro_mode && !is_resume` → "First-Time Onboarding" greeting
  3. `!intro_mode` → Regular lesson greeting

**Files Changed:**
- `app/api/voice_ws.py` - Added resume detection in greeting trigger

**Code Reference:**
```python
# voice_ws.py:694-717
if intro_mode and is_resume:
    # Get pause summary for context
    context_hint = f" Before the break: {pause_summary}" if pause_summary else ""
    greeting_text = (
        f"System Event: RESUMING Onboarding.{context_hint} "
        "Welcome them back warmly and CONTINUE where you left off..."
    )
```

---

### 3. Voice Stuttering During Long Lessons

**Problem:** During extended lessons (20-30+ minutes), the tutor's voice began stuttering and breaking up.

**Root Cause:** The OpenAI Realtime API's `input_audio_buffer` was **never cleared**. Audio accumulated continuously during lessons, causing increasing latency and stuttering.

**Solution Implemented:**
- Added `input_audio_buffer.clear` events at key moments:
  1. When `response.created` (tutor starts speaking) - prevents echo
  2. When `response.done` (tutor finishes speaking) - clears accumulated audio
- Added logging for VAD events (`speech_started`, `speech_stopped`, `committed`)

**Files Changed:**
- `app/api/voice_ws.py` - Added buffer clearing at lines 952-971, 964-979

**Code Reference:**
```python
# voice_ws.py:964-971
# Clear input audio buffer after response to prevent accumulation
clear_buffer_event = {"type": "input_audio_buffer.clear"}
await openai_ws.send(json.dumps(clear_buffer_event))
```

---

### 4. "Speak Slowly" Request Not Persisting

**Problem:** User asked the tutor to "говори медленно" (speak slowly) multiple times during a lesson. The tutor acknowledged ("Буду говорить медленно") but immediately forgot and returned to normal speed.

**Root Cause:**
1. Realtime API doesn't persist preferences between responses
2. No mechanism to detect and save speech preferences
3. Rules aren't created dynamically from user requests

**Solution Implemented:**
Created new service `app/services/speech_preferences.py`:
- **Detection:** Regex patterns for RU/EN slow speech requests:
  - `говори медленн`, `помедленн`, `слишком быстр`
  - `speak slow`, `slow down`, `too fast`, `more slowly`
- **Persistence:** Creates `TutorRule` in database:
  - `scope="student"`, `type="speech_pace"`
  - `priority=100` (high)
  - Applied to all future lessons
- **Immediate Injection:** Rule is injected into active session via `conversation.item.create`

**Files Created:**
- `app/services/speech_preferences.py` - New service for preference detection

**Files Changed:**
- `app/api/voice_ws.py` - Added import and integration (lines 26, 935-959)

**Code Reference:**
```python
# speech_preferences.py
SLOW_SPEECH_PATTERNS = [
    r"говори\s*(по)?медленн",
    r"медленн\w*\s+говори",
    r"speak\s+slow",
    r"slow\s*down",
    ...
]

def get_or_create_slow_speech_rule(db, user_id):
    rule = TutorRule(
        scope="student",
        type="speech_pace",
        title="Speak Slowly",
        description="ВАЖНО: Этот ученик просил говорить МЕДЛЕННО...",
        priority=100,
        applies_to_student_id=user_id,
        ...
    )
```

---

## New Features Added

### 1. Function Calling for Profile Updates

**Feature:** Silent profile data collection during onboarding

**How It Works:**
1. Session configured with `update_profile` tool when `intro_mode=True`
2. Model calls function instead of outputting text markers
3. Handler processes function call, updates profile in database
4. Function result sent back, model continues conversation

**Benefits:**
- No more vocalized data markers
- Cleaner user experience
- Structured data collection

---

### 2. Speech Preference Persistence System

**Feature:** Automatic detection and persistence of user speech preferences

**How It Works:**
1. User says "говори медленно" or "slow down"
2. System detects via regex patterns
3. Creates persistent `TutorRule` in database
4. Injects rule into current session immediately
5. Rule loaded automatically in all future lessons

**Database Schema Used:**
```sql
tutor_rules (
    id, scope, type, title, description,
    priority, is_active, applies_to_student_id,
    created_by, source, ...
)
```

**Future Extensibility:**
- Can add more preference types (volume, formality, topics, etc.)
- Pattern-based detection system is modular

---

### 3. VAD Event Logging

**Feature:** Visibility into Voice Activity Detection events

**Events Now Logged:**
- `input_audio_buffer.speech_started` - User started speaking
- `input_audio_buffer.speech_stopped` - User stopped speaking
- `input_audio_buffer.committed` - Audio committed for processing

**Benefits:**
- Better debugging of audio issues
- Visibility into turn-taking behavior
- Foundation for future interruption handling

---

## Configuration Changes

### Environment Variables
- `OPENAI_API_KEY` now takes priority over database value (fixed in previous session)

### Feature Flags
- `USE_SMART_BRAIN = True` in `lesson_pipeline_manager.py`

---

## Files Modified Summary

| File | Changes |
|------|---------|
| `app/api/voice_ws.py` | Function calling, buffer clearing, resume handling, speech preferences |
| `app/services/prompt_builder.py` | Updated intro prompt for function calls |
| `app/services/speech_preferences.py` | **NEW** - Speech preference detection |
| `.gitignore` | Added `.claude/` to prevent secret commits |

---

## Commits Made

### Commit 1: `422b293`
```
fix: Use function calls for profile updates and fix lesson resume

Two bugs fixed:
1. PROFILE_UPDATE markers were being spoken aloud by the Realtime API
2. Lesson restart from scratch after pause/resume
```

### Commit 2: `63f1930`
```
fix: Clear audio buffer to prevent voice stuttering in long lessons

The OpenAI Realtime API's input_audio_buffer was never cleared, causing
audio to accumulate during long lessons.
```

### Commit 3: `51d2759`
```
feat: Add speech preference detection and persistence

When user asks "говори медленно" or "speak slowly", the system now:
1. Detects the request using regex patterns (RU/EN)
2. Creates a persistent TutorRule for the student
3. Injects the rule into the active session immediately
```

---

## Lesson Log Analysis

### Observations from User's Lesson:

1. **Topic:** Describing objects with colors and positions
   - "The phone is next to the black computer"
   - "The computer is black"

2. **Language Mix:** Tutor used Russian for explanations, English for practice
   - "Отлично, Филипп! Теперь добавь ещё один предмет рядом."
   - "Good job! Now put it all together..."

3. **Slow Speech Requests:** User asked 3+ times for slower speech
   - Tutor acknowledged each time but didn't persist the preference

4. **Audio Quality:** No stuttering observed in log timestamps (fixes working)

---

## Architecture Insights

### Dual-Pipeline Architecture (Existing)
- **STREAMING Pipeline:** Real-time voice interaction via OpenAI Realtime API
- **ANALYSIS Pipeline:** Background brain analysis for learning tracking

### Data Flow
```
User Speech → OpenAI Realtime → Tutor Response → Audio to Frontend
                                      ↓
                              LessonTurn saved
                                      ↓
                              Smart Brain analysis
                                      ↓
                              TutorBrainEvent created
```

### Key Models
- `LessonSession` - Voice lesson container
- `LessonTurn` - Individual conversation turns
- `TutorLesson` - New pipeline lesson tracking
- `TutorLessonTurn` - New pipeline turns
- `TutorRule` - Dynamic tutor behavior rules
- `TutorBrainEvent` - Brain analysis events

---

## Known Issues Remaining

### 1. Transcript Extraction Issue
**Location:** `voice_ws.py:230`
```
WARNING: response.output_item.done - no transcript found in item structure
```
The code looks for `type="audio"` but Realtime API returns `type="output_audio"`.

**Fix Needed:** Update condition to check both types.

### 2. Many Unhandled Event Types
Multiple events logged as "Unhandled":
- `response.content_part.added`
- `response.content_part.done`
- `conversation.item.added`
- `conversation.item.done`
- `rate_limits.updated`

**Recommendation:** Add handlers or suppress warnings for known-safe events.

### 3. User Transcript Often `null`
```json
{"type": "input_audio", "transcript": null}
```
User transcripts sometimes arrive as null. May need to handle `conversation.item.input_audio_transcription.completed` event.

---

## Recommendations for Future Sessions

### High Priority
1. **Fix transcript extraction** - Update `output_audio` detection
2. **Add repeat/pronunciation detection** - "повтори", "repeat that"
3. **Implement interruption handling** - When user speaks while tutor is talking

### Medium Priority
4. **Add volume preference** - "говори громче/тише"
5. **Implement topic preferences** - Save favorite topics for future lessons
6. **Add correction style detection** - "исправляй чаще/реже"

### Low Priority
7. **Clean up warning logs** - Handle or suppress known events
8. **Add analytics dashboard** - Track preference usage
9. **Implement A/B testing** - Test different prompt strategies

---

## Testing Checklist

- [x] Profile updates no longer vocalized
- [x] Lesson resumes correctly after pause
- [x] Audio buffer clearing prevents stuttering
- [x] "Speak slowly" creates persistent rule
- [ ] Rule injection works in active session (needs live testing)
- [ ] Rule persists across lesson sessions (needs live testing)

---

## Session Statistics

- **Duration:** ~2 hours
- **Files Modified:** 4
- **Files Created:** 1
- **Commits:** 3
- **Bugs Fixed:** 4
- **Features Added:** 3

---

*Document created: 2026-01-15*
*Author: Claude Opus 4.5 with Filipp Miller*
*Next review: After testing speech preference persistence*
