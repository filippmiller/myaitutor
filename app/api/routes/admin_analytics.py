from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, text
from app.database import get_session
from app.models import UserAccount, UsageSession
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
        buckets.append(AnalyticsBucket(
            period_start=key,
            total_minutes=data["total_minutes"],
            total_revenue=data["total_revenue"],
            sessions_count=data["sessions_count"]
        ))

    return AnalyticsResponse(
        grouping=group_by,
        buckets=buckets,
        totals={
            "total_minutes": total_minutes,
            "total_revenue": total_revenue,
            "sessions_count": total_sessions
        }
    )
