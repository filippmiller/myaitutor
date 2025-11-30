from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.database import get_session
from app.models import UserAccount, UserState, SessionSummary
from app.services.auth_service import get_current_user
from app.services.profile_service import get_or_create_state_for_user
from app.services.progress_service import load_words
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class SessionSummaryRead(BaseModel):
    id: int
    created_at: datetime
    summary_text: Optional[str]
    practiced_words: List[str]
    weak_words: List[str]
    grammar_notes: List[str]

class ProgressStateRead(BaseModel):
    session_count: int
    total_messages: int
    last_session_at: Optional[datetime]
    xp_points: int
    weak_words: List[str]
    known_words: List[str]

class ProgressResponse(BaseModel):
    state: ProgressStateRead
    recent_sessions: List[SessionSummaryRead]

@router.get("", response_model=ProgressResponse)
def get_progress(
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    # 1. Get State
    state = get_or_create_state_for_user(session, current_user)
    
    # 2. Get Recent Sessions
    statement = select(SessionSummary).where(SessionSummary.user_account_id == current_user.id).order_by(SessionSummary.created_at.desc()).limit(5)
    recent_sessions_db = session.exec(statement).all()
    
    # 3. Format Response
    recent_sessions = []
    for s in recent_sessions_db:
        # Handle potential None id, though it should be set by DB
        s_id = s.id if s.id is not None else 0
        
        recent_sessions.append(SessionSummaryRead(
            id=s_id,
            created_at=s.created_at,
            summary_text=s.summary_text,
            practiced_words=load_words(s.practiced_words_json),
            weak_words=load_words(s.weak_words_json),
            grammar_notes=load_words(s.grammar_notes_json)
        ))
        
    return ProgressResponse(
        state=ProgressStateRead(
            session_count=state.session_count,
            total_messages=state.total_messages,
            last_session_at=state.last_session_at,
            xp_points=state.xp_points,
            weak_words=load_words(state.weak_words_json),
            known_words=load_words(state.known_words_json)
        ),
        recent_sessions=recent_sessions
    )
