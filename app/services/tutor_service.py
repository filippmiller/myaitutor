import json
from typing import Optional
from sqlmodel import Session, select
from app.models import UserProfile, UserState, TutorSystemRule, SessionSummary, TutorRule, LessonSession
from app.security import ADMIN_EMAIL

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

def build_tutor_system_prompt(session: Session, user: UserProfile, lesson_session_id: Optional[int] = None) -> str:
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

    # 1. Fetch Legacy System Rules (backward compatibility)
    legacy_rules = session.exec(select(TutorSystemRule).where(TutorSystemRule.enabled == True).order_by(TutorSystemRule.sort_order)).all()
    
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
    
    # 3. Fetch Language Mode (if lesson_session_id provided)
    language_mode = None
    language_level = None
    if lesson_session_id:
        lesson = session.get(LessonSession, lesson_session_id)
        if lesson:
            language_mode = lesson.language_mode
            language_level = lesson.language_level
    
    # 4. Fetch User Preferences
    prefs = json.loads(user.preferences)
    preferred_address = prefs.get("preferred_address")
    
    # 5. Fetch Memory
    memory = get_tutor_memory_for_user(session, user.id)
    
    # 6. Construct Prompt
    prompt_parts = []
    
    # Base Identity
    prompt_parts.append("You are a personal English tutor for a Russian-speaking student.")
    
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
        
    # Standard Instructions (can be partially replaced by rules, but keeping core logic here)
    prompt_parts.append("""
**Core Behavior:**
- Speak slowly and clearly.
- Adapt to the student's level.
- If the student makes a mistake, correct it gently and explain briefly.
- Answer primarily based on the language mode set above.
""")

    return "\\n".join(prompt_parts)
