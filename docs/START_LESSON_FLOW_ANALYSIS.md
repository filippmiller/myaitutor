# Start Lesson Flow - Complete Analysis

**Date**: 2025-01-XX  
**Goal**: Trace the complete flow from "Start Lesson" button press to first tutor voice response

---

## 🔍 Complete Flow Trace

### Step 1: Frontend - Button Press
**File**: `frontend/src/pages/Student.tsx:95-129`

```typescript
const startLesson = async () => {
    // 1. Get microphone access
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    
    // 2. Initialize Audio Context
    audioContextRef.current = new AudioContext();
    
    // 3. Connect WebSocket
    const ws = new WebSocket('ws://localhost:8000/api/ws/voice');
    
    ws.onopen = () => {
        // 4. IMMEDIATELY send config + lesson_started
        ws.send(JSON.stringify({ type: 'config', stt_language: sttLanguage }));
        ws.send(JSON.stringify({ type: 'system_event', event: 'lesson_started' }));
        
        // 5. Start MediaRecorder
        mediaRecorder.start(250);
    };
}
```

**Key Points**:
- ✅ Frontend sends `config` message
- ✅ Frontend sends `lesson_started` event
- ⚠️ **PROBLEM**: Messages sent IMMEDIATELY when WebSocket opens
- ⚠️ Backend might not be ready yet!

---

### Step 2: Backend - WebSocket Connection
**File**: `app/api/voice_ws.py:56-145`

```python
@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    
    # 1. Authenticate user
    user = authenticate_user(websocket)
    profile = get_user_profile(user)
    
    # 2. Load settings & API key
    api_key = get_api_key()
    
    # 3. Determine TTS engine
    tts_engine = "openai"  # or "yandex"
    
    # 4. Try Realtime Session
    if tts_engine == "openai":
        await run_realtime_session(...)
```

**Key Points**:
- ✅ User authenticated
- ✅ Profile loaded (contains student name, level, etc.)
- ✅ API key loaded
- ✅ TTS engine determined

---

### Step 3: Backend - Realtime Session Setup
**File**: `app/api/voice_ws.py:148-202`

```python
async def run_realtime_session(websocket, api_key, voice_id, profile, session):
    # 1. Create LessonSession in database
    lesson_session = LessonSession(...)
    session.add(lesson_session)
    session.commit()
    
    # 2. Build System Prompt (INCLUDES student info!)
    system_instructions = build_tutor_system_prompt(session, profile, lesson_session_id=lesson_session.id)
    # This includes:
    # - Student name
    # - English level
    # - Goals
    # - Universal Greeting Protocol
    # - Memory (last session summary, weak words, etc.)
    
    # 3. Connect to OpenAI Realtime API
    async with websockets.connect("wss://api.openai.com/v1/realtime", ...) as openai_ws:
        
        # 4. Send session configuration with system prompt
        session_update = {
            "type": "session.update",
            "session": {
                "instructions": system_instructions,  # ← SYSTEM PROMPT SENT HERE
                "voice": voice_id,
                "modalities": ["text", "audio"],
                ...
            }
        }
        await openai_ws.send(json.dumps(session_update))
        # ✅ System prompt is now active in OpenAI session
        
        # 5. Start async tasks
        tasks = [
            frontend_to_openai(),    # ← Receives messages from frontend
            converter_reader(),      # ← Converts audio
            openai_to_frontend()     # ← Receives responses from OpenAI
        ]
```

**Key Points**:
- ✅ System prompt built with ALL student information
- ✅ System prompt sent to OpenAI via `session.update`
- ⚠️ **PROBLEM**: Async tasks start, but greeting trigger happens INSIDE `frontend_to_openai()` task
- ⚠️ **TIMING ISSUE**: `lesson_started` might arrive before tasks are ready!

---

### Step 4: Backend - Receiving `lesson_started`
**File**: `app/api/voice_ws.py:222-260`

```python
async def frontend_to_openai():
    while True:
        message = await websocket.receive()  # ← Waits for frontend messages
        
        if "text" in message:
            data = json.loads(message["text"])
            
            if data.get("type") == "system_event" and data.get("event") == "lesson_started":
                # ✅ Received lesson_started!
                
                # Send greeting trigger to OpenAI
                greeting_trigger = {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "Start the lesson."}]
                    }
                }
                await openai_ws.send(json.dumps(greeting_trigger))
                
                # Request response
                await openai_ws.send(json.dumps({"type": "response.create"}))
```

**Key Points**:
- ✅ Receives `lesson_started` event
- ✅ Sends greeting trigger to OpenAI
- ⚠️ **CRITICAL**: System prompt was already sent in Step 3
- ✅ OpenAI should follow system prompt to generate greeting

