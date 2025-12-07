# AIlingva Multi-Pipeline Implementation
## Dual Pipeline Architecture + Live Rules Terminal

**Date:** 2025-12-07  
**Author:** Warp AI  
**Status:** IN PROGRESS

---

## Executive Summary

This document tracks the implementation of a **dual-pipeline architecture** for AIlingva that separates real-time streaming from analytical processing. The system will:

1. **Streaming Pipeline**: Handle real-time voice lessons (existing functionality, enhanced with instrumentation)
2. **Analysis/Brain Pipeline**: Process conversation turns to:
   - Detect weak words & grammar patterns
   - Update student knowledge models
   - Generate dynamic rules for future lessons
3. **Admin Visualization**: Live "Rules Terminal" showing brain events in real-time

---

## PART A: Current Architecture Audit

### Current Data Flow

```
User presses "Start Lesson"
  ↓
Frontend: VoicePage.tsx → /api/voice/ws (WebSocket)
  ↓
Backend: voice_ws.py → voice_websocket() → run_realtime_session() or run_legacy_session()
  ↓
Process:
  - User speaks → STT (Whisper/OpenAI Realtime)
  - Text → LLM (gpt-4o-mini or gpt-realtime with system prompt from tutor_service.py)
  - Response → TTS (OpenAI/Yandex)
  - Audio → User
  ↓
Persistence:
  - LessonSession row created/updated (lesson_sessions table)
  - Turn records saved (lesson_turns table) - PARTIALLY IMPLEMENTED
  - Prompts logged to static/prompts/ (for admin debugging)
```

### Current Database Tables (Relevant)

| Table | Purpose | Key Fields | Notes |
|-------|---------|------------|-------|
| `user_accounts` | Authentication | id, email, role | ✅ Existing |
| `userprofile` | User profile data | id, name, english_level, goals, user_account_id | ✅ Existing |
| `user_state` | Student knowledge | weak_words_json, known_words_json, session_count | ⚠️ Needs enhancement |
| `lesson_sessions` | Active lesson sessions | id, user_account_id, started_at, status, language_mode | ✅ Existing |
| `lesson_turns` | Dialogue turns | id, session_id, speaker, text, created_at | ✅ Created recently, needs usage |
| `session_summaries` | Post-lesson summaries | summary_text, practiced_words_json, weak_words_json | ✅ Existing |
| `tutor_rules` | Dynamic tutor rules | scope, type, title, description, trigger_condition | ✅ Existing (for Admin AI) |

### Gap Analysis

**What's Missing:**

1. ❌ **Lesson Numbering**: No tracking of 1st, 2nd, 3rd lesson per user
2. ❌ **First Lesson Flow**: No dedicated intro + placement test logic
3. ❌ **Brain Events**: No table to store when/why new rules are generated
4. ❌ **Turn Event Processing**: `lesson_turns` table exists but NOT populated during lessons
5. ❌ **Pipeline Type Tracking**: No way to distinguish STREAMING vs ANALYSIS events
6. ❌ **Structured Student Knowledge**: `user_state` exists but lacks:
   - Lesson count/first_lesson_completed flag
   - Placement level
   - Grammar patterns tracking
   - Vocabulary strength metrics
7. ❌ **Admin Visualization**: No UI for viewing brain events or rules terminal

---

## PART B: New Data Model Design

### New Tables

#### 1. `tutor_lessons` (Enhanced Lesson Sessions)

```sql
CREATE TABLE tutor_lessons (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_accounts(id),
    lesson_number INTEGER NOT NULL,  -- 1, 2, 3...
    is_first_lesson BOOLEAN DEFAULT FALSE,
    placement_test_run BOOLEAN DEFAULT FALSE,
    placement_level VARCHAR(10),  -- 'A1', 'A2', 'B1', 'B2', 'C1', 'C2'
    
    summary_json JSONB,  -- Lesson recap
    next_plan_json JSONB,  -- What to practice next
    pipeline_state_json JSONB,  -- Meta about pipelines
    
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMP,
    
    -- Link to existing lesson_sessions for backwards compatibility
    legacy_session_id INTEGER REFERENCES lesson_sessions(id),
    
    UNIQUE(user_id, lesson_number)
);

CREATE INDEX idx_tutor_lessons_user_id ON tutor_lessons(user_id);
CREATE INDEX idx_tutor_lessons_lesson_number ON tutor_lessons(user_id, lesson_number);
```

