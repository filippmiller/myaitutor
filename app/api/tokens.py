"""
API endpoints for AI token health management.
"""
import logging
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel

from app.database import get_session
from app.models import AppSettings
from app.services.token_health import test_openai_key, test_yandex_speechkit_key, mask_api_key, TokenHealthResult

logger = logging.getLogger(__name__)
router = APIRouter()

class ProviderStatus(BaseModel):
    """Status of a single AI provider token."""
    has_key: bool
    masked_key: str
    status: str  # ok, invalid, quota, error, unknown
    last_checked_at: str | None
    last_error: str | None

class TokensStatusResponse(BaseModel):
    """Response containing status of all AI provider tokens."""
    openai: ProviderStatus
    yandex_speechkit: ProviderStatus

class TestTokenRequest(BaseModel):
    """Request to test a specific provider's token."""
    provider: str  # "openai" or "yandex_speechkit"

class TestTokenResponse(BaseModel):
    """Response from testing a token."""
    provider: str
    status: str
    message: str
    last_checked_at: str
    debug_info: dict | None = None  # Full request/response debug info

@router.get("/tokens/status", response_model=TokensStatusResponse)
async def get_tokens_status(session: Session = Depends(get_session)):
    """
    Get the current status of all AI provider tokens.
    
    Returns aggregated health information for OpenAI and Yandex keys.
    """
    settings = session.get(AppSettings, 1)
    
    # OpenAI status
    openai_status = ProviderStatus(
        has_key=bool(settings and settings.openai_api_key),
        masked_key=mask_api_key(settings.openai_api_key if settings else None),
        status=settings.openai_key_status if settings and hasattr(settings, 'openai_key_status') else "unknown",
        last_checked_at=settings.openai_key_last_checked_at.isoformat() if settings and hasattr(settings, 'openai_key_last_checked_at') and settings.openai_key_last_checked_at else None,
        last_error=settings.openai_key_last_error if settings and hasattr(settings, 'openai_key_last_error') else None
    )
    
    # Yandex status (currently from env vars)
    yandex_key = os.getenv("YANDEX_API_KEY")
    yandex_status = ProviderStatus(
        has_key=bool(yandex_key),
        masked_key=mask_api_key(yandex_key),
        status=settings.yandex_key_status if settings and hasattr(settings, 'yandex_key_status') else "unknown",
        last_checked_at=settings.yandex_key_last_checked_at.isoformat() if settings and hasattr(settings, 'yandex_key_last_checked_at') and settings.yandex_key_last_checked_at else None,
        last_error=settings.yandex_key_last_error if settings and hasattr(settings, 'yandex_key_last_error') else None
    )
    
    return TokensStatusResponse(
        openai=openai_status,
        yandex_speechkit=yandex_status
    )

@router.post("/tokens/test", response_model=TestTokenResponse)
async def test_token(request: TestTokenRequest, session: Session = Depends(get_session)):
    """
    Test a specific AI provider's token.
    
    This makes an actual API call to verify the token is valid and working.
    Updates the token status in the database.
    """
    settings = session.get(AppSettings, 1)
    if not settings:
        settings = AppSettings(id=1)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    
    now = datetime.utcnow()
    
    if request.provider == "openai":
        # Check if key exists
        if not settings.openai_api_key:
            result = TokenHealthResult(
                status="error",
                message="OpenAI API key not configured"
            )
        else:
            # Test the key
            logger.info("Testing OpenAI API key...")
            result = await test_openai_key(
                api_key=settings.openai_api_key,
                model=settings.default_model
            )
        
        # Update settings (only if fields exist)
        if hasattr(settings, 'openai_key_status'):
            settings.openai_key_status = result.status
        if hasattr(settings, 'openai_key_last_checked_at'):
            settings.openai_key_last_checked_at = now
        if hasattr(settings, 'openai_key_last_error'):
            settings.openai_key_last_error = result.message if result.status != "ok" else None
        
        session.add(settings)
        session.commit()
        
        return TestTokenResponse(
            provider="openai",
            status=result.status,
            message=result.message,
            last_checked_at=now.isoformat(),
            debug_info=result.debug_info
        )
    
    elif request.provider == "yandex_speechkit":
        # Yandex keys are from env, not DB (for now)
        yandex_key = os.getenv("YANDEX_API_KEY")
        
        if not yandex_key:
            result = TokenHealthResult(
                status="error",
                message="Yandex API key not configured (check YANDEX_API_KEY env var)"
            )
        else:
            logger.info("Testing Yandex SpeechKit API key...")
            result = await test_yandex_speechkit_key(yandex_key)
        
        # Update settings (only if fields exist)
        if hasattr(settings, 'yandex_key_status'):
            settings.yandex_key_status = result.status
        if hasattr(settings, 'yandex_key_last_checked_at'):
            settings.yandex_key_last_checked_at = now
        if hasattr(settings, 'yandex_key_last_error'):
            settings.yandex_key_last_error = result.message if result.status != "ok" else None
        
        session.add(settings)
        session.commit()
        
        return TestTokenResponse(
            provider="yandex_speechkit",
            status=result.status,
            message=result.message,
            last_checked_at=now.isoformat(),
            debug_info=result.debug_info
        )
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {request.provider}"
        )
