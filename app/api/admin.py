from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models import AppSettings
from pydantic import BaseModel

router = APIRouter()

class SettingsUpdate(BaseModel):
    openai_api_key: str
    default_model: str

@router.get("/settings")
def get_settings(session: Session = Depends(get_session)):
    settings = session.get(AppSettings, 1)
    if not settings:
        return {"openai_api_key": None, "default_model": "gpt-4o-mini"}
    
    # Mask key for security if needed, but user said "open is fine for personal project"
    # We will return it as is for convenience as requested
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