---

### Step 5: OpenAI - Processing Request

**What OpenAI Receives**:
1. **System Prompt** (from `session.update`):
   ```
   You are a personal English tutor for a Russian-speaking student.
   
   UNIVERSAL GREETING PROTOCOL (STRICT):
   When the lesson starts (first interaction), you MUST:
   1. Greet briefly: Use the student's name if known. Be warm but concise.
   2. Contextual Bridge: If there is a 'last_summary' in your memory, briefly mention it.
   3. IMMEDIATE ACTIVITY: Do NOT ask "What do you want to do?". Instead, propose a specific simple activity...
   
   Student Context:
   Name: Яна
   Level: A1
   ...
   ```

2. **Greeting Trigger** (from `conversation.item.create`):
   ```
   User message: "Start the lesson."
   ```

3. **Response Request** (from `response.create`):
   ```
   Generate a response following the system prompt
   ```

**What OpenAI Should Do**:
- Follow Universal Greeting Protocol
- Use student's name (Яна)
- Greet warmly
- Start an immediate activity
- Generate audio response

---

### Step 6: Backend - Receiving Response from OpenAI
**File**: `app/api/voice_ws.py:302-380`

```python
async def openai_to_frontend():
    async for message in openai_ws:
        event = json.loads(message)
        event_type = event.get("type")
        
        if event_type == "response.audio.delta":
            # Received audio chunk
            pcm_data = base64.b64decode(event.get("delta"))
            wav_data = add_wav_header(pcm_data)
            await websocket.send_bytes(wav_data)  # ← Send to frontend
        
        elif event_type == "response.audio_transcript.delta":
            # Received text transcript
            delta = event.get("delta")
            await websocket.send_json({
                "type": "transcript",
                "role": "assistant",
                "text": delta
            })  # ← Send to frontend
        
        elif event_type == "response.output_item.done":
            # Save transcript to database
            transcript = extract_transcript(event)
            turn = LessonTurn(session_id=..., speaker="assistant", text=transcript)
            session.add(turn)
            session.commit()
```

**Key Points**:
- ✅ Receives audio deltas from OpenAI
- ✅ Receives text transcripts from OpenAI
- ✅ Sends audio to frontend
- ✅ Sends transcript to frontend
- ✅ Saves to database

---

### Step 7: Frontend - Receiving Response
**File**: `frontend/src/pages/Student.tsx:147-193`

```typescript
ws.onmessage = async (event) => {
    if (event.data instanceof Blob) {
        // Binary = Audio
        queueAudio(event.data);  // ← Play audio
    } else {
        // Text = JSON transcript
        const msg = JSON.parse(event.data);
        
        if (msg.type === 'transcript') {
            setTranscript(prev => [...prev, {
                role: msg.role,
                text: msg.text
            }]);  // ← Display transcript
        }
    }
};
```

**Key Points**:
- ✅ Receives audio blobs
- ✅ Receives transcript JSON
- ✅ Plays audio
- ✅ Displays transcript

---

## 🔴 CRITICAL ISSUES IDENTIFIED

### Issue #1: RACE CONDITION - Timing Problem

**Problem**: 
- Frontend sends `lesson_started` IMMEDIATELY when WebSocket opens
- Backend async tasks might not be fully initialized
- `session.update` might not have been sent to OpenAI yet
- Greeting trigger might be sent before system prompt is active

**Current Flow**:
```
1. Frontend: WebSocket opens
2. Frontend: Sends lesson_started (IMMEDIATELY)
3. Backend: Receives lesson_started (might be too early!)
4. Backend: Sends greeting trigger (system prompt might not be ready)
5. OpenAI: Processes without proper context
```

**Should Be**:
```
1. Frontend: WebSocket opens
2. Backend: Sends session.update with system prompt
3. Backend: Waits for session to be ready
4. Backend: Signals frontend "ready"
5. Frontend: Receives "ready" signal
6. Frontend: Sends lesson_started
7. Backend: Receives lesson_started
8. Backend: Sends greeting trigger
```

---

### Issue #2: System Prompt Not Verified

**Problem**: 
- We send `session.update` but don't wait for confirmation
- OpenAI might not have processed it yet
- No way to know if system prompt is active

**Solution Needed**: 
- Wait for `session.updated` event from OpenAI
- Or add a delay/confirmation mechanism

---

### Issue #3: Greeting Trigger Too Simple

**Problem**:
- Current greeting trigger: `"Start the lesson."`
- System prompt says "When the lesson starts (first interaction)..."
- OpenAI might not recognize "Start the lesson." as "first interaction"

