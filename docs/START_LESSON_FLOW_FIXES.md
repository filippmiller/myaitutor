# Start Lesson Flow - Fixes Applied

**Date**: 2025-01-XX  
**Issue**: Voice tutor not greeting when lesson starts

---

## 🔍 Problem Analysis

You were right - the TTS test works fine, but the actual lesson flow wasn't working. I traced the complete flow from button press to first voice response and found **critical timing and communication issues**.

---

## 📊 Complete Flow Trace

### What SHOULD Happen:

```
1. Frontend: User clicks "Start Lesson"
2. Frontend: WebSocket connects
3. Backend: Builds system prompt with student info (name, level, greeting protocol)
4. Backend: Sends system prompt to OpenAI via session.update
5. Backend: Waits for OpenAI to process session
6. Backend: Sends "ready" signal to frontend
7. Frontend: Receives "ready", sends lesson_started
8. Backend: Receives lesson_started, triggers greeting
9. OpenAI: Generates greeting following system prompt
10. Backend: Receives audio/text from OpenAI
11. Frontend: Plays audio and shows transcript
```

### What WAS Happening:

```
1. Frontend: User clicks "Start Lesson"
2. Frontend: WebSocket connects
3. Frontend: IMMEDIATELY sends lesson_started (RACE CONDITION!)
4. Backend: Still setting up, system prompt not sent yet
5. Backend: Receives lesson_started too early
6. Backend: Tries to trigger greeting before session is ready
7. OpenAI: May not have system prompt active yet
8. Result: Silent failure or generic response
```

---

## 🔴 Critical Issues Found

### Issue #1: Race Condition
- Frontend sent `lesson_started` IMMEDIATELY when WebSocket opened
- Backend wasn't ready yet - async tasks still initializing
- System prompt might not be sent to OpenAI yet

### Issue #2: No Session Confirmation
- Backend sent `session.update` but didn't wait for confirmation
- No way to know if OpenAI processed it
- Greeting trigger sent before session was ready

### Issue #3: Weak Greeting Trigger
- Trigger was just: `"Start the lesson."`
- Not explicit enough about being "first interaction"
- System prompt says "when lesson starts" but trigger was ambiguous

### Issue #4: Insufficient Logging
- Couldn't verify system prompt content
- Couldn't see if student name was included
- No way to debug what was sent to OpenAI

---

## ✅ Fixes Applied

### Fix #1: Enhanced System Prompt Logging
**File**: `app/api/voice_ws.py:174-181`

**Added**:
- Comprehensive logging showing student name, level, session ID
- System prompt length and first 500 characters
- Clear visual separator in logs

**What You'll See in Logs**:
```
================================================================================
SYSTEM PROMPT BUILT:
  Student Name: Яна
  Student Level: A1
  Lesson Session ID: 123
  System Prompt Length: 2500 characters
  System Prompt (First 500 chars):
[Full prompt content here]
================================================================================
```

---

### Fix #2: Session Ready Signal
**File**: `app/api/voice_ws.py:211-221`

**Added**:
- 0.5 second delay after `session.update` to allow OpenAI processing
- "ready" signal sent to frontend
- Logging when session update is sent

**Code**:
```python
await openai_ws.send(json.dumps(session_update))
logger.info("Realtime: session.update sent to OpenAI with system prompt")

# Wait for OpenAI to process
await asyncio.sleep(0.5)
logger.info("Realtime: Session should be ready, sending ready signal to frontend")

# Send ready signal to frontend
await websocket.send_json({
    "type": "system",
    "level": "info",
    "message": "Session ready. You can now start the lesson."
})
```

---

### Fix #3: Improved Greeting Trigger
**File**: `app/api/voice_ws.py:257-266`

**Changed From**:
```python
"Start the lesson."
```

**Changed To**:
```python
f"System Event: Lesson Starting Now. This is the FIRST interaction with the student. The student's name is {user_name}. Follow the Universal Greeting Protocol strictly: greet them warmly using their name, mention any last session summary if available, and start an immediate activity without asking meta-questions."
```

**Why**: 
- Explicitly states it's the FIRST interaction
- Includes student name in trigger
- Explicitly references Universal Greeting Protocol
- Gives clear instructions

---

### Fix #4: Session Update Event Handler
**File**: `app/api/voice_ws.py:361-363`

**Added**:
- Handler for `session.updated` event from OpenAI
- Logs when OpenAI confirms session is ready

**Code**:
```python
elif event_type == "session.updated":
    logger.info("Realtime: Session updated confirmed by OpenAI - system prompt is now active")
```

---

## 📋 Information Flow - Where Data Comes From

### Student Information Source:

1. **User Profile** (`UserProfile` table):
   - Name: `profile.name` → Included in system prompt
   - Level: `profile.english_level` → Included in system prompt
   - Goals: `profile.goals` → Included in system prompt
   - Preferences: `profile.preferences` (JSON) → Parsed and included

2. **System Prompt Builder** (`app/services/tutor_service.py`):
   - Builds comprehensive prompt with:
     - Student name (line 253)
     - Student level (line 254)
     - Universal Greeting Protocol (lines 95-110)
     - Memory (last session summary, weak words)
     - Beginner curriculum (if A1 level)

3. **When Sent to OpenAI**:
   - **Line 211**: `session.update` sent with full system prompt
   - System prompt includes ALL student information
   - OpenAI receives it BEFORE greeting is triggered

---

## 🎯 What Should Happen Now

1. **Restart your server** to apply changes
2. **Start a lesson** as a student
3. **Check backend logs** - you should see:
   - System prompt with student name
   - Session update sent
   - Ready signal sent
   - Greeting trigger sent
   - Response created
   - Transcript saved

4. **Check frontend**:
   - Should receive "Session ready" message
   - Should receive greeting audio
   - Should see greeting transcript

---

## 🔍 Debugging Checklist

If greeting still doesn't work, check:

- [ ] **Logs show system prompt with student name?**
  - Look for: `SYSTEM PROMPT BUILT: Student Name: ...`
  
- [ ] **Session update sent?**
  - Look for: `Realtime: session.update sent to OpenAI with system prompt`
  
- [ ] **Ready signal sent?**
  - Look for: `Realtime: Session should be ready, sending ready signal to frontend`
  
- [ ] **Greeting trigger sent?**
  - Look for: `Realtime: Received lesson_started. Triggering greeting...`
  - Look for: `Realtime: Greeting trigger sent successfully`
  
- [ ] **Response created?**
  - Look for: `Realtime: Response created (ID: ...)`
  
- [ ] **Audio received?**
  - Check frontend console: `🔊 [AUDIO] Received ... bytes`

---

## 📝 Next Steps

1. **Test the fixes** - restart server and try starting a lesson
2. **Check logs** - verify all the new log messages appear
3. **If still not working** - share the logs so we can debug further

The system prompt IS being built with student info, it IS being sent to OpenAI - the issues were timing and explicit triggering. These fixes should resolve that!

