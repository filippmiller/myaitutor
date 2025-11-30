from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlmodel import Session, select
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.database import get_session
from app.models import UserAccount, UserProfile, UserAccountRead, AuthSession
from app.security import get_password_hash, verify_password, create_access_token
from app.services.auth_service import create_session_for_user, set_session_cookie, clear_session_cookie, get_current_user

router = APIRouter()

# Schemas
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    user: UserAccountRead
    access_token: str
    token_type: str = "bearer"

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    data: RegisterRequest, 
    response: Response, 
    request: Request, 
    db: Session = Depends(get_session)
):
    # Check if user exists
    existing_user = db.exec(select(UserAccount).where(UserAccount.email == data.email)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        
    # Create UserAccount
    hashed_pwd = get_password_hash(data.password)
    new_user = UserAccount(
        email=data.email,
        hashed_password=hashed_pwd,
        full_name=data.full_name
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create UserProfile
    new_profile = UserProfile(
        name=data.full_name or data.email.split("@")[0],
        english_level="A1", # Default
        user_account_id=new_user.id
    )
    db.add(new_profile)
    db.commit()
    
    # Create Session
    session = create_session_for_user(db, new_user, request)
    
    # Create JWT
    access_token = create_access_token(subject=str(new_user.id))
    
    # Set Cookie
    set_session_cookie(response, session.id, session.expires_at)
    
    return AuthResponse(
        user=UserAccountRead.from_orm(new_user),
        access_token=access_token
    )

@router.post("/login", response_model=AuthResponse)
def login(
    data: LoginRequest, 
    response: Response, 
    request: Request, 
    db: Session = Depends(get_session)
):
    user = db.exec(select(UserAccount).where(UserAccount.email == data.email)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    # Create Session
    session = create_session_for_user(db, user, request)
    
    # Create JWT
    access_token = create_access_token(subject=str(user.id))
    
    # Set Cookie
    set_session_cookie(response, session.id, session.expires_at)
    
    return AuthResponse(
        user=UserAccountRead.from_orm(user),
        access_token=access_token
    )

@router.post("/logout")
def logout(
    response: Response, 
    request: Request, 
    db: Session = Depends(get_session)
):
    session_id = request.cookies.get("session_id")
    if session_id:
        auth_session = db.get(AuthSession, session_id)
        if auth_session:
            auth_session.is_revoked = True
            db.add(auth_session)
            db.commit()
            
    clear_session_cookie(response)
    return {"detail": "Logged out"}

@router.get("/me", response_model=UserAccountRead)
def get_me(current_user: UserAccount = Depends(get_current_user)):
    return current_user
