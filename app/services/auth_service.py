import uuid
from datetime import datetime, timedelta
from fastapi import Request, Response, Depends, HTTPException, status
from sqlmodel import Session, select
from app.models import UserAccount, AuthSession
from app.database import get_session
from app.security import SESSION_EXPIRE_HOURS, COOKIE_SECURE

def create_session_for_user(db: Session, user: UserAccount, request: Request) -> AuthSession:
    session_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_EXPIRE_HOURS)
    
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    
    auth_session = AuthSession(
        id=session_id,
        user_id=user.id,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address
    )
    
    db.add(auth_session)
    db.commit()
    db.refresh(auth_session)
    return auth_session

def set_session_cookie(response: Response, session_id: str, expires_at: datetime) -> None:
    # Calculate max_age in seconds
    now = datetime.utcnow()
    max_age = int((expires_at - now).total_seconds())
    
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=max_age
    )

def clear_session_cookie(response: Response) -> None:
    response.set_cookie(
        key="session_id",
        value="",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=0
    )

async def get_current_user(request: Request, db: Session = Depends(get_session)) -> UserAccount:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    auth_session = db.get(AuthSession, session_id)
    if not auth_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found")
        
    if auth_session.is_revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked")
        
    if auth_session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
        
    user = db.get(UserAccount, auth_session.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
        
    return user

def verify_session_id(session_id: str, db: Session) -> int | None:
    if not session_id:
        return None
    
    auth_session = db.get(AuthSession, session_id)
    if not auth_session:
        return None
        
    if auth_session.is_revoked:
        return None
        
    if auth_session.expires_at < datetime.utcnow():
        return None
        
    return auth_session.user_id
