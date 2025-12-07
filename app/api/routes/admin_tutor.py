"""
Admin Tutor API Routes - Multi-Pipeline Monitoring

Provides endpoints for:
- Viewing lesson timelines (conversation turns)
- Monitoring brain events (Analysis pipeline output)
- Live "Rules Terminal" (streaming brain events)
- Student knowledge snapshots
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from pydantic import BaseModel

from app.database import get_session
from app.models import (
    UserAccount,
    TutorLesson,
    TutorLessonTurn,
    TutorBrainEvent,
    TutorStudentKnowledge
)
from app.services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Response Models
# ============================================================

class LessonSummary(BaseModel):
    id: int
    user_id: int
    lesson_number: int
    is_first_lesson: bool
    placement_level: Optional[str]
    started_at: str
    ended_at: Optional[str]
    turn_count: int
    
    class Config:
        from_attributes = True


class TurnDetail(BaseModel):
    id: int
    turn_index: int
    pipeline_type: str
    user_text: Optional[str]
    tutor_text: Optional[str]
    created_at: str
    brain_events_count: int = 0
    
    class Config:
        from_attributes = True


class BrainEventDetail(BaseModel):
    id: int
    lesson_id: int
    user_id: int
    turn_id: Optional[int]
    pipeline_type: str
    event_type: str
    event_payload_json: dict
    created_at: str
    
    class Config:
        from_attributes = True


class StudentKnowledgeSnapshot(BaseModel):
    user_id: int
    level: str
    lesson_count: int
    first_lesson_completed: bool
    vocabulary_json: dict
    grammar_json: dict
    topics_json: dict
    updated_at: str
    
    class Config:
        from_attributes = True


# ============================================================
# Endpoints
# ============================================================

@router.get("/lessons", response_model=List[LessonSummary])
def get_user_lessons(
    user_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get list of lessons, optionally filtered by user."""
    
    # Only admins can view all users
    if current_user.role != "admin" and user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    statement = select(TutorLesson).order_by(TutorLesson.started_at.desc()).limit(limit)
    
    if user_id:
        statement = statement.where(TutorLesson.user_id == user_id)
    
    lessons = session.exec(statement).all()
    
    # Enrich with turn count
    result = []
    for lesson in lessons:
        turn_count_stmt = select(TutorLessonTurn).where(TutorLessonTurn.lesson_id == lesson.id)
        turn_count = len(list(session.exec(turn_count_stmt)))
        
        result.append(LessonSummary(
            id=lesson.id,
            user_id=lesson.user_id,
            lesson_number=lesson.lesson_number,
            is_first_lesson=lesson.is_first_lesson,
            placement_level=lesson.placement_level,
            started_at=lesson.started_at.isoformat(),
            ended_at=lesson.ended_at.isoformat() if lesson.ended_at else None,
            turn_count=turn_count
        ))
    
    return result