**Rationale**: Separate tracking of lesson progression from WebSocket sessions. One lesson can have multiple pause/resume cycles (multiple `lesson_sessions`).

---

#### 2. `tutor_lesson_turns` (Enhanced Turn Tracking)

```sql
CREATE TABLE tutor_lesson_turns (
    id SERIAL PRIMARY KEY,
    lesson_id INTEGER NOT NULL REFERENCES tutor_lessons(id),
    user_id INTEGER NOT NULL REFERENCES user_accounts(id),
    turn_index INTEGER NOT NULL,  -- 0, 1, 2... within lesson
    
    pipeline_type VARCHAR(20) DEFAULT 'STREAMING',  -- 'STREAMING', 'ANALYSIS', 'INSIGHTS'
    
    user_text TEXT,
    tutor_text TEXT,
    
    raw_payload_json JSONB,  -- Full debug info (STT confidence, etc.)
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    UNIQUE(lesson_id, turn_index)
);

CREATE INDEX idx_tutor_lesson_turns_lesson_id ON tutor_lesson_turns(lesson_id);
CREATE INDEX idx_tutor_lesson_turns_user_id ON tutor_lesson_turns(user_id);
CREATE INDEX idx_tutor_lesson_turns_pipeline ON tutor_lesson_turns(pipeline_type);
```

**Rationale**: `lesson_turns` is too basic. We need pipeline_type, turn_index, and lesson_id for proper sequencing.

---

#### 3. `tutor_brain_events`

```sql
CREATE TABLE tutor_brain_events (
    id SERIAL PRIMARY KEY,
    lesson_id INTEGER NOT NULL REFERENCES tutor_lessons(id),
    user_id INTEGER NOT NULL REFERENCES user_accounts(id),
    turn_id INTEGER REFERENCES tutor_lesson_turns(id),  -- Specific turn that triggered this
    
    pipeline_type VARCHAR(20) DEFAULT 'ANALYSIS',
    
    event_type VARCHAR(50) NOT NULL,  -- 'WEAK_WORD_ADDED', 'GRAMMAR_PATTERN_UPDATE', 'RULE_CREATED', etc.
    
    event_payload_json JSONB NOT NULL,  -- Details: weak_words_added, grammar_updates, new_rules, etc.
    
    snapshot_student_knowledge_json JSONB,  -- Optional snapshot after this event
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tutor_brain_events_lesson_id ON tutor_brain_events(lesson_id);
CREATE INDEX idx_tutor_brain_events_user_id ON tutor_brain_events(user_id);
CREATE INDEX idx_tutor_brain_events_event_type ON tutor_brain_events(event_type);
CREATE INDEX idx_tutor_brain_events_created_at ON tutor_brain_events(created_at DESC);
```

**Event Payload Examples:**

```json
// WEAK_WORD_ADDED
{
  "weak_words_added": ["go", "went"],
  "frequency": 3,
  "context": "User struggled with past tense of 'go'"
}

// GRAMMAR_PATTERN_UPDATE
{
  "pattern": "3rd_person_singular",
  "mistakes_count": 2,
  "examples": ["He go to school", "She have a cat"]
}

// RULE_CREATED
{
  "rule_id": 123,
  "rule_type": "difficulty_adjustment",
  "rule_title": "Focus on Past Simple next lesson",
  "rule_description": "User made 5+ mistakes with irregular verbs"
}
```

---

#### 4. `tutor_student_knowledge` (Enhanced User Knowledge)

