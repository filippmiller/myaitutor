from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlmodel import Session, select
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.database import get_session
from app.models import UserAccount, UserProfile, UserAccountRead, AuthSession
from app.security import get_password_hash, verify_password, create_access_token
from app.services.auth_service import create_session_for_user, set_session_cookie, clear_session_cookie, get_current_user

router = APIRouter()

from app.services.billing_service import BillingService
from app.services.referral_service import ReferralService

# Schemas
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    referral_code: Optional[str] = None

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
    try:
        # Check if user exists
        existing_user = db.exec(select(UserAccount).where(UserAccount.email == data.email)).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        if len(data.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
            
        # Create UserAccount
        print(f"DEBUG: Hashing password of length {len(data.password)}")
        hashed_pwd = get_password_hash(data.password)
        
        from app.security import ADMIN_EMAIL
        role = "admin" if data.email == ADMIN_EMAIL else "student"
        
        new_user = UserAccount(
            email=data.email,
            hashed_password=hashed_pwd,
            full_name=data.full_name,
            role=role
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        if not new_user.id:
            raise HTTPException(status_code=500, detail="Failed to create user account ID")

        # Create UserProfile
        new_profile = UserProfile(
            name=data.full_name or data.email.split("@")[0],
            english_level="A1", # Default
            user_account_id=new_user.id
        )
        db.add(new_profile)
        db.commit()
        
        # --- Billing & Referral Logic ---
        billing_service = BillingService(db)
        referral_service = ReferralService(db)
        
        # 1. Give 60 free minutes
        billing_service.create_trial_bonus(new_user.id)
        
        # 2. Process referral if code provided
        if data.referral_code:
            referral_service.process_referral_signup(new_user.id, data.referral_code)
            
        # 3. Generate own referral code (optional, but good to have ready)
        # referral_service.generate_referral_code(new_user.id) 
        
        # Create Session for immediate login
        session = create_session_for_user(db, new_user, request)
        access_token = create_access_token(subject=str(new_user.id))
        set_session_cookie(response, session.id, session.expires_at)
        
        return AuthResponse(
            user=UserAccountRead.from_orm(new_user),
            access_token=access_token
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Registration Error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

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
