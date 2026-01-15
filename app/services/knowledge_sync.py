"""
Knowledge Sync Service for AIlingva

This service synchronizes data between different parts of the system:
1. UserProfile.preferences (from intro/onboarding) → TutorStudentKnowledge (brain)
2. UserState (legacy weak/known words) → TutorStudentKnowledge
3. Ensures the "brain" always has the latest student information

The brain needs to know everything about the student to make intelligent decisions.
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlmodel import Session, select

from app.models import (
    UserProfile,
    UserState,
    TutorStudentKnowledge,
    TutorBrainEvent,
    UserAccount,
)

logger = logging.getLogger(__name__)


# ============================================================
# Level Mapping
# ============================================================

def scale_1_10_to_cefr(scale: int) -> str:
    """
    Convert 1-10 self-assessment scale to CEFR level.

    1-2: A1 (Absolute Beginner)
    3-4: A2 (Elementary)
    5-6: B1 (Intermediate)
    7-8: B2 (Upper-Intermediate)
    9:   C1 (Advanced)
    10:  C2 (Proficient)
    """
    if scale <= 2:
        return "A1"
    elif scale <= 4:
        return "A2"
    elif scale <= 6:
        return "B1"
    elif scale <= 8:
        return "B2"
    elif scale == 9:
        return "C1"
    else:
        return "C2"


def cefr_to_scale_1_10(cefr: str) -> int:
    """Convert CEFR level back to approximate 1-10 scale."""
    mapping = {
        "A1": 2,
        "A2": 4,
        "B1": 5,
        "B2": 7,
        "C1": 9,
        "C2": 10,
    }
    return mapping.get(cefr.upper(), 5)


# ============================================================
# Knowledge Sync Functions
# ============================================================

def get_or_create_knowledge(session: Session, user_id: int) -> TutorStudentKnowledge:
    """Get existing knowledge record or create a new one."""
    knowledge = session.get(TutorStudentKnowledge, user_id)

    if not knowledge:
        knowledge = TutorStudentKnowledge(
            user_id=user_id,
            level="A1",
            lesson_count=0,
            first_lesson_completed=False,
            vocabulary_json={"weak": [], "strong": [], "neutral": []},
            grammar_json={"patterns": {}, "mistakes": {}},
            topics_json={"covered": [], "to_practice": []},
            meta_json={},
        )
        session.add(knowledge)
        session.commit()
        session.refresh(knowledge)
        logger.info(f"Created new TutorStudentKnowledge for user {user_id}")

    return knowledge


def sync_intro_to_knowledge(
    session: Session,
    profile: UserProfile,
    create_event: bool = True,
) -> TutorStudentKnowledge:
    """
    Sync intro/onboarding data from UserProfile.preferences to TutorStudentKnowledge.

    This should be called after intro is completed to ensure the brain has all
    the information it needs.

    Args:
        session: Database session
        profile: User profile with preferences
        create_event: Whether to create a brain event for this sync

    Returns:
        Updated TutorStudentKnowledge
    """
    if not profile or not profile.user_account_id:
        logger.warning("Cannot sync: no profile or user_account_id")
        return None

    user_id = profile.user_account_id
    knowledge = get_or_create_knowledge(session, user_id)

    # Parse preferences
    try:
        prefs = json.loads(profile.preferences or "{}")
    except:
        prefs = {}

    intro = prefs.get("intro", {})
    changes_made = []

    # 1. Sync level from self-assessment
    scale_level = intro.get("english_level_scale_1_10")
    if scale_level:
        new_level = scale_1_10_to_cefr(scale_level)
        if knowledge.level != new_level:
            knowledge.level = new_level
            changes_made.append(f"level: {new_level} (from scale {scale_level})")

    # Also sync from profile.english_level if set
    if profile.english_level and not scale_level:
        knowledge.level = profile.english_level
        changes_made.append(f"level: {profile.english_level} (from profile)")

    # 2. Sync intro completion status
    if intro.get("intro_completed") and not knowledge.first_lesson_completed:
        knowledge.first_lesson_completed = True
        changes_made.append("first_lesson_completed: True")

    # 3. Sync goals to meta
    goals = intro.get("goals", [])
    if goals:
        knowledge.meta_json["goals"] = goals
        changes_made.append(f"goals: {goals}")

    # 4. Sync topics of interest
    topics = intro.get("topics_interest", [])
    if topics:
        knowledge.meta_json["topics_interest"] = topics
        # Also add to topics to practice
        knowledge.topics_json["to_practice"] = list(set(
            knowledge.topics_json.get("to_practice", []) + topics
        ))
        changes_made.append(f"topics_interest: {topics}")

    # 5. Sync learning preferences
    correction_style = intro.get("correction_style")
    if correction_style:
        knowledge.meta_json["correction_style"] = correction_style
        changes_made.append(f"correction_style: {correction_style}")

    addressing_mode = intro.get("addressing_mode")
    if addressing_mode:
        knowledge.meta_json["addressing_mode"] = addressing_mode
        changes_made.append(f"addressing_mode: {addressing_mode}")

    tutor_name = intro.get("tutor_name")
    if tutor_name:
        knowledge.meta_json["tutor_name"] = tutor_name
        changes_made.append(f"tutor_name: {tutor_name}")

    # 6. Sync native language and other languages
    native_lang = intro.get("native_language")
    if native_lang:
        knowledge.meta_json["native_language"] = native_lang
        changes_made.append(f"native_language: {native_lang}")

    other_langs = intro.get("other_languages", [])
    if other_langs:
        knowledge.meta_json["other_languages"] = other_langs
        changes_made.append(f"other_languages: {other_langs}")

    # Update timestamp
    knowledge.updated_at = datetime.utcnow()

    # Commit changes
    session.add(knowledge)
    session.commit()

    # Create brain event if requested and changes were made
    if create_event and changes_made:
        event = TutorBrainEvent(
            lesson_id=0,  # No specific lesson
            user_id=user_id,
            turn_id=None,
            pipeline_type="SYNC",
            event_type="KNOWLEDGE_SYNCED_FROM_INTRO",
            event_payload_json={
                "changes": changes_made,
                "timestamp": datetime.utcnow().isoformat(),
            },
            snapshot_student_knowledge_json={
                "level": knowledge.level,
                "first_lesson_completed": knowledge.first_lesson_completed,
                "goals": knowledge.meta_json.get("goals", []),
                "topics_interest": knowledge.meta_json.get("topics_interest", []),
            },
        )
        session.add(event)
        session.commit()

        logger.info(f"Synced intro to knowledge for user {user_id}: {changes_made}")

    return knowledge


def sync_legacy_state_to_knowledge(
    session: Session,
    user_id: int,
) -> TutorStudentKnowledge:
    """
    Sync legacy UserState data (weak_words, known_words) to TutorStudentKnowledge.

    This ensures old data is preserved in the new brain system.
    """
    knowledge = get_or_create_knowledge(session, user_id)

    # Find UserState by user_account_id
    user_state = session.exec(
        select(UserState).where(UserState.user_account_id == user_id)
    ).first()

    if not user_state:
        return knowledge

    changes_made = []

    # Sync weak words
    legacy_weak = user_state.weak_words or []
    if legacy_weak:
        current_weak = knowledge.vocabulary_json.get("weak", [])
        # Convert to new format
        for word in legacy_weak:
            if isinstance(word, str):
                # Check if already exists
                exists = any(
                    (isinstance(w, dict) and w.get("word") == word) or w == word
                    for w in current_weak
                )
                if not exists:
                    current_weak.append({
                        "word": word,
                        "frequency": 1,
                        "source": "legacy_sync",
                        "added_at": datetime.utcnow().isoformat(),
                    })
                    changes_made.append(f"weak_word: {word}")

        knowledge.vocabulary_json["weak"] = current_weak

    # Sync known words
    legacy_known = user_state.known_words or []
    if legacy_known:
        current_strong = knowledge.vocabulary_json.get("strong", [])
        for word in legacy_known:
            if isinstance(word, str) and word not in current_strong:
                current_strong.append(word)
                changes_made.append(f"known_word: {word}")

        knowledge.vocabulary_json["strong"] = current_strong

    # Sync XP and session count to meta
    if user_state.xp_points:
        knowledge.meta_json["legacy_xp"] = user_state.xp_points
    if user_state.session_count:
        knowledge.lesson_count = max(knowledge.lesson_count, user_state.session_count)

    if changes_made:
        knowledge.updated_at = datetime.utcnow()
        session.add(knowledge)
        session.commit()
        logger.info(f"Synced legacy state to knowledge for user {user_id}: {len(changes_made)} changes")

    return knowledge


def sync_all_for_user(session: Session, user_id: int) -> TutorStudentKnowledge:
    """
    Perform full sync for a user: intro + legacy state → knowledge.

    Call this when starting a lesson to ensure brain has latest data.
    """
    # First, get profile
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_account_id == user_id)
    ).first()

    knowledge = None

    # Sync intro if profile exists
    if profile:
        knowledge = sync_intro_to_knowledge(session, profile, create_event=False)

    # Sync legacy state
    knowledge = sync_legacy_state_to_knowledge(session, user_id)

    logger.info(f"Full sync completed for user {user_id}")
    return knowledge


def update_knowledge_from_lesson(
    session: Session,
    user_id: int,
    lesson_data: Dict[str, Any],
) -> TutorStudentKnowledge:
    """
    Update knowledge after a lesson ends.

    Args:
        session: Database session
        user_id: User ID
        lesson_data: Dict containing:
            - weak_words: List of words to add as weak
            - strong_words: List of words to add as strong
            - grammar_patterns: Dict of pattern -> mastery
            - topics_covered: List of topics practiced
            - level_assessment: Optional new level assessment
    """
    knowledge = get_or_create_knowledge(session, user_id)

    # Update weak words
    weak_words = lesson_data.get("weak_words", [])
    current_weak = knowledge.vocabulary_json.get("weak", [])
    for word in weak_words:
        exists = any(
            (isinstance(w, dict) and w.get("word") == word) or w == word
            for w in current_weak
        )
        if not exists:
            current_weak.append({
                "word": word,
                "frequency": 1,
                "added_at": datetime.utcnow().isoformat(),
            })
    knowledge.vocabulary_json["weak"] = current_weak

    # Update strong words (mastered)
    strong_words = lesson_data.get("strong_words", [])
    current_strong = knowledge.vocabulary_json.get("strong", [])
    for word in strong_words:
        if word not in current_strong:
            current_strong.append(word)
            # Remove from weak if it was there
            current_weak = [
                w for w in knowledge.vocabulary_json.get("weak", [])
                if not (isinstance(w, dict) and w.get("word") == word or w == word)
            ]
            knowledge.vocabulary_json["weak"] = current_weak
    knowledge.vocabulary_json["strong"] = current_strong

    # Update grammar patterns
    grammar_patterns = lesson_data.get("grammar_patterns", {})
    current_patterns = knowledge.grammar_json.get("patterns", {})
    for pattern, stats in grammar_patterns.items():
        if pattern not in current_patterns:
            current_patterns[pattern] = {"attempts": 0, "mistakes": 0, "mastery": 0.0}
        current_patterns[pattern]["attempts"] += stats.get("attempts", 0)
        current_patterns[pattern]["mistakes"] += stats.get("mistakes", 0)
        # Recalculate mastery
        attempts = current_patterns[pattern]["attempts"]
        mistakes = current_patterns[pattern]["mistakes"]
        current_patterns[pattern]["mastery"] = 1.0 - (mistakes / max(attempts, 1))
    knowledge.grammar_json["patterns"] = current_patterns

    # Update topics covered
    topics_covered = lesson_data.get("topics_covered", [])
    current_covered = knowledge.topics_json.get("covered", [])
    for topic in topics_covered:
        if topic not in current_covered:
            current_covered.append(topic)
    knowledge.topics_json["covered"] = current_covered

    # Update level if assessed
    level_assessment = lesson_data.get("level_assessment")
    if level_assessment:
        knowledge.level = level_assessment

    # Increment lesson count
    knowledge.lesson_count += 1
    knowledge.updated_at = datetime.utcnow()

    session.add(knowledge)
    session.commit()

    logger.info(f"Updated knowledge for user {user_id} after lesson")
    return knowledge


def get_knowledge_summary(session: Session, user_id: int) -> Dict[str, Any]:
    """
    Get a summary of student knowledge for display/debugging.
    """
    knowledge = session.get(TutorStudentKnowledge, user_id)

    if not knowledge:
        return {
            "exists": False,
            "user_id": user_id,
        }

    weak_words = knowledge.vocabulary_json.get("weak", [])
    strong_words = knowledge.vocabulary_json.get("strong", [])
    patterns = knowledge.grammar_json.get("patterns", {})

    return {
        "exists": True,
        "user_id": user_id,
        "level": knowledge.level,
        "lesson_count": knowledge.lesson_count,
        "first_lesson_completed": knowledge.first_lesson_completed,
        "weak_words_count": len(weak_words),
        "weak_words_sample": [
            (w.get("word") if isinstance(w, dict) else w)
            for w in weak_words[:5]
        ],
        "strong_words_count": len(strong_words),
        "grammar_patterns": list(patterns.keys()),
        "topics_covered": knowledge.topics_json.get("covered", []),
        "goals": knowledge.meta_json.get("goals", []),
        "updated_at": knowledge.updated_at.isoformat() if knowledge.updated_at else None,
    }