```sql
CREATE TABLE tutor_student_knowledge (
    user_id INTEGER PRIMARY KEY REFERENCES user_accounts(id),
    
    level VARCHAR(10) DEFAULT 'A1',  -- Current CEFR level
    lesson_count INTEGER DEFAULT 0,
    first_lesson_completed BOOLEAN DEFAULT FALSE,
    
    -- Vocabulary tracking
    vocabulary_json JSONB DEFAULT '{"weak": [], "strong": [], "neutral": []}'::jsonb,
    
    -- Grammar tracking
    grammar_json JSONB DEFAULT '{"patterns": {}, "mistakes": {}}'::jsonb,
    
    -- Topics tracking
    topics_json JSONB DEFAULT '{"covered": [], "to_practice": []}'::jsonb,
    
    -- Extensibility
    meta_json JSONB DEFAULT '{}'::jsonb,
    
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tutor_student_knowledge_user_id ON tutor_student_knowledge(user_id);
```

**Vocabulary JSON Structure:**
```json
{
  "weak": [
    {"word": "go", "frequency": 5, "last_mistake": "2025-12-07T10:30:00Z"},
    {"word": "beautiful", "frequency": 2, "last_mistake": "2025-12-07T11:00:00Z"}
  ],
  "strong": ["hello", "thank", "yes", "no"],
  "neutral": ["computer", "water"]
}
```

**Grammar JSON Structure:**
```json
{
  "patterns": {
    "present_simple": {"mastery": 0.8, "attempts": 20, "mistakes": 4},
    "past_simple": {"mastery": 0.4, "attempts": 10, "mistakes": 6}
  },
  "mistakes": {
    "3rd_person_singular": 5,
    "irregular_verbs": 8
  }
}
```

---

## PART C: Implementation Checklist

### ✅ A. Deep Audit (COMPLETED)

- [x] Map current streaming lesson flow
- [x] Document database schema
- [x] Identify gaps
- [x] Create architecture diagrams

### ✅ B. Database Schema Implementation (COMPLETED)

- [x] Create migration: `tutor_lessons` table
- [x] Create migration: `tutor_lesson_turns` table
- [x] Create migration: `tutor_brain_events` table
- [x] Create migration: `tutor_student_knowledge` table
- [x] Add SQLModel models to `app/models.py`
- [x] Test migrations locally
- [x] Deploy migrations to Supabase

### 🔲 C. First Lesson Logic

- [x] Implement `get_lesson_number_for_user()` in `tutor_service.py`
- [x] Implement `is_first_lesson()` check
- [ ] Create placement test prompts/flow
- [ ] Modify `run_realtime_session()` to:
  - Create `tutor_lessons` row
  - Run intro + placement on first lesson
  - Skip intro on subsequent lessons
- [ ] Store placement results in `tutor_student_knowledge`

### 🔲 D. Streaming Pipeline Instrumentation

- [ ] Modify `run_realtime_session()` to populate `tutor_lesson_turns` on EVERY turn
- [ ] Add `pipeline_type='STREAMING'` to all turn records
- [ ] Ensure turn_index increments correctly
- [ ] Store raw_payload_json for debugging

### ✅ E. Analysis/Brain Pipeline Implementation (PARTIAL)

- [x] Create `app/services/brain_service.py`
- [ ] Implement background task/worker to:
  - Poll new turns from `tutor_lesson_turns`
  - Analyze text for weak words
  - Analyze text for grammar mistakes
  - Update `tutor_student_knowledge`
  - Create `tutor_brain_events`
- [x] Define event types:
  - `WEAK_WORD_ADDED`
  - `GRAMMAR_PATTERN_UPDATE`
  - `RULE_CREATED`
  - `VOCABULARY_STRENGTH_CHANGE`
- [ ] Test brain pipeline with mock data

### 🔲 F. Admin Visualization & Rules Terminal

#### Backend (COMPLETED ✅)

- [x] Create `app/api/routes/admin_tutor.py`:
  - [x] `GET /api/admin/tutor/lessons?user_id=X`
  - [x] `GET /api/admin/tutor/lessons/{lesson_id}/turns`
  - [x] `GET /api/admin/tutor/lessons/{lesson_id}/brain-events`
  - [x] `GET /api/admin/tutor/users/{user_id}/knowledge`
  - [x] `GET /api/admin/tutor/brain-events/terminal-feed` (for live terminal)
- [x] Add routes to `app/main.py`
- [ ] Test all endpoints

#### Frontend (TODO)

