from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session
from app.database import get_session
from app.models import AppSettings, UserAccount
from app.services.openai_service import process_voice_interaction, analyze_learning_exchange
from app.services.progress_service import apply_learning_update, create_session_summary
from app.services.auth_service import get_current_user
from app.services.profile_service import get_or_create_profile_for_user, get_or_create_state_for_user
import shutil
import os
import uuid

router = APIRouter()

@router.post("/voice_chat")
async def voice_chat(
    audio_file: UploadFile = File(...),
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    # 1. Check Settings
    settings = session.get(AppSettings, 1)
    if not settings or not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OpenAI key not configured, go to /admin")

    # 2. Get Profile and State for authenticated user
    profile = get_or_create_profile_for_user(session, current_user)
    state = get_or_create_state_for_user(session, current_user)
    
    # Ensure profile has state loaded (it should be linked via relationship, but let's be safe)
    # The service ensures they exist.
    
    # 3. Save temp audio file
    temp_filename = f"temp_{uuid.uuid4()}.webm"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(audio_file.file, buffer)
        
    try:
        # 4. Process with OpenAI Service
        result = await process_voice_interaction(
            audio_path=temp_filename,
            user=profile,
            settings=settings,
            db_session=session
        )
        
        # 5. Analyze and Update Progress
        analysis = analyze_learning_exchange(
            user_profile=profile,
            user_state=state,
            user_text=result["user_text"],
            assistant_text=result["assistant_text"],
            settings=settings
        )
        
        apply_learning_update(session, state, analysis)
        create_session_summary(session, current_user, analysis)
        
        return result
    finally:
        # Cleanup temp file
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@router.post("/profile")
def create_or_update_profile(
    name: str,
    english_level: str,
    goals: str,
    pains: str,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    # Get or create profile for the authenticated user
    profile = get_or_create_profile_for_user(session, current_user)
    
    # Update fields
    profile.name = name
    profile.english_level = english_level
    profile.goals = goals
    profile.pains = pains
    
    session.add(profile)
    session.commit()
    session.refresh(profile)
    
    # Ensure state exists too
    get_or_create_state_for_user(session, current_user)
    
    return profile

@router.get("/profile")
def get_profile(
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    # Get or create profile for the authenticated user
    profile = get_or_create_profile_for_user(session, current_user)
    return profile
