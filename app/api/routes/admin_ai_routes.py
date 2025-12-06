from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

from app.database import get_session
from app.models import (
    UserAccount, TutorRule, TutorRuleVersion, 
    LessonSession, UserState, LessonPauseEvent
)
from app.services.auth_service import get_current_user
from app.services.admin_ai_service import process_admin_message

router = APIRouter()

# --- Chat Endpoint ---

class ChatRequest(BaseModel):
    conversation_id: Optional[int] = None
    message: str

@router.post("/chat")
def chat_with_ai(
    data: ChatRequest,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Chat with the AI Admin Assistant."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    result = process_admin_message(
        admin_user_id=current_user.id,
        message_text=data.message,
        session=session,
        conversation_id=data.conversation_id
    )
    
    return result

# --- Rules Management Endpoints ---

@router.get("/rules")
def list_rules(
    scope: Optional[str] = None,
    student_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """List all tutor rules with optional filters."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    statement = select(TutorRule)
    
    if scope:
        statement = statement.where(TutorRule.scope == scope)
    if student_id is not None:
        statement = statement.where(TutorRule.applies_to_student_id == student_id)
    if is_active is not None:
        statement = statement.where(TutorRule.is_active == is_active)
    
    rules = session.exec(statement.order_by(TutorRule.priority)).all()
    return rules

class RuleCreate(BaseModel):
    scope: str
    type: str
    title: str
    description: str
    trigger_condition: Optional[str] = None
    action: Optional[str] = None
    priority: int = 0

@router.post("/rules")
def create_rule(
    data: RuleCreate,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Create a new rule (manually by admin)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    rule = TutorRule(
        scope=data.scope,
        type=data.type,
        title=data.title,
        description=data.description,
        trigger_condition=data.trigger_condition,
        action=data.action,
        priority=data.priority,
        is_active=True,
        created_by="human_admin",
        updated_by="human_admin",
        source="manual"
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    
    # Create audit version
    version = TutorRuleVersion(
        rule_id=rule.id,
        scope=rule.scope,
        type=rule.type,
        title=rule.title,
        description=rule.description,
        trigger_condition=rule.trigger_condition,
        action=rule.action,
        priority=rule.priority,
        is_active=rule.is_active,
        changed_by="human_admin",
        change_reason="Created manually by admin"
    )
    session.add(version)
    session.commit()
    
    return rule

class RuleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    trigger_condition: Optional[str] = None
    action: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None

@router.patch("/rules/{rule_id}")
def update_rule(
    rule_id: int,
    data: RuleUpdate,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update a rule (manually by admin)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    rule = session.get(TutorRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    changes = []
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        old_value = getattr(rule, key)
        if old_value != value:
            setattr(rule, key, value)
            changes.append(f"{key}: {old_value} -> {value}")
    
    if changes:
        rule.updated_by = "human_admin"
        rule.updated_at = datetime.utcnow()
        session.add(rule)
        session.commit()
        session.refresh(rule)
        
        # Create audit version
        version = TutorRuleVersion(
            rule_id=rule.id,
            scope=rule.scope,
            type=rule.type,
            title=rule.title,
            description=rule.description,
            trigger_condition=rule.trigger_condition,
            action=rule.action,
            priority=rule.priority,
            is_active=rule.is_active,
            changed_by="human_admin",
            change_reason=f"Updated manually: {', '.join(changes)}"
        )
        session.add(version)
        session.commit()
    
    return rule

@router.get("/rules/{rule_id}/history")
def get_rule_history(
    rule_id: int,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get version history for a rule."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    versions = session.exec(
        select(TutorRuleVersion)
        .where(TutorRuleVersion.rule_id == rule_id)
        .order_by(TutorRuleVersion.created_at.desc())
    ).all()
    
    return versions

# --- Analytics Endpoints ---

@router.get("/analytics/summary/today")
def get_today_summary(
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get summary of today's activity."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Count sessions today
    sessions = session.exec(
        select(LessonSession)
        .where(LessonSession.started_at >= today_start)
    ).all()
    
    session_count = len(sessions)
    
    # Count active students (those with sessions)
    active_students = len(set(s.user_account_id for s in sessions))
    
    # Calculate avg XP gain
    xp_gains = []
    for s in sessions:
        user_state = session.exec(
            select(UserState)
            .where(UserState.user_account_id == s.user_account_id)
        ).first()
        if user_state:
            xp_gains.append(user_state.xp_points)
    
    avg_xp = sum(xp_gains) / len(xp_gains) if xp_gains else 0
    
    return {
        "date": today_start.isoformat(),
        "session_count": session_count,
        "active_students": active_students,
        "avg_xp_per_student": round(avg_xp, 2)
    }

@router.get("/analytics/students/top-xp")
def get_top_students_by_xp(
    days: int = 7,
    limit: int = 10,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get top students by XP growth in the last N days."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Get all user states ordered by XP
    states = session.exec(
        select(UserState)
        .order_by(UserState.xp_points.desc())
        .limit(limit)
    ).all()
    
    results = []
    for state in states:
        user = session.get(UserAccount, state.user_account_id)
        if user:
            results.append({
                "user_id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "xp_points": state.xp_points,
                "session_count": state.session_count
            })
    
    return results

@router.get("/analytics/sessions/count")
def get_session_count(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get session count in a date range."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    statement = select(LessonSession)
    
    if from_date:
        from_dt = datetime.fromisoformat(from_date)
        statement = statement.where(LessonSession.started_at >= from_dt)
    
    if to_date:
        to_dt = datetime.fromisoformat(to_date)
        statement = statement.where(LessonSession.started_at <= to_dt)
    
    sessions = session.exec(statement).all()
    
    return {
        "count": len(sessions),
        "from_date": from_date or "beginning",
        "to_date": to_date or "now"
    }

@router.get("/analytics/lesson-pauses/recent")
def get_recent_lesson_pauses(
    days: int = 7,
    limit: int = 50,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Return recent lesson pauses for admin analytics.

    Each entry describes a single pause/resume pair (if resumed), including the
    student and a short summary of what was done before the break.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    from_date = datetime.utcnow() - timedelta(days=days)

    statement = (
        select(LessonPauseEvent, LessonSession, UserAccount)
        .join(LessonSession, LessonPauseEvent.lesson_session_id == LessonSession.id)
        .join(UserAccount, LessonSession.user_account_id == UserAccount.id)
        .where(LessonPauseEvent.paused_at >= from_date)
        .order_by(LessonPauseEvent.paused_at.desc())
        .limit(limit)
    )

    rows = session.exec(statement).all()
    results = []
    for pause, lesson, user in rows:
        results.append({
            "pause_id": pause.id,
            "lesson_session_id": lesson.id,
            "paused_at": pause.paused_at.isoformat(),
            "resumed_at": pause.resumed_at.isoformat() if pause.resumed_at else None,
            "summary_text": pause.summary_text,
            "student_id": user.id,
            "student_email": user.email,
            "pause_reason": pause.reason,
        })

    return {
        "days": days,
        "limit": limit,
        "items": results,
    }


@router.get("/analytics/language-modes/distribution")
def get_language_mode_distribution(
    days: int = 7,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get distribution of language modes chosen by students over the last N days."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    from_date = datetime.utcnow() - timedelta(days=days)
    
    statement = select(LessonSession).where(
        LessonSession.started_at >= from_date
    )
    
    sessions = session.exec(statement).all()
    total = len(sessions)
    
    # Count by mode
    by_mode = {
        "EN_ONLY": 0,
        "RU_ONLY": 0,
        "MIXED": 0,
        "NOT_SET": 0
    }
    
    for sess in sessions:
        if sess.language_mode:
            by_mode[sess.language_mode] = by_mode.get(sess.language_mode, 0) + 1
        else:
            by_mode["NOT_SET"] += 1
    
    # Calculate percentages
    percentage = {}
    for mode, count in by_mode.items():
        percentage[mode] = round((count / total * 100), 2) if total > 0 else 0.0
    
    return {
        "total_sessions": total,
        "days": days,
        "by_mode": by_mode,
        "percentage": percentage
    }
