"""
Token health check service for AI providers.

This module provides health checking for AI API tokens (OpenAI, Yandex SpeechKit, etc).
"""
import logging
from typing import Literal
from pydantic import BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)

class TokenHealthResult(BaseModel):
    """Result of a token health check."""
    status: Literal["ok", "invalid", "quota", "error", "unknown"]
    message: str
    raw_error: str | None = None  # Internal error details, not for UI

async def test_openai_key(api_key: str, model: str = "gpt-4o-mini") -> TokenHealthResult:
    """
    Test an OpenAI API key by making a minimal API call.
    
    Args:
        api_key: The OpenAI API key to test
        model: The model to use for the test (default: gpt-4o-mini)
        
    Returns:
        TokenHealthResult with status and message
    """
    try:
        from openai import AsyncOpenAI
        
        # Create client with the key
        client = AsyncOpenAI(api_key=api_key)
        
        # Make a minimal test request
        logger.info("Testing OpenAI key with minimal request...")
        completion = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "ping"}],
            max_tokens=1,
            temperature=0
        )
        
        # If we got here, the key works
        logger.info("OpenAI key test: SUCCESS")
        return TokenHealthResult(
            status="ok",
            message=f"Key is valid. Test request succeeded with model {model}."
        )
        
    except Exception as e:
        error_str = str(e).lower()
        logger.warning(f"OpenAI key test failed: {e}")
        
        # Parse error type
        if "401" in error_str or "invalid" in error_str or "unauthorized" in error_str:
            return TokenHealthResult(
                status="invalid",
                message="Invalid API key (HTTP 401 Unauthorized)",
                raw_error=str(e)
            )
        elif "429" in error_str or "quota" in error_str or "rate limit" in error_str:
            return TokenHealthResult(
                status="quota",
                message="Rate limit exceeded or quota exhausted (HTTP 429)",
                raw_error=str(e)
            )
        else:
            return TokenHealthResult(
                status="error",
                message=f"Unexpected error: {str(e)[:100]}",
                raw_error=str(e)
            )

async def test_yandex_speechkit_key(api_key: str) -> TokenHealthResult:
    """
    Test a Yandex SpeechKit API key.
    
    Note: This is a placeholder for future implementation.
    Yandex keys are currently loaded from env vars, not the database.
    
    Args:
        api_key: The Yandex API key to test
        
    Returns:
        TokenHealthResult
    """
    # TODO: Implement Yandex key testing
    # For now, return unknown
    return TokenHealthResult(
        status="unknown",
        message="Yandex SpeechKit health check not yet implemented"
    )

def mask_api_key(key: str | None) -> str:
    """
    Mask an API key for display, showing only the last 4 characters.
    
    Args:
        key: The API key to mask
        
    Returns:
        Masked key string like "********abcd" or "Not set"
    """
    if not key:
        return "Not set"
    if len(key) <= 4:
        return "****"
    return "*" * (len(key) - 4) + key[-4:]
