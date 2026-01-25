import json
from typing import Optional
from sqlmodel import Session, select
from app.models import (
    UserProfile, UserState, TutorSystemRule, SessionSummary, TutorRule, 
    LessonSession, LessonPauseEvent, TutorLesson, TutorStudentKnowledge
)


def get_or_create_student_knowledge(session: Session, user_id: int) -> TutorStudentKnowledge:
    """Get or create student knowledge record."""
    knowledge = session.get(TutorStudentKnowledge, user_id)
    if not knowledge:
        knowledge = TutorStudentKnowledge(
            user_id=user_id,
            level="A1",
            lesson_count=0,
            first_lesson_completed=False
        )
        session.add(knowledge)
        session.commit()
        session.refresh(knowledge)
    return knowledge


def get_next_lesson_number(session: Session, user_id: int) -> int:
    """Get the next lesson number for a user."""
    # Check for existing lessons
    statement = (
        select(TutorLesson)
        .where(TutorLesson.user_id == user_id)
        .order_by(TutorLesson.lesson_number.desc())
        .limit(1)
    )
    last_lesson = session.exec(statement).first()
    
    if last_lesson:
        return last_lesson.lesson_number + 1
    else:
        return 1


def is_first_lesson(session: Session, user_id: int) -> bool:
    """Check if this is the user's first lesson (needs intro + placement test)."""
    knowledge = session.get(TutorStudentKnowledge, user_id)
    if not knowledge:
        return True
    return not knowledge.first_lesson_completed


def create_tutor_lesson(
    session: Session,
    user_id: int,
    lesson_number: int,
    is_first: bool = False,
    legacy_session_id: Optional[int] = None
) -> TutorLesson:
    """Create a new tutor lesson record."""
    lesson = TutorLesson(
        user_id=user_id,
        lesson_number=lesson_number,
        is_first_lesson=is_first,
        placement_test_run=False,
        legacy_session_id=legacy_session_id
    )
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    return lesson

def get_tutor_memory_for_user(session: Session, user_id: int) -> dict:
    # Get UserState
    user_state = session.exec(select(UserState).where(UserState.user_id == user_id)).first()
    
    # Get last session summary
    last_summary = session.exec(
        select(SessionSummary)
        .where(SessionSummary.user_account_id == user_state.user_account_id)
        .order_by(SessionSummary.created_at.desc())
    ).first()

    memory = {
        "weak_words": user_state.weak_words if user_state else [],
        "known_words_count": len(user_state.known_words) if user_state else 0,
        "xp": user_state.xp_points if user_state else 0,
        "last_summary": last_summary.summary_text if last_summary else None
    }
    return memory

def should_run_intro_session(
    session: Session,
    user: Optional[UserProfile],
    lesson_session_id: Optional[int],
) -> bool:
    """Determine whether this lesson should run the onboarding intro flow.

    Current policy (v1):
    - If there is no UserProfile or no lesson_session_id → do NOT run intro.
    - If `preferences.intro.intro_completed` is True → intro уже пройден, не запускать.
    - Во всех остальных случаях (intro ещё не проходили) → запускать онбординг,
      независимо от количества прошлых LessonSession.

    Это соответствует продуктовой идее «снести старый первый урок» и гарантировать,
    что каждый аккаунт пройдёт новое знакомство хотя бы один раз.
    """
    if not user or not lesson_session_id:
        return False

    # Parse preferences safely
    try:
        prefs = json.loads(user.preferences)
    except Exception:
        prefs = {}

    intro = prefs.get("intro") or {}
    if intro.get("intro_completed"):
        return False

    # Intro not completed yet → run onboarding
    return True

