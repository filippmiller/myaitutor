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

class UserPreferencesUpdate(BaseModel):
    preferred_address: str | None = None
    preferred_voice: str | None = None

@router.patch("/users/{user_id}/preferences")
def update_user_preferences(
    user_id: int,
    data: UserPreferencesUpdate,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    user = session.get(UserAccount, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    profile = session.exec(select(UserProfile).where(UserProfile.user_account_id == user.id)).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    import json
    try:
        prefs = json.loads(profile.preferences)
    except:
        prefs = {}
        
    if data.preferred_address is not None:
        prefs["preferred_address"] = data.preferred_address
    if data.preferred_voice is not None:
        prefs["preferred_voice"] = data.preferred_voice
        
    profile.preferences = json.dumps(prefs)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    
    return profile

class TestVoiceRequest(BaseModel):
    text: str
    voice: str

@router.post("/test-voice-gen")
async def test_voice_gen(
    data: TestVoiceRequest,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    settings = session.get(AppSettings, 1)
    if not settings or not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OpenAI key not configured")

    # 1. Check Yandex
    yandex_voices = ['alisa', 'alena', 'filipp', 'jane', 'madirus', 'omazh', 'zahar', 'ermil']
    
    import os
    import uuid
    from fastapi.responses import FileResponse
    
    temp_filename = f"static/audio/test_{uuid.uuid4()}.mp3"
    os.makedirs("static/audio", exist_ok=True)
    full_path = os.path.join(os.getcwd(), temp_filename)
    
    if data.voice in yandex_voices:
        try:
            from app.services.yandex_service import YandexService
            import subprocess
            yandex_service = YandexService()
            
            process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-f", "s16le", "-ar", "48000", "-ac", "1", "-i", "pipe:0",
                    "-y",
                    full_path
                ],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            
            for chunk in yandex_service.synthesize_stream(text=data.text, voice=data.voice):
                try:
                    process.stdin.write(chunk)
                except BrokenPipeError:
                    break
            
            process.stdin.close()
            process.wait()
            
            return FileResponse(full_path)
        except Exception as e:
            print(f"Yandex Test Failed: {e}")
            raise HTTPException(status_code=500, detail=f"Yandex TTS failed: {str(e)}")
            
    # 2. Fallback to OpenAI
    try:
        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.audio.speech.create(
            model="tts-1",
            voice=data.voice if data.voice in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"] else "alloy",
            input=data.text
        )
        response.stream_to_file(full_path)
        return FileResponse(full_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI TTS failed: {str(e)}")

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


