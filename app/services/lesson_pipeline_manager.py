"""
Integration helper for voice session with multi-pipeline architecture.

This module bridges the existing voice_ws.py with the new tutor lesson tracking
and brain analysis pipeline.
"""

import logging
from typing import Optional
from sqlmodel import Session
from datetime import datetime

from app.models import (
    UserAccount,
    LessonSession,
    TutorLesson,
    TutorLessonTurn,
)
from app.services.tutor_service import (
    get_next_lesson_number,
    is_first_lesson,
    create_tutor_lesson,
    get_or_create_student_knowledge
)
from app.services.brain_service import BrainService

logger = logging.getLogger(__name__)


class LessonPipelineManager:
    """Manages lesson lifecycle and coordinates STREAMING + ANALYSIS pipelines."""
    
    def __init__(self, session: Session, user: UserAccount):
        self.session = session
        self.user = user
        self.tutor_lesson: Optional[TutorLesson] = None
        self.turn_counter = 0
        self.brain_service = BrainService(session)
    
    def start_lesson(self, legacy_session_id: int) -> TutorLesson:
        """
        Start a new tutor lesson.
        
        This determines if this is the first lesson (needs intro + placement)
        or a regular lesson (uses existing knowledge).
        
        Args:
            legacy_session_id: The old LessonSession.id for backwards compatibility
            
        Returns:
            TutorLesson instance
        """
        lesson_number = get_next_lesson_number(self.session, self.user.id)
        is_first = is_first_lesson(self.session, self.user.id)
        
        self.tutor_lesson = create_tutor_lesson(
            self.session,
            user_id=self.user.id,
            lesson_number=lesson_number,
            is_first=is_first,
            legacy_session_id=legacy_session_id
        )
        
        logger.info(
            f"Started tutor lesson {self.tutor_lesson.id} "
            f"(lesson_number={lesson_number}, is_first={is_first}) "
            f"for user {self.user.id}"
        )
        
        # Ensure knowledge record exists
        get_or_create_ = get_or_create_student_knowledge(self.session, self.user.id)
        
        return self.tutor_lesson
    
    def save_turn(
        self,
        user_text: Optional[str],
        tutor_text: Optional[str],
        raw_payload: Optional[dict] = None
    ) -> Optional[TutorLessonTurn]:
        """
        Save a conversation turn and trigger brain analysis.
        
        Args:
            user_text: What the user said (can be None for tutor-only turns, e.g., greeting)
            tutor_text: What the tutor said (can be None for user-only turns)
            raw_payload: Optional debug payload
            
        Returns:
            TutorLessonTurn instance or None if lesson not started
        """
        if not self.tutor_lesson:
            logger.warning("Attempted to save turn but lesson not started")
            return None
        
        # Only save if there's actual content
        if not user_text and not tutor_text:
            return None
        
        turn = TutorLessonTurn(
            lesson_id=self.tutor_lesson.id,
            user_id=self.user.id,
            turn_index=self.turn_counter,
            pipeline_type="STREAMING",
            user_text=user_text,
            tutor_text=tutor_text,
            raw_payload_json=raw_payload or {}
        )
        
        self.session.add(turn)
        self.session.commit()
        self.session.refresh(turn)
        
        self.turn_counter += 1
        
        logger.info(
            f"Saved turn {turn.turn_index} for lesson {self.tutor_lesson.id}: "
            f"user={bool(user_text)}, tutor={bool(tutor_text)}"
        )
        
        # Trigger brain analysis (synchronous for MVP)
        try:
            events = self.brain_service.analyze_turn(turn, self.user)
            if events:
                logger.info(
                    f"Brain analysis generated {len(events)} events for turn {turn.turn_index}"
                )
        except Exception as e:
            logger.error(f"Brain analysis failed for turn {turn.turn_index}: {e}", exc_info=True)
        
        return turn
    
    def end_lesson(self, summary: Optional[str] = None):
        """Mark lesson as complete and generate end-of-lesson brain event."""
        if not self.tutor_lesson:
            logger.warning("Attempted to end lesson but lesson not started")
            return
        
        self.tutor_lesson.ended_at = datetime.utcnow()
        
        if summary:
            self.tutor_lesson.summary_json = {"text": summary}
        
        self.session.add(self.tutor_lesson)
        self.session.commit()
        
        # Generate lesson summary brain event
        try:
            self.brain_service.analyze_lesson_end(
                lesson_id=self.tutor_lesson.id,
                user_id=self.user.id,
                turns_summary=summary
            )
            logger.info(f"Lesson {self.tutor_lesson.id} ended successfully")
        except Exception as e:
            logger.error(f"Failed to generate lesson end event: {e}", exc_info=True)
    
    def complete_placement_test(self, placement_level: str):
        """Mark first lesson placement test as complete."""
        if not self.tutor_lesson:
            logger.warning("Attempted to complete placement test but lesson not started")
            return
        
        if not self.tutor_lesson.is_first_lesson:
            logger.warning("Attempted to complete placement test on non-first lesson")
            return
        
        self.tutor_lesson.placement_test_run = True
        self.tutor_lesson.placement_level = placement_level
        self.session.add(self.tutor_lesson)
        self.session.commit()
        
        # Generate brain event
        try:
            self.brain_service.complete_placement_test(
                lesson_id=self.tutor_lesson.id,
                user_id=self.user.id,
                placement_level=placement_level
            )
            logger.info(
                f"Placement test completed for user {self.user.id}: {placement_level}"
            )
        except Exception as e:
            logger.error(f"Failed to generate placement test event: {e}", exc_info=True)
