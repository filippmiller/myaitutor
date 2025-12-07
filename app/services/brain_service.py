"""
Brain Service - Analysis Pipeline for AIlingva

This service processes conversation turns to:
1. Detect weak words and vocabulary patterns
2. Identify grammar mistakes
3. Update student knowledge models
4. Generate brain events for admin monitoring
5. Create dynamic tutor rules

The Analysis pipeline runs asynchronously after streaming turns are saved.
"""

import logging
import json
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlmodel import Session, select

from app.models import (
    TutorLessonTurn,
    TutorBrainEvent,
    TutorStudentKnowledge,
    TutorRule,
    UserAccount
)

logger = logging.getLogger(__name__)


class BrainService:
    """Service for analyzing conversation turns and updating student knowledge."""
    
    def __init__(self, session: Session):
        self.session = session
    
    # ============================================================
    # Public API
    # ============================================================
    
    def analyze_turn(
        self,
        turn: TutorLessonTurn,
        user: UserAccount
    ) -> List[TutorBrainEvent]:
        """Analyze a single conversation turn and generate brain events.
        
        Args:
            turn: The conversation turn to analyze
            user: The user account
            
        Returns:
            List of brain events generated from this analysis
        """
        events = []
        
        # Get or create student knowledge snapshot
        knowledge = self._get_or_create_knowledge(user.id)
        
        # Skip analysis if no user text
        if not turn.user_text:
            return events
        
        # 1. Analyze weak words
        weak_words_event = self._analyze_weak_words(turn, knowledge)
        if weak_words_event:
            events.append(weak_words_event)
        
        # 2. Analyze grammar patterns
        grammar_event = self._analyze_grammar(turn, knowledge)
        if grammar_event:
            events.append(grammar_event)
        
        # 3. Check for vocabulary strength changes
        vocab_change_event = self._check_vocabulary_changes(turn, knowledge)
        if vocab_change_event:
            events.append(vocab_change_event)
        
        # Save all events
        for event in events:
            self.session.add(event)
        
        # Update knowledge snapshot (incremental update, not full replace)
        knowledge.updated_at = datetime.utcnow()
        self.session.add(knowledge)
        self.session.commit()
        
        return events
    
    def analyze_lesson_end(
        self,
        lesson_id: int,
        user_id: int,
        turns_summary: Optional[str] = None
    ) -> TutorBrainEvent:
        """Generate end-of-lesson summary event.
        
        Args:
            lesson_id: The lesson ID
            user_id: The user ID
            turns_summary: Optional human-readable summary
            
        Returns:
            Brain event for lesson summary
        """
        knowledge = self._get_or_create_knowledge(user_id)
        
        # Increment lesson count
        knowledge.lesson_count += 1
        
        event = TutorBrainEvent(
            lesson_id=lesson_id,
            user_id=user_id,
            turn_id=None,  # Not tied to specific turn
            pipeline_type="ANALYSIS",
            event_type="LESSON_SUMMARY_GENERATED",
            event_payload_json={
                "summary": turns_summary or "Lesson completed",
                "lesson_count": knowledge.lesson_count,
                "new_weak_words_count": len(knowledge.vocabulary_json.get("weak", [])),
            },
            snapshot_student_knowledge_json=knowledge.vocabulary_json
        )
        
        self.session.add(event)
        self.session.add(knowledge)
        self.session.commit()
        
        return event
    
    def complete_placement_test(
        self,
        lesson_id: int,
        user_id: int,
        placement_level: str
    ) -> TutorBrainEvent:
        """Mark first lesson placement test as complete.
        
        Args:
            lesson_id: The lesson ID
            user_id: The user ID
            placement_level: Determined CEFR level (A1, A2, B1, B2, C1, C2)
            
        Returns:
            Brain event for placement test completion
        """
        knowledge = self._get_or_create_knowledge(user_id)
        
        knowledge.level = placement_level
        knowledge.first_lesson_completed = True
        knowledge.lesson_count = 1
        
        event = TutorBrainEvent(
            lesson_id=lesson_id,
            user_id=user_id,
            turn_id=None,
            pipeline_type="ANALYSIS",
            event_type="PLACEMENT_TEST_COMPLETED",
            event_payload_json={
                "placement_level": placement_level,
                "timestamp": datetime.utcnow().isoformat()
            },
            snapshot_student_knowledge_json={
                "level": placement_level,
                "first_lesson_completed": True,
                "lesson_count": 1
            }
        )
        
        self.session.add(event)
        self.session.add(knowledge)
        self.session.commit()
        
        logger.info(f"Placement test completed for user {user_id}: {placement_level}")
        
        return event
    
    # ============================================================
    # Private Analysis Methods
    # ============================================================
    
    def _get_or_create_knowledge(self, user_id: int) -> TutorStudentKnowledge:
        """Get existing knowledge or create new snapshot for user."""
        knowledge = self.session.get(TutorStudentKnowledge, user_id)
        
        if not knowledge:
            knowledge = TutorStudentKnowledge(
                user_id=user_id,
                level="A1",
                lesson_count=0,
                first_lesson_completed=False,
                vocabulary_json={"weak": [], "strong": [], "neutral": []},
                grammar_json={"patterns": {}, "mistakes": {}},
                topics_json={"covered": [], "to_practice": []},
                meta_json={}
            )
            self.session.add(knowledge)
            self.session.commit()
            self.session.refresh(knowledge)
        
        return knowledge
    
    def _analyze_weak_words(
        self,
        turn: TutorLessonTurn,
        knowledge: TutorStudentKnowledge
    ) -> Optional[TutorBrainEvent]:
        """Detect weak words from user's text.
        
        Simple heuristic: if tutor's response contains corrections or
        repetitions of user's words, those might be weak points.
        
        TODO: In v2, use LLM to detect mistakes more accurately.
        """
        if not turn.user_text or not turn.tutor_text:
            return None
        
        # Simple pattern: detect if tutor is correcting
        correction_markers = [
            "actually, it's",
            "you mean",
            "the correct form is",
            "should be",
            "you meant to say"
        ]
        
        tutor_lower = turn.tutor_text.lower()
        
        # Check if correction is happening
        has_correction = any(marker in tutor_lower for marker in correction_markers)
        
        if not has_correction:
            return None
        
        # Extract words from user text (simple tokenization)
        user_words = re.findall(r'\b\w+\b', turn.user_text.lower())
        
        # For now, mark first few content words as potentially weak
        # In production, this needs LLM-based analysis
        potential_weak = [w for w in user_words if len(w) > 3][:3]
        
        if not potential_weak:
            return None
        
        # Update knowledge
        current_weak = knowledge.vocabulary_json.get("weak", [])
        new_weak = []
        
        for word in potential_weak:
            # Check if already tracked
            existing = next((w for w in current_weak if isinstance(w, dict) and w.get("word") == word), None)
            if existing:
                existing["frequency"] = existing.get("frequency", 1) + 1
                existing["last_mistake"] = datetime.utcnow().isoformat()
            else:
                new_weak.append(word)
                current_weak.append({
                    "word": word,
                    "frequency": 1,
                    "last_mistake": datetime.utcnow().isoformat()
                })
        
        if not new_weak:
            return None
        
        knowledge.vocabulary_json["weak"] = current_weak
        
        event = TutorBrainEvent(
            lesson_id=turn.lesson_id,
            user_id=turn.user_id,
            turn_id=turn.id,
            pipeline_type="ANALYSIS",
            event_type="WEAK_WORD_ADDED",
            event_payload_json={
                "weak_words_added": new_weak,
                "context": turn.user_text[:100],
                "correction_detected": True
            }
        )
        
        logger.info(f"Weak words detected for user {turn.user_id}: {new_weak}")
        
        return event
    
    def _analyze_grammar(
        self,
        turn: TutorLessonTurn,
        knowledge: TutorStudentKnowledge
    ) -> Optional[TutorBrainEvent]:
        """Detect grammar patterns and mistakes.
        
        Simple heuristic for MVP:
        - Detect common patterns (past tense, present simple, etc.)
        - Count mistakes based on tutor corrections
        
        TODO: In v2, use LLM for detailed grammar analysis.
        """
        if not turn.user_text or not turn.tutor_text:
            return None
        
        tutor_lower = turn.tutor_text.lower()
        user_lower = turn.user_text.lower()
        
        # Detect grammar correction patterns
        grammar_markers = {
            "past_simple": ["went", "did", "was", "were", "had"],
            "present_simple": ["goes", "does", "is", "are", "has"],
            "3rd_person_singular": ["he goes", "she goes", "it goes", "he has", "she has"],
        }
        
        detected_patterns = []
        
        for pattern_name, markers in grammar_markers.items():
            if any(marker in user_lower for marker in markers):
                detected_patterns.append(pattern_name)
        
        if not detected_patterns:
            return None
        
        # Update grammar tracking
        grammar_data = knowledge.grammar_json
        patterns = grammar_data.get("patterns", {})
        
        for pattern in detected_patterns:
            if pattern not in patterns:
                patterns[pattern] = {"attempts": 0, "mistakes": 0, "mastery": 0.0}
            
            patterns[pattern]["attempts"] += 1
            
            # Check if correction happened (indicating mistake)
            if any(marker in tutor_lower for marker in ["actually", "should be", "correct form"]):
                patterns[pattern]["mistakes"] += 1
            
            # Calculate mastery
            attempts = patterns[pattern]["attempts"]
            mistakes = patterns[pattern]["mistakes"]
            patterns[pattern]["mastery"] = 1.0 - (mistakes / max(attempts, 1))
        
        grammar_data["patterns"] = patterns
        knowledge.grammar_json = grammar_data
        
        event = TutorBrainEvent(
            lesson_id=turn.lesson_id,
            user_id=turn.user_id,
            turn_id=turn.id,
            pipeline_type="ANALYSIS",
            event_type="GRAMMAR_PATTERN_UPDATE",
            event_payload_json={
                "patterns_detected": detected_patterns,
                "patterns_stats": {p: patterns[p] for p in detected_patterns}
            }
        )
        
        logger.info(f"Grammar patterns detected for user {turn.user_id}: {detected_patterns}")
        
        return event
    
    def _check_vocabulary_changes(
        self,
        turn: TutorLessonTurn,
        knowledge: TutorStudentKnowledge
    ) -> Optional[TutorBrainEvent]:
        """Check if any weak words should be promoted to strong/neutral.
        
        Heuristic: If a word appears multiple times without correction,
        it might have been mastered.
        
        TODO: Implement in v2 with more sophisticated logic.
        """
        # Placeholder for future implementation
        return None
    
    # ============================================================
    # Utility Methods
    # ============================================================
    
    def get_student_knowledge(self, user_id: int) -> Optional[TutorStudentKnowledge]:
        """Get current student knowledge snapshot."""
        return self.session.get(TutorStudentKnowledge, user_id)
    
    def get_brain_events_for_lesson(
        self,
        lesson_id: int,
        limit: int = 100
    ) -> List[TutorBrainEvent]:
        """Get all brain events for a specific lesson."""
        statement = (
            select(TutorBrainEvent)
            .where(TutorBrainEvent.lesson_id == lesson_id)
            .order_by(TutorBrainEvent.created_at)
            .limit(limit)
        )
        return list(self.session.exec(statement))
    
    def get_recent_brain_events(
        self,
        user_id: Optional[int] = None,
        limit: int = 50
    ) -> List[TutorBrainEvent]:
        """Get recent brain events, optionally filtered by user."""
        statement = select(TutorBrainEvent).order_by(TutorBrainEvent.created_at.desc()).limit(limit)
        
        if user_id:
            statement = statement.where(TutorBrainEvent.user_id == user_id)
        
        return list(self.session.exec(statement))
