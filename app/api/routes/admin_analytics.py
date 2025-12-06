from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models import UserAccount, UsageSession, LessonPauseEvent, LessonSession
from app.services.auth_service import get_current_user
from pydantic import BaseModel
from decimal import Decimal

router = APIRouter()

class AnalyticsBucket(BaseModel):
    period_start: datetime
    total_minutes: int
    total_revenue: Decimal
    sessions_count: int

class AnalyticsResponse(BaseModel):
    grouping: str
    buckets: List[AnalyticsBucket]
    totals: dict


class PauseEvent(BaseModel):
    pause_id: int
    lesson_session_id: int
    paused_at: datetime
    resumed_at: Optional[datetime]
    summary_text: Optional[str]
    student_id: Optional[int]
    student_email: Optional[str]
    pause_reason: Optional[str]


class PauseResponse(BaseModel):
    days: int
    limit: int
    items: List[PauseEvent]


@router.get("/revenue/minutes", response_model=AnalyticsResponse)
def get_revenue_analytics(
    from_date: datetime,
    to_date: datetime,
    group_by: str = Query("day", regex="^(hour|day)$"),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    # Base query
    query = select(UsageSession).where(
        UsageSession.created_at >= from_date,
        UsageSession.created_at <= to_date
    )
    sessions = db.exec(query).all()

    # Grouping logic
    buckets_map = {}
    
    total_minutes = 0
    total_revenue = Decimal(0)
    total_sessions = 0

    for session in sessions:
        ts = session.created_at
        if group_by == "hour":
            key = ts.replace(minute=0, second=0, microsecond=0)
        else: # day
            key = ts.replace(hour=0, minute=0, second=0, microsecond=0)
            
        if key not in buckets_map:
            buckets_map[key] = {
                "total_minutes": 0,
                "total_revenue": Decimal(0),
                "sessions_count": 0
            }
            
        buckets_map[key]["total_minutes"] += session.billed_minutes
        buckets_map[key]["total_revenue"] += session.billed_amount_rub
        buckets_map[key]["sessions_count"] += 1
        
        total_minutes += session.billed_minutes
        total_revenue += session.billed_amount_rub
        total_sessions += 1

    # Format response
    buckets = []
    for key in sorted(buckets_map.keys()):
        data = buckets_map[key]
        buckets.append(
            AnalyticsBucket(
                period_start=key,
                total_minutes=data["total_minutes"],
                total_revenue=data["total_revenue"],
                sessions_count=data["sessions_count"],
            )
        )

    return AnalyticsResponse(
        grouping=group_by,
        buckets=buckets,
        totals={
            "total_minutes": total_minutes,
            "total_revenue": total_revenue,
            "sessions_count": total_sessions,
        },
    )


@router.get("/lesson-pauses/recent", response_model=PauseResponse)
def get_recent_lesson_pauses(
    days: int = 7,
    limit: int = 50,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Return recent lesson pause events for analytics.

    Used by the AdminAnalytics page to show when students tend to pause lessons
    and whether they return after the break.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    # Basic guards so we don't accidentally ask for absurd ranges
    if days < 1:
        days = 1
    if limit < 1:
        limit = 1

    cutoff = datetime.utcnow() - timedelta(days=days)

    # Join pause events with lesson_sessions + user_accounts to get student email
    stmt = (
        select(LessonPauseEvent, LessonSession, UserAccount)
        .where(LessonPauseEvent.paused_at >= cutoff)
        .join(LessonSession, LessonPauseEvent.lesson_session_id == LessonSession.id)
        .join(UserAccount, LessonSession.user_account_id == UserAccount.id)
        .order_by(LessonPauseEvent.paused_at.desc())
        .limit(limit)
    )

    rows = db.exec(stmt).all()

    items: List[PauseEvent] = []
    for pause, lesson, user in rows:
        items.append(
            PauseEvent(
                pause_id=pause.id,
                lesson_session_id=pause.lesson_session_id,
                paused_at=pause.paused_at,
                resumed_at=pause.resumed_at,
                summary_text=pause.summary_text,
                student_id=user.id,
                student_email=user.email,
                pause_reason=pause.reason,
            )
        )

    return PauseResponse(days=days, limit=limit, items=items)
