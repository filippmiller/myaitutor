"""
Simplified Prompt Builder for AIlingva

This module builds focused, concise system prompts that are:
1. Short enough for the model to actually follow
2. Strict about language enforcement
3. Modular and easy to extend with dynamic rules

Philosophy: Less is more. A 100-line focused prompt beats a 700-line essay.
"""

import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

from app.models import (
    UserProfile,
    TutorStudentKnowledge,
    TutorRule,
    SessionSummary,
    UserState,
    LessonSession,
    LessonPauseEvent,
)
from app.services.language_enforcement import get_language_enforcement_prompt, LanguageMode


# ============================================================
# CORE IDENTITY (Never changes)
# ============================================================

CORE_IDENTITY = """You are an AI English tutor for Russian-speaking students.

CRITICAL RULES (NEVER VIOLATE):
1. ONLY speak English and Russian. NEVER Spanish, French, German, Italian, Portuguese.
2. Keep responses SHORT: 1-3 sentences, then WAIT for student.
3. Be warm, patient, supportive. Never judge.
4. If student interrupts, STOP and listen.
5. Start activities IMMEDIATELY. Don't ask "what do you want to do?"
"""


# ============================================================
# FIRST LESSON (Onboarding)
# ============================================================

FIRST_LESSON_INTRO = """
🎯 THIS IS THE STUDENT'S FIRST LESSON

Your goal: Get to know them and collect basic info.
Speak RUSSIAN for this intro (they're beginners).

COLLECT (in order):
1. Your name - ask what they want to call you (Mike, Kate, etc.)
2. Their name - how to address them
3. Ты/Вы preference - ask which is comfortable
4. Their English level (1-10 scale, where 1=nothing, 10=fluent)
5. Why they need English (work, travel, etc.)

IMPORTANT: Use the update_profile function to save information SILENTLY.
Do NOT speak the data aloud - just call the function in the background.

Examples of when to call update_profile:
- Student says "Зови меня Майк" → call update_profile(tutor_name="Майк")
- Student says "Меня зовут Вася" → call update_profile(student_name="Вася")
- Student says "На ты" → call update_profile(addressing_mode="ty")
- Student rates themselves "3 из 10" → call update_profile(english_level_scale_1_10=3)

When done with intro:
Call update_profile(intro_completed=true)

Keep it CONVERSATIONAL, not like a form. Be friendly!
"""


# ============================================================
# REGULAR LESSON GREETING
# ============================================================

REGULAR_GREETING_TEMPLATE = """
🎯 GREETING PROTOCOL (First message only)

Student: {student_name}
Level: {level}
{last_summary_line}

YOUR FIRST MESSAGE MUST:
1. Greet by name: "Hi {student_name}!" or "Привет, {student_name}!"
2. {context_bridge}
3. START an activity immediately - don't ask what they want

Example good greeting:
"Hi {student_name}! Last time we practiced colors. Let's continue - what color is the sky?"

Example BAD greeting (NEVER DO THIS):
"Hello! How would you like to conduct today's lesson?"
"""


# ============================================================
# LEVEL-SPECIFIC INSTRUCTIONS
# ============================================================

LEVEL_INSTRUCTIONS = {
    "A1": """
LEVEL: ABSOLUTE BEGINNER (A1)
- Use VERY simple words: I, you, want, like, go, see, hello, yes, no
- Speak slowly, 1 sentence at a time
- After each phrase: "Repeat, please" / "Повтори, пожалуйста"
- Explain EVERYTHING in Russian, teach English words one by one
- Max 3-5 new words per lesson
- Praise EVERY correct answer
""",
    "A2": """
LEVEL: ELEMENTARY (A2)
- Simple sentences, basic grammar (present simple, past simple)
- Mix Russian explanations with English practice
- Introduce 5-10 new words per lesson
- Focus on everyday topics: family, food, time, shopping
""",
    "B1": """
LEVEL: INTERMEDIATE (B1)
- Speak mostly English, Russian for complex explanations only
- Practice all tenses, introduce conditionals
- Encourage longer responses (3-5 sentences)
- Topics: travel, work, opinions, experiences
""",
    "B2": """
LEVEL: UPPER-INTERMEDIATE (B2)
- Speak 90%+ English
- Natural conversation pace
- Discuss abstract topics, news, culture
- Correct subtle grammar/vocabulary errors
""",
    "C1": """
LEVEL: ADVANCED (C1)
- Full English immersion
- Discuss complex topics: philosophy, science, politics
- Focus on nuance, idioms, advanced vocabulary
- Challenge them with complex questions
""",
}