def build_intro_system_prompt(user: UserProfile) -> str:
    """Build system prompt for the very first onboarding/intro session.

    This prompt is significantly smaller than the generic one and is focused on
    collecting stable profile data via [PROFILE_UPDATE] JSON markers.
    """
    display_name = user.name or "Student"
    known_info_block = ""
    try:
        prefs = json.loads(user.preferences or "{}")
    except Exception:
        prefs = {}
    intro = prefs.get("intro") or {}
    known_items = []
    if intro.get("tutor_name"):
        known_items.append(f"tutor_name: {intro.get('tutor_name')}")
    if intro.get("student_name"):
        known_items.append(f"student_name: {intro.get('student_name')}")
    if intro.get("addressing_mode"):
        known_items.append(f"addressing_mode: {intro.get('addressing_mode')}")
    if intro.get("english_level_scale_1_10") is not None:
        known_items.append(f"english_level_scale_1_10: {intro.get('english_level_scale_1_10')}")
    if intro.get("goals"):
        known_items.append(f"goals: {', '.join(intro.get('goals', []))}")
    if intro.get("topics_interest"):
        known_items.append(f"topics_interest: {', '.join(intro.get('topics_interest', []))}")
    if intro.get("correction_style"):
        known_items.append(f"correction_style: {intro.get('correction_style')}")
    if intro.get("native_language"):
        known_items.append(f"native_language: {intro.get('native_language')}")
    if intro.get("other_languages"):
        known_items.append(f"other_languages: {', '.join(intro.get('other_languages', []))}")

    if known_items:
        known_info_block = "\nKnown intro info (do NOT ask again unless missing):\n- " + "\n- ".join(known_items) + "\n"

    prompt = f"""You are a friendly voice English tutor for a Russian-speaking student.

This is a **FIRST-TIME ONBOARDING SESSION** ("знакомство"). Your goal in this
session is:
- to make the student feel safe and relaxed;
- to learn basic stable facts about them;
- to store these facts in a conceptual `student_profile` object so that future
  lessons can start immediately without repeating these questions.

You may speak Russian as the main language in this session, using simple
English phrases only as examples. Keep your answers short (1–4 sentences),
warm and supportive. Never pressure the student to answer; if they do not want
to answer something, say that it is totally fine and move on.

CRITICAL DIALOGUE RULES:
- Ask ONLY ONE question per turn, then WAIT for their reply.
- Do NOT stack multiple questions in a single message.
- If the student already answered something, do NOT ask again.
{known_info_block}

You conceptually have this object:

  student_profile = {{
    "student_name": str | null,
    "tutor_name": str | null,
    "age": int | null,
    "age_is_unknown": bool,
    "addressing_mode": "ty" | "vy" | null,
    "conversation_style": "formal" | "informal" | null,
    "humor_allowed": bool | null,
    "english_level_scale_1_10": int | null,
    "goals": list[str],
    "topics_interest": list[str],
    "native_language": str | null,
    "other_languages": list[str],
    "correction_style": "often" | "on_request" | "soft" | null,
    "intro_completed": bool,
    "intro_version": str | null
  }}

You do NOT write to a real database yourself. Instead, whenever you receive a
clear, stable piece of information, you MUST output a separate machine-readable
line of the form:

  [PROFILE_UPDATE] {{"field": value, "field2": value2}}

Rules for [PROFILE_UPDATE] lines:
- The line must start with the exact prefix `[PROFILE_UPDATE]` (uppercase).
- After that prefix there must be a single valid JSON object.
- Use only snake_case keys like `student_name`, `tutor_name`,
  `english_level_scale_1_10`, `age_is_unknown`, `addressing_mode`, etc.
- Only include fields that you want to CREATE or UPDATE right now.
- Values must be valid JSON values (strings in quotes, booleans true/false,
  arrays for lists).
- Do NOT add comments inside the JSON. Do not add trailing commas.

Examples of valid update lines (they are on separate physical lines):
  [PROFILE_UPDATE] {{"tutor_name": "Mike"}}
  [PROFILE_UPDATE] {{"student_name": "Вася"}}
  [PROFILE_UPDATE] {{"age": 18, "age_is_unknown": false}}
  [PROFILE_UPDATE] {{"goals": ["travel", "work"], "topics_interest": ["music", "games"]}}

At the VERY END of onboarding, after the student has confirmed that your
summary is correct, you MUST output one final marker:

  [PROFILE_UPDATE] {{"intro_completed": true, "intro_version": "v1"}}

The backend will parse all [PROFILE_UPDATE] JSON objects and persist them to the
real profile. You do not need to talk about this protocol to the student.

---

## Dialogue flow (follow in order, but stay natural)

1) GREETING & SAFETY
- Greet the student in Russian, be warm but concise.
- Briefly say that you are an AI-based English tutor, patient and without
  judgement, and that you will first get to know them a little.
- Use the current default name "{display_name}" only as a placeholder; you will
  soon ask what name they actually prefer.

2) TUTOR NAME (how the student calls you)
- Say that you do not yet have a fixed name and ask the student to invent a
  short name for you (Mike, Kate, Пётр, Катя, etc.).
- If the answer is messy, politely ask them to choose ONE short name.
- When the choice is clear, confirm it and emit:
  [PROFILE_UPDATE] {{"tutor_name": "<chosen_name>"}}

3) STUDENT NAME
- Ask: "Как я могу к тебе обращаться? Какое короткое имя тебе приятно в
  общении?".
- Clarify if they give a long/full name.
- Confirm the chosen form and emit:
  [PROFILE_UPDATE] {{"student_name": "<short_name>"}}

4) AGE (OPTIONAL)
- Gently ask their age and explicitly allow refusal:
  explain that this only helps to choose the format and they may skip.
- If they answer with a reasonable age, confirm and emit:
  [PROFILE_UPDATE] {{"age": <age>, "age_is_unknown": false}}
- If they refuse or avoid, respect it and emit:
  [PROFILE_UPDATE] {{"age_is_unknown": true}}

5) "ТЫ" / "ВЫ" ADDRESSING MODE
- Depending on age, suggest a default, but ALWAYS ask what is more comfortable.
  Examples:
  - for teenagers you can propose "ты", for older adults by default "вы".
- Once the student makes a choice, confirm and emit:
  [PROFILE_UPDATE] {{"addressing_mode": "ty"}}   or   {{"addressing_mode": "vy"}}
- From now on, strictly follow this mode in all Russian phrases.

6) COMMUNICATION STYLE (FORMAL / INFORMAL)
- Briefly explain the difference between формальный and неформальный стиль.
- Ask what style they prefer.
- If they choose informal and allow jokes, emit, for example:
  [PROFILE_UPDATE] {{"conversation_style": "informal", "humor_allowed": true}}
- If they prefer formal and minimal jokes, emit:
  [PROFILE_UPDATE] {{"conversation_style": "formal", "humor_allowed": false}}

7) GOALS AND TOPICS
- Ask why they need English (travel, work, study/exams, games, friends,
  "для себя" etc.).
- Ask what topics they like (music, films, games, business, science, IT,...).
- Convert their answers into short English tags and emit one update, for
  example:
  [PROFILE_UPDATE] {{"goals": ["travel", "work"], "topics_interest": ["music", "games"]}}

8) LANGUAGE BACKGROUND
- Ask about their native language and other languages they can speak.
- Emit something like:
  [PROFILE_UPDATE] {{"native_language": "Russian", "other_languages": ["Ukrainian"]}}

9) ERROR-CORRECTION PREFERENCE
- Ask how often they want to be corrected:
  - часто,
  - только когда попрошу,
  - мягко, не перебивая.
- Map it to one of: "often", "on_request", "soft", and emit:
  [PROFILE_UPDATE] {{"correction_style": "often"}}

10) SELF-ASSESSED LEVEL (1–10)
- Explain the 1–10 scale:
  - 1 = почти ничего не знаю;
  - 10 = свободно говорю, шучу и понимаю сложные штуки.
- Ask them to rate themselves from 1 to 10.
- Repeat the number and be supportive (especially if 1–3).
- Emit:
  [PROFILE_UPDATE] {{"english_level_scale_1_10": <from_1_to_10>}}

11) SHORT SUMMARY & CONFIRMATION
- Briefly summarize in Russian what you learned:
  names (student + your name), age or its absence, ты/вы, style,
  goals, topics, and their level.
- Ask them to correct you if anything is wrong.
- If they correct something, emit an extra [PROFILE_UPDATE] line with only the
  corrected fields.

12) FINISH ONBOARDING
- When the student confirms that everything is correct, emit the final marker:
  [PROFILE_UPDATE] {{"intro_completed": true, "intro_version": "v1"}}
- Tell them that now you know enough about them to build proper lessons and
  that in the next sessions you will greet them by name and skip these
  repetitive questions.

Throughout this onboarding:
- Keep each of your turns short and conversational, not big essays.
- Speak mostly Russian, adding simple English only as examples.
- Be kind, encouraging and never judgemental.
"""
    return prompt

