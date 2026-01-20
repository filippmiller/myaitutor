# Session Notes: 2026-01-20 11:42 MSK

## Session Focus: Dynamic Rule Injection & Preference Persistence

### Problem Statement

The AI tutor was "forgetting" student preferences mid-conversation:
- Student says "говори по-русски" (speak Russian)
- Tutor acknowledges, speaks Russian for 1-2 sentences
- Tutor reverts to English without remembering the preference
- Same issue with "говори медленнее" (speak slower)

**Root Cause Identified**: Rules were being saved to database but NOT injected into the active OpenAI Realtime conversation. The system prompt is built once at session start and cannot be modified mid-session in OpenAI's Realtime API.

---

## Solution Implemented

### New Service: `app/services/session_rule_manager.py`

**Purpose**: Real-time rule management for active tutoring sessions.

**Key Components**:

1. **Expanded Pattern Detection**
   ```
   LANGUAGE_SWITCH_PATTERNS: 24+ patterns
   - Russian: "говори по-русски", "перейди на русский", "я не понимаю", etc.
   - English: "speak Russian", "switch to Russian", "I don't understand"
   - Both directions (to Russian AND to English)

   SLOW_SPEECH_PATTERNS: 20+ patterns
   - Russian: "говори медленнее", "слишком быстро", "не успеваю"
   - English: "speak slower", "slow down", "too fast", "can't keep up"

   CORRECTION_PATTERNS: For frequent/minimal corrections
   ```

2. **ActiveRule Dataclass**
   ```python
   @dataclass
   class ActiveRule:
       rule_id: Optional[int]
       type: str  # "language", "speech_pace", "correction_style"
       content: str  # Human-readable rule for injection
       value: Optional[str]  # "RU_ONLY", "EN_ONLY", "slow"
       priority: int
       injected: bool
       reminder_count: int
   ```

3. **Dynamic Injection via `conversation.item.create`**
   - OpenAI Realtime API supports adding items to conversation
   - Rules are injected as system messages mid-conversation
   - Model sees them immediately in context

4. **Acknowledgment Protocol**
   ```
   When new rule detected, injection includes:
   "⚠️ CRITICAL: You MUST acknowledge this IMMEDIATELY by saying:
   'Хорошо, буду говорить по-русски.' Then CONTINUE in Russian."
   ```

5. **Periodic Reminders**
   - Every 8 turns, high-priority rules are re-injected
   - Combats LLM "forgetting" as context grows

6. **Persistence**
   - Rules saved to `TutorRule` table
   - Next session loads rules automatically
   - `get_initial_rules_injection()` for session start

---

## Integration Points in `voice_ws.py`

### 1. Initialization (after lesson_session created)
```python
rule_manager = None
if user:
    rule_manager = SessionRuleManager(session, user, lesson_session)
    logger.info(f"✅ SessionRuleManager initialized with {len(rule_manager.active_rules)} rules")
```

### 2. Processing User Turns
```python
# On each user transcript
if rule_manager:
    rule_injection = rule_manager.process_user_turn(transcript)
    if rule_injection:
        inject_event = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "system",
                "content": [{"type": "input_text", "text": rule_injection}],
            },
        }
        await openai_ws.send(json.dumps(inject_event))
```

### 3. Initial Rules at Session Start
```python
# After greeting is sent
if rule_manager:
    initial_rules = rule_manager.get_initial_rules_injection()
    if initial_rules:
        # Inject as system message
        await openai_ws.send(json.dumps(rules_inject_event))
```

### 4. Language Mode Sync
```python
# Update LessonSession when language changes
new_lang_mode = rule_manager.get_language_mode()
if new_lang_mode and new_lang_mode != lesson_session.language_mode:
    lesson_session.language_mode = new_lang_mode
    session.commit()
```

---

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `app/services/session_rule_manager.py` | NEW | 582 lines - Core rule management service |
| `app/api/voice_ws.py` | MODIFIED | +67 lines - Integration with SessionRuleManager |

---

## Key Design Decisions

### Why conversation.item.create?

OpenAI Realtime API doesn't support updating the system prompt mid-session. The only way to inject new instructions is via `conversation.item.create` with role "system". This adds the instruction to the conversation context.

### Why acknowledgment protocol?

Without explicit acknowledgment, the model might process the rule silently but still drift back. Forcing "Хорошо, буду говорить по-русски" ensures:
1. Model explicitly commits to the rule
2. Student hears confirmation
3. Model demonstrates the new behavior immediately

### Why periodic reminders?

LLMs have limited attention span. As conversation grows, early instructions fade in influence. Reminders every 8 turns keep rules "fresh" in context.

### Why persist to database?

If student always wants Russian mode, they shouldn't have to say it every session. Persistent rules are loaded at session start and injected immediately.

---

## Testing Verification

### Manual Tests:
1. **Language Switch**:
   - Say "говори по-русски" mid-lesson
   - Expect: Tutor acknowledges in Russian, continues in Russian
   - Say "speak English" - tutor switches back

2. **Speech Pace**:
   - Say "говори помедленнее"
   - Expect: Tutor acknowledges and uses pauses ("The cat... is on... the table")

3. **Persistence**:
   - Set Russian mode, end lesson
   - Start new lesson
   - Expect: Russian mode active from start

4. **Logs**: Look for `🎯` markers in server logs

---

## Metrics & Confidence

| Metric | Value |
|--------|-------|
| Lines of new code | 582 |
| Lines modified | 67 |
| Patterns for language | 24 |
| Patterns for pace | 20 |
| Confidence level | 92% |

---

## Future Improvements

| Priority | Idea | Status |
|----------|------|--------|
| HIGH | LLM-based command extraction for implicit preferences | Not started |
| HIGH | UI indicator showing active rules | Not started |
| MEDIUM | Rule editing in user settings | Not started |
| MEDIUM | A/B test reminder intervals | Not started |
| LOW | Rule compliance analytics | Not started |

---

## Commit

```
4b07261 feat: Add SessionRuleManager for dynamic rule injection mid-conversation
```

Pushed to `origin/main` at 2026-01-20 11:42 MSK.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Speech                               │
│                    "говори по-русски"                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   OpenAI Realtime API                            │
│                   (Whisper transcription)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      voice_ws.py                                 │
│         conversation.item.input_audio_transcription.completed    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  SessionRuleManager                              │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  extract_commands(transcript)                            │    │
│  │  - Matches against LANGUAGE_SWITCH_PATTERNS              │    │
│  │  - Matches against SLOW_SPEECH_PATTERNS                  │    │
│  │  - Returns: [{type: "language", value: "RU_ONLY"}]       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  _add_rule_from_command()                                │    │
│  │  - Creates/updates ActiveRule                            │    │
│  │  - Persists to TutorRule table                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  _format_rule_injection()                                │    │
│  │  - Builds injection message with acknowledgment          │    │
│  │  - Returns: "🚨 LANGUAGE: SPEAK RUSSIAN... You MUST      │    │
│  │             acknowledge by saying 'Хорошо, буду...'"     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      voice_ws.py                                 │
│           conversation.item.create (role: system)                │
│                              │                                   │
│                              ▼                                   │
│                   OpenAI Realtime API                            │
│              (Rule added to conversation context)                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Tutor Response                               │
│              "Хорошо, буду говорить по-русски.                   │
│               Давай продолжим урок..."                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Related Files Reference

- `app/services/speech_preferences.py` - Old pattern detection (still used as fallback)
- `app/services/prompt_builder.py` - System prompt construction
- `app/services/language_enforcement.py` - Language validation
- `app/models.py` - TutorRule model definition (line 249-266)
