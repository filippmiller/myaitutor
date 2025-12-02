"""
Token health check service for AI providers.

This module provides health checking for AI API tokens (OpenAI, Yandex SpeechKit, etc).
"""
import logging
import json
from typing import Literal, Any
from pydantic import BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)

class TokenHealthResult(BaseModel):
    """Result of a token health check."""
    status: Literal["ok", "invalid", "quota", "error", "unknown"]
    message: str
    raw_error: str | None = None
    debug_info: dict[str, Any] | None = None  # Full request/response for debugging

async def test_openai_key(api_key: str, model: str = "gpt-4o-mini") -> TokenHealthResult:
    """
    Test an OpenAI API key by making a minimal API call.
    
    Args:
        api_key: The OpenAI API key to test
        model: The model to use for the test (default: gpt-4o-mini)
        
    Returns:
        TokenHealthResult with status, message, and full debug info
    """
    debug_info = {
        "provider": "OpenAI",
        "test_time": datetime.utcnow().isoformat(),
        "request": {
            "url": "https://api.openai.com/v1/chat/completions",
            "method": "POST",
            "headers": {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key[:10]}..." if api_key else "None"
            },
            "body": {
                "model": model,
                "messages": [{"role": "system", "content": "ping"}],
                "max_tokens": 1,
                "temperature": 0
            }
        },
        "response": None,
        "http_status": None,
        "error": None
    }
    
    try:
        from openai import AsyncOpenAI
        import httpx
        
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
        
        # Capture response details
        debug_info["response"] = {
            "id": completion.id,
            "object": completion.object,
            "created": completion.created,
            "model": completion.model,
            "choices": [
                {
                    "index": c.index,
                    "message": {
                        "role": c.message.role,
                        "content": c.message.content
                    },
                    "finish_reason": c.finish_reason
                } for c in completion.choices
            ],
            "usage": {
                "prompt_tokens": completion.usage.prompt_tokens if completion.usage else 0,
                "completion_tokens": completion.usage.completion_tokens if completion.usage else 0,
                "total_tokens": completion.usage.total_tokens if completion.usage else 0
            }
        }
        debug_info["http_status"] = 200
        
        # If we got here, the key works
        logger.info("OpenAI key test: SUCCESS")
        return TokenHealthResult(
            status="ok",
            message=f"✓ Key is valid. Test request succeeded with model {model}.",
            debug_info=debug_info
        )
        
    except Exception as e:
        error_str = str(e)
        error_lower = error_str.lower()
        
        # Try to extract HTTP status if available
        http_status = None
        if hasattr(e, 'status_code'):
            http_status = e.status_code
        elif "401" in error_str:
            http_status = 401
        elif "429" in error_str:
            http_status = 429
        elif "500" in error_str or "503" in error_str:
            http_status = int(error_str.split()[0]) if error_str.split()[0].isdigit() else 500
        
        debug_info["http_status"] = http_status
        debug_info["error"] = {
            "type": type(e).__name__,
            "message": error_str,
            "details": repr(e)
        }
        
        logger.warning(f"OpenAI key test failed: {e}")
        
        # Parse error type
        if "401" in error_lower or "invalid" in error_lower or "unauthorized" in error_lower:
            return TokenHealthResult(
                status="invalid",
                message="✗ Invalid API key (HTTP 401 Unauthorized)",
                raw_error=error_str,
                debug_info=debug_info
            )
        elif "429" in error_lower or "quota" in error_lower or "rate limit" in error_lower:
            return TokenHealthResult(
                status="quota",
                message="⚠ Rate limit exceeded or quota exhausted (HTTP 429)",
                raw_error=error_str,
                debug_info=debug_info
            )
        else:
            return TokenHealthResult(
                status="error",
                message=f"✗ Unexpected error: {error_str[:100]}",
                raw_error=error_str,
                debug_info=debug_info
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