**Solution Needed**:
- More explicit trigger: `"The lesson is starting now. This is your first interaction with the student. Follow the Universal Greeting Protocol."`

---

### Issue #4: No Confirmation of Response Generation

**Problem**:
- We send `response.create` but don't wait for confirmation
- No way to know if OpenAI is actually generating a response
- If it fails silently, we never know

---

## ✅ WHAT IS WORKING

1. ✅ System prompt is built correctly with student info
2. ✅ System prompt includes Universal Greeting Protocol
3. ✅ System prompt is sent to OpenAI
4. ✅ Student information (name, level, etc.) is included
5. ✅ Audio/transcript forwarding works

---

## 🔧 RECOMMENDED FIXES

### Fix #1: Add Ready Signal
- Backend sends "ready" signal to frontend after `session.update` is sent
- Frontend waits for "ready" before sending `lesson_started`

### Fix #2: Wait for Session Update Confirmation
- Wait for `session.updated` event from OpenAI
- Or add explicit delay after `session.update`

### Fix #3: Improve Greeting Trigger
- Make trigger more explicit about being first interaction
- Include student name in trigger for clarity

### Fix #4: Add Response Confirmation
- Wait for `response.created` event
- Log when response starts
- Track if response is actually generated

---

## 📋 VERIFICATION CHECKLIST

To verify the flow is working:

- [ ] Check logs: "System Instructions (First 200 chars): ..." - verify student name is in prompt
- [ ] Check logs: "Connected to OpenAI Realtime API"
- [ ] Check logs: "Realtime: Received lesson_started. Triggering greeting..."
- [ ] Check logs: "Realtime: Greeting trigger sent successfully"
- [ ] Check logs: "Realtime: Response created (ID: ...)"
- [ ] Check logs: "Realtime: Response done (ID: ...)"
- [ ] Check logs: "Realtime: Saved assistant transcript"
- [ ] Check frontend console: Audio received and played
- [ ] Check frontend console: Transcript displayed

---

## 🎯 NEXT STEPS

1. ✅ **Add logging** to verify system prompt content - DONE
2. ✅ **Add ready signal** mechanism - DONE (with 0.5s delay)
3. ✅ **Improve greeting trigger** text - DONE (more explicit)
4. ⏳ **Test with actual student data** to verify name appears
5. ✅ **Monitor OpenAI events** - DONE (session.updated handler added)

---

## ✅ FIXES IMPLEMENTED (2025-01-XX)

### Fix #1: Enhanced Logging
- Added comprehensive system prompt logging showing:
  - Student name
  - Student level
  - Lesson session ID
  - System prompt length
  - First 500 characters of prompt

### Fix #2: Session Ready Signal
- Added 0.5 second delay after `session.update` to allow OpenAI to process
- Added "ready" signal sent to frontend
- Logs when session update is sent

### Fix #3: Improved Greeting Trigger
- Changed from simple "Start the lesson." to explicit instruction:
  - Mentions it's the FIRST interaction
  - Includes student name
  - Explicitly references Universal Greeting Protocol
  - Reminds to follow protocol strictly

### Fix #4: Session Update Event Handler
- Added handler for `session.updated` event from OpenAI
- Logs when session is confirmed ready

### Code Changes Summary:
```python
# Before:
await openai_ws.send(json.dumps(session_update))

# After:
await openai_ws.send(json.dumps(session_update))
logger.info("Realtime: session.update sent to OpenAI with system prompt")
await asyncio.sleep(0.5)  # Wait for processing
await websocket.send_json({"type": "system", "level": "info", "message": "Session ready..."})
```

```python
# Before:
"Start the lesson."

# After:
"System Event: Lesson Starting Now. This is the FIRST interaction with the student. The student's name is {user_name}. Follow the Universal Greeting Protocol strictly: greet them warmly using their name, mention any last session summary if available, and start an immediate activity without asking meta-questions."
```

---

## 🔍 VERIFICATION STEPS

When testing, check these logs:

1. **System Prompt Built**:
   ```
   ================================================================================
   SYSTEM PROMPT BUILT:
     Student Name: Яна
     Student Level: A1
     Lesson Session ID: 123
     System Prompt Length: 2500 characters
   ================================================================================
   ```

2. **Session Update Sent**:
   ```
   Realtime: session.update sent to OpenAI with system prompt
   Realtime: Session should be ready, sending ready signal to frontend
   ```

3. **Greeting Trigger**:
   ```
   Realtime: Received lesson_started. Triggering greeting...
   Realtime: Greeting trigger sent successfully
   ```

4. **Response Generation**:
   ```
   Realtime: Response created (ID: resp_xxx)
   Realtime: Saved assistant transcript (length: 150)
   ```

