from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models import AppSettings
from pydantic import BaseModel
import openai
import requests

router = APIRouter()

class SettingsUpdate(BaseModel):
    openai_api_key: str
    default_model: str
    deepgram_api_key: str
    deepgram_voice_id: str

@router.get("/settings")
def get_settings(session: Session = Depends(get_session)):
    settings = session.get(AppSettings, 1)
    if not settings:
        return {
            "openai_api_key": None, 
            "default_model": "gpt-4o-mini",
            "deepgram_api_key": None,
            "deepgram_voice_id": "aura-asteria-en"
        }
    return settings

@router.post("/settings")
def update_settings(data: SettingsUpdate, session: Session = Depends(get_session)):
    settings = session.get(AppSettings, 1)
    if not settings:
        settings = AppSettings(id=1)
    
    settings.openai_api_key = data.openai_api_key
    settings.default_model = data.default_model
    settings.deepgram_api_key = data.deepgram_api_key
    settings.deepgram_voice_id = data.deepgram_voice_id
    
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

@router.post("/test-deepgram")
def test_deepgram(session: Session = Depends(get_session)):
    settings = session.get(AppSettings, 1)
    if not settings or not settings.deepgram_api_key:
        raise HTTPException(status_code=400, detail="Deepgram API Key not set")
    
    try:
        # Simple test to Deepgram Usage API or similar to verify token
        url = "https://api.deepgram.com/v1/projects"
        headers = {
            "Authorization": f"Token {settings.deepgram_api_key}",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return {"status": "ok", "message": "Deepgram connection successful"}
        else:
            return {"status": "error", "message": f"Deepgram API returned {response.status_code}: {response.text}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