def build_tutor_system_prompt(
    session: Session,
    user: UserProfile,
    lesson_session_id: Optional[int] = None,
    is_resume: bool = False,
) -> str:
    """
    Build the system prompt for the AI tutor.
    
    Args:
        session: Database session
        user: User profile
        lesson_session_id: Optional ID of the current lesson session (for language mode and session-scoped rules)
    
    Returns:
        Complete system prompt string
    """
    if not user:
        return "You are an English tutor. The user profile could not be loaded, so please be polite and ask for their name."

    # If this is the student's very first lesson and intro is not yet completed,
    # use the dedicated onboarding prompt instead of the big generic one.
    if should_run_intro_session(session, user, lesson_session_id):
        return build_intro_system_prompt(user)

    # 1. Fetch Legacy System Rules (backward compatibility)
    legacy_rules = session.exec(
        select(TutorSystemRule)
        .where(TutorSystemRule.enabled == True)
        .order_by(TutorSystemRule.sort_order)
    ).all()
    
    # 2. Fetch New TutorRule (active, global + student-specific + session-scoped)
    new_rules_statement = select(TutorRule).where(TutorRule.is_active == True)
    
    # Get global rules
    global_rules = session.exec(
        new_rules_statement.where(TutorRule.scope == "global")
        .order_by(TutorRule.priority)
    ).all()
    
    # Get student-specific rules
    student_rules = session.exec(
        new_rules_statement
        .where(TutorRule.scope == "student")
        .where(TutorRule.applies_to_student_id == user.user_account_id)
        .order_by(TutorRule.priority)
    ).all()
    
    # Get session-scoped rules (if lesson_session_id provided)
    session_rules = []
    if lesson_session_id:
        session_rules = session.exec(
            new_rules_statement
            .where(TutorRule.scope == "session")
            .order_by(TutorRule.priority)
        ).all()
    
    # Combine all new rules
    all_new_rules = list(global_rules) + list(student_rules) + list(session_rules)
    
    # 3. Fetch Language Mode and pause metadata (if lesson_session_id provided)
    language_mode = None
    language_level = None
    pause_count = 0
    last_pause_summary: Optional[str] = None
    if lesson_session_id:
        lesson = session.get(LessonSession, lesson_session_id)
        if lesson:
            language_mode = lesson.language_mode
            language_level = lesson.language_level

            # Pause metadata is stored in LessonPauseEvent to avoid altering the existing lesson_sessions schema.
            pause_events = session.exec(
                select(LessonPauseEvent)
                .where(LessonPauseEvent.lesson_session_id == lesson_session_id)
                .order_by(LessonPauseEvent.paused_at)
            ).all()
            pause_count = len(pause_events)
            if pause_events:
                last_event = pause_events[-1]
                last_pause_summary = last_event.summary_text
    
    # 4. Fetch User Preferences
    try:
        prefs = json.loads(user.preferences)
    except Exception:
        prefs = {}
    preferred_address = prefs.get("preferred_address")
    intro_prefs = prefs.get("intro") or {}
    
    # 5. Fetch Memory
    memory = get_tutor_memory_for_user(session, user.id)
    
    # 6. Construct Prompt
    prompt_parts = []
    
    # Base Identity
    prompt_parts.append("You are a personal English tutor for a Russian-speaking student.")

    # --- UNIVERSAL GREETING PROTOCOL ---
    prompt_parts.append("""
\\n**🚀 UNIVERSAL GREETING PROTOCOL (STRICT):**
When the lesson starts (first interaction), you MUST follow this sequence:
1. **Greet briefly**: Use the student's name if known. Be warm but concise.
2. **Contextual Bridge**: If there is a 'last_summary' in your memory, briefly mention it (e.g., "Last time we practiced X").
3. **IMMEDIATE ACTIVITY**: Do NOT ask "What do you want to do?". Instead, propose a specific simple activity or ask a warm-up question related to their level/goals.
   - Example: "Let's start with a quick warm-up. Tell me about your day in 3 sentences."
   - Example: "I remember you wanted to improve fluency. Let's discuss [Topic]."

**⛔ NEGATIVE CONSTRAINTS (NEVER DO THIS):**
- NEVER ask: "How would you like to conduct this lesson?"
- NEVER ask: "What is your plan for today?"
- NEVER ask: "Shall we start?" (Just start!)
- NEVER say: "I am ready to help you." (Just help!)
""")
    
    # --- LANGUAGE MODE SECTION (CRITICAL) ---
    prompt_parts.append("\\n**🗣️ LANGUAGE MODE FOR THIS SESSION:**")
    
    if language_mode is None and lesson_session_id:
        # Language mode not set - must ask at the start
        prompt_parts.append("""
**⚠️ FIRST INTERACTION - LANGUAGE SELECTION REQUIRED:**

This is the student's FIRST message in this session. You MUST:

1. **Greet warmly in Russian** (e.g., "Привет! Я твой друг-репетитор!")

2. **Ask this question in simple Russian:**
   "Скажи, пожалуйста, как тебе удобнее сегодня заниматься:
    — только по-английски,
    — только по-русски,
    — или вперемешку (иногда русский, иногда английский)?"

3. **Parse their response** and determine mode:
   - "только английский" / "english only" / "по-английски" / "английский" → EN_ONLY
   - "только русский" / "russian only" / "по-русски" / "русский" → RU_ONLY  
   - "смешать" / "вперемешку" / "и так и так" / "mixed" / "чуть-чуть" → MIXED

4. **In your first response, include a hidden marker:** 
   After your greeting and question, add on a new line: `[LANGUAGE_MODE: NOT_YET_CHOSEN]`
   
5. **After student responds, detect their choice and include:**
   `[LANGUAGE_MODE_DETECTED: EN_ONLY]` or `[LANGUAGE_MODE_DETECTED: RU_ONLY]` or `[LANGUAGE_MODE_DETECTED: MIXED]`

6. **Confirm their choice warmly** and begin the lesson in that mode.

**This language selection happens ONLY ONCE per session.**
""")
    elif language_mode == "EN_ONLY":
        prompt_parts.append("""
**Mode: English Only** 🇬🇧

- Speak 95%+ in English
- Use simple, clear English appropriate for student's level
- Use Russian ONLY for critical clarifications if student is completely stuck
- Praise English usage: "Great job speaking English!"
- Gently encourage: "Try to answer in English, you can do it!"
""")
    elif language_mode == "RU_ONLY":
        prompt_parts.append("""
**Mode: Russian Only** 🇷🇺

- Explain concepts and give instructions in Russian
- Introduce English words/phrases as learning material with Russian translations
- Practice pronunciation of English words
- Keep all feedback and meta-commentary in Russian
- Example: "Давай выучим слово 'app le' - это 'яблоко'. Repeat after me: apple."
""")
    elif language_mode == "MIXED":
        level_desc = f" (Level {language_level}/5)" if language_level else ""
        prompt_parts.append(f"""
**Mode: Mixed (Adaptive)**{level_desc} 🌐

- Balance Russian and English based on student comfort
- Start with comfortable amount of Russian
- Gradually increase English proportion as student succeeds
- Monitor reactions - if student struggles, add more Russian
- Every 10-15 successful exchanges, subtly increase English
- After ~5-10 minutes of success, offer upgrade:
  "Как ты себя чувствуешь? Хочешь попробовать чуть больше английского? Если что, всегда можно вернуться на русский!"
- If student agrees, mark: `[LANGUAGE_LEVEL_UP]` and increase English
""")
    
    # --- NEW RULES BY TYPE ---
   # Group new rules by type for better organization
    greeting_rules = [r for r in all_new_rules if r.type == "greeting"]
    toxicity_rules = [r for r in all_new_rules if r.type == "toxicity_warning"]
    difficulty_rules = [r for r in all_new_rules if r.type == "difficulty_adjustment"]
    language_mode_rules = [r for r in all_new_rules if r.type == "language_mode"]
    other_rules = [r for r in all_new_rules if r.type == "other"]
    
    # Apply Language Mode Rules (in addition to built-in mode behavior)
    if language_mode_rules:
        prompt_parts.append("\\n**Language Mode Rules (from Admin):**")
        for rule in language_mode_rules:
            prompt_parts.append(f"- {rule.description}")
            if rule.action:
                try:
                    action = json.loads(rule.action)
                    for key, value in action.items():
                        prompt_parts.append(f"  {key}: {value}")
                except:
                    pass
    
    # Apply Greeting Rules
    if greeting_rules:
        prompt_parts.append("\\n**Greeting Instructions:**")
        for rule in greeting_rules:
            prompt_parts.append(f"- {rule.description}")
            if rule.action:
                try:
                    action = json.loads(rule.action)
                    if "say" in action:
                        prompt_parts.append(f"  Use this greeting: \"{action['say']}\"")
                except:
                    pass
    
    # Apply Toxicity Rules
    if toxicity_rules:
        prompt_parts.append("\\n**Behavior Rules:**")
        for rule in toxicity_rules:
            prompt_parts.append(f"- {rule.description}")
            if rule.trigger_condition:
                try:
                    condition = json.loads(rule.trigger_condition)
                    prompt_parts.append(f"  Trigger: {json.dumps(condition)}")
                except:
                    pass
            if rule.action:
                try:
                    action = json.loads(rule.action)
                    if "say" in action:
                        prompt_parts.append(f"  Action: Say \"{action['say']}\"")
                except:
                    pass
   
    # Apply Difficulty Rules
    if difficulty_rules:
        prompt_parts.append("\\n**Difficulty Adaptation:**")
        for rule in difficulty_rules:
            prompt_parts.append(f"- {rule.description}")
    
    # Apply Other Rules
    if other_rules:
        prompt_parts.append("\\n**Additional Rules:**")
        for rule in other_rules:
            prompt_parts.append(f"- {rule.description}")
    
    # Legacy System Rules (for backward compatibility)
    if legacy_rules:
        prompt_parts.append("\\n**System Rules:**")
        for rule in legacy_rules:
            prompt_parts.append(f"- {rule.rule_text}")
            
    # Personalization
    prompt_parts.append("\\n**Student Context:**")
    prompt_parts.append(f"Name: {user.name}")
    prompt_parts.append(f"Level: {user.english_level}")

    # Intro-based personalization (from onboarding)
    if intro_prefs:
        tutor_name = intro_prefs.get("tutor_name")
        if tutor_name:
            prompt_parts.append(
                f"TutorName (how the student calls you): {tutor_name}"
            )
            prompt_parts.append(
                "When you introduce yourself in Russian, say \"Меня зовут "
                f"{tutor_name}\" and consistently use this name."
            )

        addressing_mode = intro_prefs.get("addressing_mode")
        if addressing_mode in ["ty", "vy"]:
            if addressing_mode == "ty":
                mode_desc = "ты (informal, friendly)"
                mode_word = "ты"
            else:
                mode_desc = "вы (formal, respectful)"
                mode_word = "вы"
            prompt_parts.append(
                "When speaking Russian, ALWAYS address the student using "
                f"\"{mode_word}\" ({mode_desc}). Do not switch unless the student explicitly asks."
            )

        conversation_style = intro_prefs.get("conversation_style")
        humor_allowed = intro_prefs.get("humor_allowed")
        if conversation_style or humor_allowed is not None:
            prompt_parts.append("\\n**Style Preferences (from onboarding):**")
            if conversation_style == "informal":
                prompt_parts.append(
                    "- Use a relatively informal, relaxed tone. You may use simple jokes and light slang, "
                    "but stay kind and supportive."
                )
            elif conversation_style == "formal":
                prompt_parts.append(
                    "- Use a more formal, teacher-like tone. Avoid slang and too many jokes."
                )
            if humor_allowed is True:
                prompt_parts.append(
                    "- Light humor is allowed if it helps the student relax."
                )
            elif humor_allowed is False:
                prompt_parts.append(
                    "- Avoid jokes and sarcasm; keep communication neutral and respectful."
                )

        goals = intro_prefs.get("goals") or []
        topics = intro_prefs.get("topics_interest") or []
        if goals or topics:
            prompt_parts.append("\\n**Student Goals and Interests (from onboarding):**")
            if goals:
                goals_str = ", ".join(str(g) for g in goals)
                prompt_parts.append(f"- Goals: {goals_str}")
            if topics:
                topics_str = ", ".join(str(t) for t in topics)
                prompt_parts.append(f"- Topics they enjoy: {topics_str}")

        correction_style = intro_prefs.get("correction_style")
        if correction_style:
            prompt_parts.append("\\n**Error Correction Preference (from onboarding):**")
            if correction_style == "often":
                prompt_parts.append(
                    "- The student wants frequent corrections. Correct most clear mistakes, but still be gentle."
                )
            elif correction_style == "on_request":
                prompt_parts.append(
                    "- Correct mainly when the student asks you to, or when a mistake is blocking understanding."
                )
            elif correction_style == "soft":
                prompt_parts.append(
                    "- Correct softly without interrupting their speech too much. Prioritize fluency over perfection."
                )

    if preferred_address:
        prompt_parts.append(f"Preferred Address: {preferred_address}")
    else:
        prompt_parts.append("Preferred Address: Not set. You should politely ask for it in the first message.")

    # --- ABSOLUTE BEGINNER CURRICULUM INJECTION ---
    # Check if user is beginner (A1 or explicit "Absolute Beginner")
    if user.english_level in ["A1", "Beginner", "Absolute Beginner", "Zero"]:
        try:
            import os
            rules_path = os.path.join(os.getcwd(), "app", "data", "tutor_rules_beginner.json")
            if os.path.exists(rules_path):
                with open(rules_path, "r", encoding="utf-8") as f:
                    beginner_rules = json.load(f)
                
                prompt_parts.append("\\n**🎓 SPECIAL CURRICULUM: ABSOLUTE BEGINNER**")
                prompt_parts.append("You are teaching a complete beginner. Follow this strict structure.")
                
                prompt_parts.append(f"\\n**Goals:**")
                for g in beginner_rules.get('goals', []):
                    prompt_parts.append(f"- {g}")
                
                prompt_parts.append("\\n**Teaching Principles (CRITICAL):**")
                for p in beginner_rules.get('teaching_principles', []):
                    prompt_parts.append(f"- {p}")
                    
                prompt_parts.append("\\n**⛔ FORBIDDEN (DO NOT DO THIS):**")
                for f in beginner_rules.get('forbidden', []):
                    prompt_parts.append(f"- {f}")
                    
                prompt_parts.append("\\n**📋 Lesson Structure (Follow strictly step-by-step):**")
                for step in beginner_rules.get('lesson_structure', []):
                    prompt_parts.append(f"Step {step['step']} [{step['name']}]: {step['description']}")
                    prompt_parts.append(f"   Example: \"{step['example']}\"")
                    
                prompt_parts.append("\\n**Core Vocabulary (Limit yourself to these):**")
                cats = beginner_rules.get('core_categories', {})
                for cat, words in cats.items():
                    prompt_parts.append(f"- {cat}: {', '.join(words)}")
                    
                prompt_parts.append("\\n**Grammar Explanations:**")
                for rule in beginner_rules.get('grammar_rules', []):
                    prompt_parts.append(f"- {rule['rule']}: {rule['explanation']}")
                    
        except Exception as e:
            # Fallback or log error
            prompt_parts.append(f"\\n[System Error loading beginner rules: {str(e)}]")

    # Memory
    prompt_parts.append("\\n**Memory:**")
    if memory["last_summary"]:
        prompt_parts.append(f"Last Lesson Summary: {memory['last_summary']}")
    if memory["weak_words"]:
        prompt_parts.append(f"Weak Words to Practice: {', '.join(memory['weak_words'])}")

    # Pause / Resume context
    if lesson_session_id and pause_count > 0:
        prompt_parts.append("\\n**Pause / Resume Context:**")
        prompt_parts.append(f"This lesson has been paused {pause_count} time(s) before.")
        if last_pause_summary:
            prompt_parts.append(f"Most recent pause summary (what you did before the break): {last_pause_summary}")

    # If this is a resumed session, instruct the tutor how to continue
    if is_resume:
        prompt_parts.append("""\n**⏸️ RESUMED LESSON BEHAVIOR (AFTER A BREAK):**
- The student has come back to the SAME lesson after a pause.
- In your VERY NEXT MESSAGE you MUST:
  1) Start with a very short "welcome back" style greeting (1–2 short sentences).
  2) If you have a pause summary, briefly remind the student what you were doing before the break (in simple English).
  3) Immediately continue the planned activity from where you stopped. Do NOT repeat your full introduction or the full lesson plan.
- Keep this welcome-back moment SHORT, warm, and practical. Then go back into interactive practice.
""")
        
    # Standard Instructions (can be partially replaced by rules, but keeping core logic here)
    prompt_parts.append("""\n**Core Behavior:**
- Speak slowly and clearly.
- Adapt to the student's level.
- If the student makes a mistake, correct it gently and explain briefly.
- Answer primarily based on the language mode set above.
- Keep your turns SHORT: usually 1–3 short sentences, then stop and wait.
- Never monologue for a long time; give the student frequent chances to speak.
- If the student starts speaking (interrupts you), IMMEDIATELY stop your idea, listen,
  and then continue your explanation taking into account what they just said.
- Prefer many short interactive exchanges over one long explanation.
""")

    return "\\n".join(prompt_parts)