@router.get("/lessons/{lesson_id}/turns", response_model=List[TurnDetail])
def get_lesson_turns(
    lesson_id: int,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get all conversation turns for a specific lesson."""
    
    # Verify lesson exists and user has access
    lesson = session.get(TutorLesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    if current_user.role != "admin" and lesson.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Get turns
    statement = (
        select(TutorLessonTurn)
        .where(TutorLessonTurn.lesson_id == lesson_id)
        .order_by(TutorLessonTurn.turn_index)
    )
    turns = session.exec(statement).all()
    
    # Enrich with brain events count
    result = []
    for turn in turns:
        events_stmt = select(TutorBrainEvent).where(TutorBrainEvent.turn_id == turn.id)
        events_count = len(list(session.exec(events_stmt)))
        
        result.append(TurnDetail(
            id=turn.id,
            turn_index=turn.turn_index,
            pipeline_type=turn.pipeline_type,
            user_text=turn.user_text,
            tutor_text=turn.tutor_text,
            created_at=turn.created_at.isoformat(),
            brain_events_count=events_count
        ))
    
    return result


@router.get("/lessons/{lesson_id}/brain-events", response_model=List[BrainEventDetail])
def get_lesson_brain_events(
    lesson_id: int,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get all brain events for a specific lesson."""
    
    # Verify lesson exists and user has access
    lesson = session.get(TutorLesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    if current_user.role != "admin" and lesson.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Get brain events
    statement = (
        select(TutorBrainEvent)
        .where(TutorBrainEvent.lesson_id == lesson_id)
        .order_by(TutorBrainEvent.created_at)
    )
    events = session.exec(statement).all()
    
    return [
        BrainEventDetail(
            id=event.id,
            lesson_id=event.lesson_id,
            user_id=event.user_id,
            turn_id=event.turn_id,
            pipeline_type=event.pipeline_type,
            event_type=event.event_type,
            event_payload_json=event.event_payload_json,
            created_at=event.created_at.isoformat()
        )
        for event in events
    ]


@router.get("/brain-events/recent", response_model=List[BrainEventDetail])
def get_recent_brain_events(
    user_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get recent brain events across all lessons, optionally filtered by user."""
    
    # Only admins can view all users
    if current_user.role != "admin" and user_id and user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    statement = select(TutorBrainEvent).order_by(TutorBrainEvent.created_at.desc()).limit(limit)
    
    if user_id:
        statement = statement.where(TutorBrainEvent.user_id == user_id)
    
    events = session.exec(statement).all()
    
    return [
        BrainEventDetail(
            id=event.id,
            lesson_id=event.lesson_id,
            user_id=event.user_id,
            turn_id=event.turn_id,
            pipeline_type=event.pipeline_type,
            event_type=event.event_type,
            event_payload_json=event.event_payload_json,
            created_at=event.created_at.isoformat()
        )
        for event in events
    ]


@router.get("/users/{user_id}/knowledge", response_model=StudentKnowledgeSnapshot)
def get_student_knowledge(
    user_id: int,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get current knowledge snapshot for a student."""
    
    # Only admins can view other users
    if current_user.role != "admin" and user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    knowledge = session.get(TutorStudentKnowledge, user_id)
    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge snapshot not found")
    
    return StudentKnowledgeSnapshot(
        user_id=knowledge.user_id,
        level=knowledge.level,
        lesson_count=knowledge.lesson_count,
        first_lesson_completed=knowledge.first_lesson_completed,
        vocabulary_json=knowledge.vocabulary_json,
        grammar_json=knowledge.grammar_json,
        topics_json=knowledge.topics_json,
        updated_at=knowledge.updated_at.isoformat()
    )


@router.get("/brain-events/terminal-feed")
async def get_brain_events_terminal_feed(
    user_id: Optional[int] = Query(None),
    since_timestamp: Optional[str] = Query(None),
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get brain events for terminal-like UI display.
    
    Returns events in a format suitable for a live terminal view:
    - Timestamp
    - Event type
    - Human-readable summary
    
    Query params:
    - user_id: Filter by user
    - since_timestamp: Only get events after this ISO timestamp
    """
    
    # Only admins can view all users
    if current_user.role != "admin" and user_id and user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    statement = select(TutorBrainEvent).order_by(TutorBrainEvent.created_at.desc()).limit(100)
    
    if user_id:
        statement = statement.where(TutorBrainEvent.user_id == user_id)
    
    if since_timestamp:
        from datetime import datetime
        try:
            since_dt = datetime.fromisoformat(since_timestamp.replace('Z', '+00:00'))
            statement = statement.where(TutorBrainEvent.created_at > since_dt)
        except Exception as e:
            logger.warning(f"Invalid timestamp format: {since_timestamp}, error: {e}")
    
    events = session.exec(statement).all()
    
    # Format for terminal display
    terminal_lines = []
    for event in reversed(list(events)):  # Oldest first for terminal
        timestamp = event.created_at.strftime("%H:%M:%S")
        event_type = event.event_type
        
        # Generate human-readable summary from payload
        payload = event.event_payload_json
        summary = ""
        
        if event_type == "WEAK_WORD_ADDED":
            words = payload.get("weak_words_added", [])
            summary = f"weak words: {', '.join(words)}"
        elif event_type == "GRAMMAR_PATTERN_UPDATE":
            patterns = payload.get("patterns_detected", [])
            summary = f"patterns: {', '.join(patterns)}"
        elif event_type == "RULE_CREATED":
            title = payload.get("rule_title", "new rule")
            summary = f"created: {title}"
        elif event_type == "PLACEMENT_TEST_COMPLETED":
            level = payload.get("placement_level", "?")
            summary = f"placed at {level}"
        elif event_type == "LESSON_SUMMARY_GENERATED":
            summary = f"lesson {payload.get('lesson_count', '?')} completed"
        else:
            summary = str(payload)[:50]
        
        terminal_lines.append({
            "timestamp": timestamp,
            "event_type": event_type,
            "summary": summary,
            "full_payload": payload,
            "user_id": event.user_id,
            "lesson_id": event.lesson_id
        })
    
    return {
        "events": terminal_lines,
        "count": len(terminal_lines)
    }