- [ ] Create `frontend/src/pages/AdminTutorPipelines.tsx`
- [ ] Implement Lesson Timeline View:
  - Table of turns (turn_index, time, user_text, tutor_text)
  - Filter by user/lesson
- [ ] Implement Brain Events View:
  - Table of brain events (event_type, payload summary, timestamp)
- [ ] Implement Live Rules Terminal:
  - Auto-refreshing component (polling or WebSocket)
  - Terminal-like UI showing new events as they appear
  - Example:
    ```
    [12:01:05] WEAK_WORD_ADDED: "go"
    [12:01:07] GRAMMAR_PATTERN_UPDATE: "3rd_person_singular" frequency=3
    [12:01:22] RULE_CREATED: "Repeat 'to go' in Past Simple next lesson"
    ```
- [ ] Implement Student Knowledge Snapshot Panel:
  - Show current level, lesson_count, weak/strong words, grammar patterns

### 🔲 G. Tests & Safety

- [ ] Test first lesson flow (new user)
- [ ] Test second lesson flow (existing user)
- [ ] Test brain events generation
- [ ] Test admin UI connectivity
- [ ] Ensure no API keys in logs/DB
- [ ] Performance test: 1000+ turns, measure brain pipeline latency

### 🔲 H. Documentation

- [ ] Create architecture diagram (old vs new)
- [ ] Document all new tables
- [ ] Document brain event payload structures
- [ ] Document admin UI usage
- [ ] Create end-to-end test guide

---

## PART D: Verification Plan

### New User First Lesson Test

1. Create new user account
2. Start lesson → Confirm intro + placement test runs
3. Check DB:
   - `tutor_lessons`: lesson_number=1, is_first_lesson=true, placement_level set
   - `tutor_student_knowledge`: first_lesson_completed=true, level set
   - `tutor_lesson_turns`: Turn records created
   - `tutor_brain_events`: Events generated during lesson

### Existing User Second Lesson Test

1. Use user from Test 1
2. Start lesson → Confirm NO intro/placement
3. Check DB:
   - `tutor_lessons`: lesson_number=2, is_first_lesson=false
   - `tutor_student_knowledge`: lesson_count=2
   - Previous knowledge persisted and used in prompts

### Brain Pipeline Test

1. Simulate mistakes: "I go to school yesterday"
2. Check `tutor_brain_events`:
   - Event type: `WEAK_WORD_ADDED` → "go" (past tense)
   - Event type: `GRAMMAR_PATTERN_UPDATE` → "past_simple"
3. Check `tutor_student_knowledge`:
   - vocabulary_json.weak contains "go"
   - grammar_json.patterns.past_simple.mistakes incremented

### Admin UI Test

1. Open Admin → Tutor Pipelines
2. Select user + lesson
3. Verify:
   - Timeline shows all turns
   - Brain events list populated
   - Rules Terminal auto-updates during active lesson
   - Knowledge snapshot shows latest data

---

## PART E: Technical Notes

### Multi-Pipeline Extensibility

Current design supports adding new pipelines easily:

- **STREAMING**: Real-time conversation (existing)
- **ANALYSIS**: Post-turn analysis (new)
- **INSIGHTS**: Future pipeline for long-term analytics (e.g., weekly reports)
- **TESTING**: Future pipeline for A/B testing prompts

To add a new pipeline:
1. Add new `pipeline_type` enum value
2. Create consumer reading from `tutor_lesson_turns` or `tutor_brain_events`
3. No schema changes needed (JSONB fields are flexible)

### Security Considerations

- All admin endpoints must check `role='admin'`
- Never expose raw API keys in brain events
- Sanitize user_text before storing (no PII beyond what user provides)
- Rate-limit brain event polling endpoints

---

## Next Steps

1. Start with **Part B: Database Schema Implementation**
2. Then **Part C: First Lesson Logic**
3. Then **Part D: Streaming Pipeline Instrumentation**
4. Then **Part E: Analysis/Brain Pipeline**
5. Finally **Part F: Admin Visualization**

---

**Last Updated:** 2025-12-07 11:30:00 UTC  
**Status:** Ready to begin implementation
