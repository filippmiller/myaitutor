from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_session
from app.models import UserAccount, LessonSession
from app.services.auth_service import get_current_user

router = APIRouter()

# --- Language Mode Management ---

class LanguageModeUpdate(BaseModel):
    language_mode: str  # EN_ONLY, RU_ONLY, MIXED
    language_level: Optional[int] = None  # 1-5 for MIXED mode

@router.patch("/lessons/{lesson_id}/language-mode")
def update_lesson_language_mode(
    lesson_id: int,
    data: LanguageModeUpdate,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Update the language mode for a specific lesson session.
    This is typically called after the tutor detects the student's language preference.
    """
    # Validate language_mode
    valid_modes = ["EN_ONLY", "RU_ONLY", "MIXED"]
    if data.language_mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Invalid language_mode. Must be one of: {valid_modes}")
    
    # Get lesson session
    lesson = session.get(LessonSession, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson session not found")
    
    # Verify ownership
    if lesson.user_account_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this lesson")
    
    # Update language mode
    lesson.language_mode = data.language_mode
    lesson.language_level = data.language_level
    lesson.language_chosen_at = datetime.utcnow()
    
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    
    return {
        "success": True,
        "lesson_id": lesson.id,
        "language_mode": lesson.language_mode,
        "language_level": lesson.language_level,
        "message": f"Language mode set to {data.language_mode}"
    }

@router.get("/lessons/{lesson_id}/language-mode")
def get_lesson_language_mode(
    lesson_id: int,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get the current language mode for a lesson session."""
    lesson = session.get(LessonSession, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson session not found")
    
    if lesson.user_account_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return {
        "lesson_id": lesson.id,
        "language_mode": lesson.language_mode,
        "language_level": lesson.language_level,
        "language_chosen_at": lesson.language_chosen_at
    }
