# Lesson Flow Rules

This document describes how lessons are structured in code today and the rules
the tutor must follow.

## Overview (Realtime Voice)
- Entry point: `app/api/voice_ws.py` (`/api/ws/voice`).
- System prompt: `app/services/prompt_builder.py` (simplified builder).
- First lesson onboarding uses `FIRST_LESSON_INTRO`.
- Regular lessons use `REGULAR_GREETING_TEMPLATE` plus level rules.
- Profile capture uses the `update_profile` tool during onboarding.

## Lesson 1 (Onboarding / Intro)

Prompt source:
- `app/services/prompt_builder.py`: `FIRST_LESSON_INTRO`
- `app/services/tutor_service.py`: `build_intro_system_prompt` (fallback)

Rules (must follow):
- Ask exactly ONE question per turn, then wait.
- Keep responses to 1-3 sentences.
- Do not repeat questions that are already answered or stored.
- Use `update_profile(...)` tool silently for each answered item.

Current onboarding order (simplified path):
1) Tutor name (what the student wants to call the tutor)
2) Student name (preferred short name)
3) Addressing mode (ty/vy)
4) Self-assessed English level (1-10)
5) Motivation/goals for English

Fallback path (legacy prompt) can ask additional items:
- Age (optional)
- Conversation style (formal/informal)
- Topics of interest
- Native/other languages
- Correction style

## Lesson 2+ (Regular)

Prompt source:
- `app/services/prompt_builder.py`: `_build_regular_prompt`

Rules (must follow):
- Greet briefly by name.
- If a last-summary exists, mention it in one line.
- Start a concrete activity immediately.
- Ask only one question per turn.
- Keep responses 1-3 sentences.

## Resume Flow (Pause/Resume)

Prompt source:
- `app/services/prompt_builder.py` resume block
- `app/api/voice_ws.py` resume greeting event

Rules (must follow):
- Short "welcome back".
- Briefly mention what was happening before pause.
- Continue from the last point; do not restart or re-introduce.
- Ask only one question per turn.

## Data Persistence

Intro data:
- Stored under `UserProfile.preferences["intro"]`.
- Updated via `update_profile` tool during onboarding.
- Used to prevent repeated questions and personalize later lessons.

Lesson tracking:
- Legacy: `lesson_sessions`, `lesson_turns`
- New pipeline: `tutor_lessons`, `tutor_lesson_turns`

## UI Transcript Assembly

The assistant transcript is streamed in deltas. The UI should append deltas
without inserting extra spaces to avoid broken words.