# ============================================================
# PROMPT BUILDER CLASS
# ============================================================

class PromptBuilder:
    """
    Builds focused, modular system prompts.

    Usage:
        builder = PromptBuilder(session, user_profile)
        prompt = builder.build()
    """

    def __init__(
        self,
        db_session: Session,
        profile: Optional[UserProfile],
        lesson_session_id: Optional[int] = None,
        is_resume: bool = False,
    ):
        self.db = db_session
        self.profile = profile
        self.lesson_session_id = lesson_session_id
        self.is_resume = is_resume

        # Loaded data
        self.knowledge: Optional[TutorStudentKnowledge] = None
        self.language_mode: Optional[str] = None
        self.last_summary: Optional[str] = None
        self.dynamic_rules: List[TutorRule] = []
        self.weak_words: List[str] = []
        self.is_first_lesson: bool = False

    def _load_data(self):
        """Load all necessary data from database."""
        if not self.profile:
            return

        user_id = self.profile.user_account_id

        # Guard against None user_id
        if not user_id:
            logger.warning("Profile has no user_account_id, skipping data load")
            return

        # Load student knowledge
        self.knowledge = self.db.get(TutorStudentKnowledge, user_id)

        # Check if first lesson
        if self.knowledge:
            self.is_first_lesson = not self.knowledge.first_lesson_completed
        else:
            self.is_first_lesson = True

        # Load language mode from lesson session
        if self.lesson_session_id:
            lesson = self.db.get(LessonSession, self.lesson_session_id)
            if lesson:
                self.language_mode = lesson.language_mode

        # Load last summary
        last_summary = self.db.exec(
            select(SessionSummary)
            .where(SessionSummary.user_account_id == user_id)
            .order_by(SessionSummary.created_at.desc())
            .limit(1)
        ).first()
        if last_summary:
            self.last_summary = last_summary.summary_text

        # Load weak words from UserState
        user_state = self.db.exec(
            select(UserState).where(UserState.user_account_id == user_id)
        ).first()
        if user_state:
            self.weak_words = user_state.weak_words or []

        # Load weak words from TutorStudentKnowledge too
        if self.knowledge and self.knowledge.vocabulary_json:
            weak = self.knowledge.vocabulary_json.get("weak", [])
            for w in weak:
                if isinstance(w, dict):
                    word = w.get("word", "")
                    if word and word not in self.weak_words:
                        self.weak_words.append(word)
                elif isinstance(w, str) and w not in self.weak_words:
                    self.weak_words.append(w)

        # Load dynamic rules (active, global + student-specific)
        rules_query = select(TutorRule).where(TutorRule.is_active == True)

        global_rules = self.db.exec(
            rules_query.where(TutorRule.scope == "global")
            .order_by(TutorRule.priority)
            .limit(10)  # Limit to prevent prompt bloat
        ).all()

        student_rules = self.db.exec(
            rules_query
            .where(TutorRule.scope == "student")
            .where(TutorRule.applies_to_student_id == user_id)
            .order_by(TutorRule.priority)
            .limit(5)
        ).all()

        self.dynamic_rules = list(global_rules) + list(student_rules)

    def _get_student_name(self) -> str:
        """Get student's display name."""
        if self.profile and self.profile.name:
            return self.profile.name
        return "Student"

    def _get_level(self) -> str:
        """Get student's English level."""
        # Prefer knowledge level, fallback to profile
        if self.knowledge and self.knowledge.level:
            return self.knowledge.level
        if self.profile and self.profile.english_level:
            return self.profile.english_level
        return "A1"

    def _get_preferences(self) -> dict:
        """Parse profile preferences."""
        if not self.profile:
            return {}
        try:
            return json.loads(self.profile.preferences or "{}")
        except:
            return {}

    def _build_intro_prompt(self) -> str:
        """Build prompt for first-time onboarding."""
        parts = [
            CORE_IDENTITY,
            FIRST_LESSON_INTRO,
            get_language_enforcement_prompt(None),  # No mode set yet
        ]

        if self.profile and self.profile.name:
            parts.append(f"\nCurrent placeholder name: {self.profile.name}")

        return "\n".join(parts)

    def _build_regular_prompt(self) -> str:
        """Build prompt for regular lessons."""
        parts = []

        # 1. Core identity
        parts.append(CORE_IDENTITY)

        # 2. Language enforcement (CRITICAL)
        parts.append(get_language_enforcement_prompt(self.language_mode))

        # 3. Level-specific instructions
        level = self._get_level()
        level_key = level.upper() if level else "A1"
        if level_key in LEVEL_INSTRUCTIONS:
            parts.append(LEVEL_INSTRUCTIONS[level_key])
        else:
            parts.append(LEVEL_INSTRUCTIONS["A1"])

        # 4. Greeting protocol (only if not resuming)
        if not self.is_resume:
            student_name = self._get_student_name()

            # Context bridge
            if self.last_summary:
                context_bridge = f"Mention briefly: '{self.last_summary}'"
                last_summary_line = f"Last lesson: {self.last_summary}"
            else:
                context_bridge = "This is their first regular lesson after intro"
                last_summary_line = "No previous lesson summary"

            greeting = REGULAR_GREETING_TEMPLATE.format(
                student_name=student_name,
                level=level,
                last_summary_line=last_summary_line,
                context_bridge=context_bridge,
            )
            parts.append(greeting)
        else:
            # Resume greeting
            parts.append(f"""
🔄 RESUMED LESSON
Student came back after a pause.
- Say "Welcome back, {self._get_student_name()}!" (short)
- Briefly mention what you were doing before
- Continue immediately - don't restart from beginning
""")

        # 5. Personalization from preferences
        prefs = self._get_preferences()
        intro = prefs.get("intro", {})

        personalization = []

        tutor_name = intro.get("tutor_name")
        if tutor_name:
            personalization.append(f"Your name (how student calls you): {tutor_name}")

        addressing_mode = intro.get("addressing_mode")
        if addressing_mode == "ty":
            personalization.append("Address student with 'ты' (informal)")
        elif addressing_mode == "vy":
            personalization.append("Address student with 'вы' (formal)")

        correction_style = intro.get("correction_style")
        if correction_style == "often":
            personalization.append("Student wants frequent corrections")
        elif correction_style == "soft":
            personalization.append("Correct softly, prioritize fluency")
        elif correction_style == "on_request":
            personalization.append("Only correct when asked")

        goals = intro.get("goals", [])
        if goals:
            personalization.append(f"Student goals: {', '.join(goals)}")

        topics = intro.get("topics_interest", [])
        if topics:
            personalization.append(f"Topics they enjoy: {', '.join(topics)}")

        if personalization:
            parts.append("\n📋 STUDENT PREFERENCES:")
            parts.append("\n".join(f"- {p}" for p in personalization))

        # 6. Weak words to practice
        if self.weak_words:
            parts.append(f"\n⚠️ WEAK WORDS (practice these):\n{', '.join(self.weak_words[:10])}")

        # 7. Dynamic rules (keep it short)
        if self.dynamic_rules:
            parts.append("\n📌 ACTIVE RULES:")
            for rule in self.dynamic_rules[:5]:  # Max 5 rules
                parts.append(f"- [{rule.type}] {rule.description}")

        # 8. Final reminder
        parts.append("""
🎯 REMEMBER:
- Keep responses SHORT (1-3 sentences)
- WAIT for student after each response
- Start activities immediately
- ONLY English and Russian
""")

        return "\n".join(parts)

    def build(self) -> str:
        """
        Build the complete system prompt.

        Returns:
            Complete system prompt string
        """
        self._load_data()

        # If first lesson and intro not completed, use intro prompt
        if self.is_first_lesson:
            prefs = self._get_preferences()
            intro = prefs.get("intro", {})
            if not intro.get("intro_completed"):
                logger.info("Building INTRO prompt (first lesson)")
                return self._build_intro_prompt()

        # Regular lesson prompt
        logger.info(f"Building REGULAR prompt (level: {self._get_level()}, mode: {self.language_mode})")
        return self._build_regular_prompt()

    def get_prompt_summary(self) -> dict:
        """Get a summary of what was built (for debugging)."""
        return {
            "is_first_lesson": self.is_first_lesson,
            "language_mode": self.language_mode,
            "level": self._get_level(),
            "student_name": self._get_student_name(),
            "has_last_summary": bool(self.last_summary),
            "weak_words_count": len(self.weak_words),
            "dynamic_rules_count": len(self.dynamic_rules),
            "is_resume": self.is_resume,
        }


def build_simple_prompt(
    db_session: Session,
    profile: Optional[UserProfile],
    lesson_session_id: Optional[int] = None,
    is_resume: bool = False,
) -> str:
    """
    Convenience function to build a prompt.

    This is a drop-in replacement for the old build_tutor_system_prompt.
    """
    builder = PromptBuilder(
        db_session=db_session,
        profile=profile,
        lesson_session_id=lesson_session_id,
        is_resume=is_resume,
    )
    return builder.build()
