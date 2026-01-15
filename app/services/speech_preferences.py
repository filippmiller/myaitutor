"""
Speech Preferences Detection and Persistence

This module detects user requests for speech modifications (speak slowly,
repeat, etc.) and creates persistent TutorRules so the tutor remembers.
"""

import re
import logging
from typing import Optional, Tuple
from sqlmodel import Session, select
from datetime import datetime

from app.models import TutorRule

logger = logging.getLogger(__name__)

# Patterns to detect "speak slowly" requests in multiple languages
SLOW_SPEECH_PATTERNS = [
    # Russian patterns
    r"говори\s*(по)?медленн",
    r"медленн\w*\s+говори",
    r"помедленн",
    r"не\s+так\s+быстр",
    r"слишком\s+быстр",
    r"чуть\s+медленн",
    r"можешь\s+медленн",
    # English patterns
    r"speak\s+slow",
    r"slow\s*down",
    r"too\s+fast",
    r"slower\s+please",
    r"more\s+slowly",
    r"not\s+so\s+fast",
    r"can\s+you\s+slow",
]

# Compile patterns for efficiency
SLOW_SPEECH_REGEX = re.compile(
    "|".join(SLOW_SPEECH_PATTERNS),
    re.IGNORECASE | re.UNICODE
)


def detect_slow_speech_request(text: str) -> bool:
    """
    Detect if the user is asking the tutor to speak more slowly.

    Args:
        text: User's transcript

    Returns:
        True if slow speech request detected
    """
    if not text:
        return False
    return bool(SLOW_SPEECH_REGEX.search(text))


def get_or_create_slow_speech_rule(
    db: Session,
    user_id: int
) -> Tuple[TutorRule, bool]:
    """
    Get or create a TutorRule for slow speech preference.

    Args:
        db: Database session
        user_id: The student's user ID

    Returns:
        Tuple of (TutorRule, was_created)
    """
    # Check if rule already exists for this student
    existing = db.exec(
        select(TutorRule)
        .where(TutorRule.scope == "student")
        .where(TutorRule.applies_to_student_id == user_id)
        .where(TutorRule.type == "speech_pace")
        .where(TutorRule.is_active == True)
    ).first()

    if existing:
        return existing, False

    # Create new rule
    rule = TutorRule(
        scope="student",
        type="speech_pace",
        title="Speak Slowly",
        description=(
            "ВАЖНО: Этот ученик просил говорить МЕДЛЕННО. "
            "Говори с паузами между фразами. Используй '...' для пауз. "
            "IMPORTANT: This student requested SLOW speech. "
            "Speak with clear pauses between phrases. Use '...' for pauses. "
            "Example: 'The phone... is next to... the black computer.'"
        ),
        trigger_condition=None,
        action='{"speech_pace": "slow", "use_pauses": true}',
        priority=100,  # High priority
        is_active=True,
        applies_to_student_id=user_id,
        created_by="system",
        updated_by="system",
        source="voice_detection",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(rule)
    db.commit()
    db.refresh(rule)

    logger.info(f"Created SLOW_SPEECH rule for user {user_id}")
    return rule, True


def process_user_speech_preferences(
    db: Session,
    user_id: int,
    transcript: str
) -> Optional[TutorRule]:
    """
    Process a user's transcript to detect and persist speech preferences.

    Call this after saving a user turn to detect patterns like "speak slowly".

    Args:
        db: Database session
        user_id: The student's user ID
        transcript: The user's speech transcript

    Returns:
        TutorRule if a new preference was detected and saved, None otherwise
    """
    if not transcript or not user_id:
        return None

    # Check for slow speech request
    if detect_slow_speech_request(transcript):
        logger.info(f"Detected SLOW SPEECH request from user {user_id}: '{transcript[:50]}...'")
        rule, was_created = get_or_create_slow_speech_rule(db, user_id)
        if was_created:
            logger.info(f"Created new speech pace rule for user {user_id}")
            return rule
        else:
            logger.debug(f"Speech pace rule already exists for user {user_id}")

    return None
