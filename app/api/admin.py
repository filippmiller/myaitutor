from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models import AppSettings, UserAccount, UserProfile, TutorSystemRule
from app.services.auth_service import get_current_user
from pydantic import BaseModel
import openai
import requests

router = APIRouter()

class SettingsUpdate(BaseModel):
    openai_api_key: str
    default_model: str

@router.get("/settings")
def get_settings(session: Session = Depends(get_session)):
    settings = session.get(AppSettings, 1)
    if not settings:
        return {
            "openai_api_key": None, 
            "default_model": "gpt-4o-mini"
        }
    return settings

@router.post("/settings")
def update_settings(data: SettingsUpdate, session: Session = Depends(get_session)):
    settings = session.get(AppSettings, 1)
    if not settings:
        settings = AppSettings(id=1)
    
    settings.openai_api_key = data.openai_api_key
    settings.default_model = data.default_model
    
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings

@router.post("/test-openai")
def test_openai(session: Session = Depends(get_session)):
    settings = session.get(AppSettings, 1)
    if not settings or not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OpenAI API Key not set")
    
    try:
        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.default_model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5
        )
        return {"status": "ok", "message": "OpenAI connection successful", "response": response.choices[0].message.content}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/users")
def list_users(
    offset: int = 0, 
    limit: int = 50, 
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    users = session.exec(select(UserAccount).offset(offset).limit(limit)).all()
    return users

@router.get("/users/{user_id}")
def get_user_details(
    user_id: int,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    user = session.get(UserAccount, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Get profile
    profile = session.exec(select(UserProfile).where(UserProfile.user_account_id == user.id)).first()
    
    return {
        "account": user,
        "profile": profile
    }

@router.get("/system-rules")
def list_system_rules(
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    rules = session.exec(select(TutorSystemRule).order_by(TutorSystemRule.sort_order)).all()
    return rules

class SystemRuleUpdate(BaseModel):
    rule_text: str
    enabled: bool
    sort_order: int

@router.patch("/system-rules/{rule_id}")
def update_system_rule(
    rule_id: int,
    data: SystemRuleUpdate,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    rule = session.get(TutorSystemRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    rule.rule_text = data.rule_text
    rule.enabled = data.enabled
    rule.sort_order = data.sort_order
    
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


