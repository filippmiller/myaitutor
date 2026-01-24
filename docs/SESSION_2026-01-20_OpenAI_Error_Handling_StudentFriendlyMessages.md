# Session Notes: OpenAI Error Handling & Student-Friendly Messages

**Date:** 2026-01-20
**Focus:** Implementing graceful error handling for OpenAI API failures with student-friendly messaging
**Status:** Completed

---

## Problem Statement

When OpenAI returns an error (e.g., quota exceeded, invalid API key, billing issues), the system was displaying **technical error messages** to students that were:

1. **Confusing** - Messages like "OpenAI API Key missing" or "insufficient_quota" mean nothing to students
2. **Not actionable** - Students had no idea what to do next
3. **Unprofessional** - Raw technical errors exposed to end users

### Examples of Previous Error Messages

| Scenario | Old Message |
|----------|-------------|
| API key missing | "OpenAI API Key missing." |
| Quota exceeded | "OpenAI Realtime error: insufficient_quota" |
| Rate limited | "OpenAI Realtime error: rate_limit_exceeded" |
| Connection failed | Connection just closes silently |

---

## Solution Implemented

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Error Detection Flow                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  OpenAI API Error                                                │
│        │                                                         │
│        ▼                                                         │
│  ┌─────────────────┐                                             │
│  │ is_critical_    │──Yes──► classify_api_error()                │
│  │ api_error()     │              │                              │
│  └────────┬────────┘              ▼                              │
│           │              get_student_error_message()             │
│           │                       │                              │
│          No                       ▼                              │
│           │              Send friendly message                   │
│           ▼              Close connection                        │
│     Fall back to                                                 │
│     legacy mode                                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Critical vs Non-Critical Errors**
   - **Critical errors** (quota, billing, auth) → Show friendly message, close session
   - **Non-critical errors** (transient network issues) → Show warning, fall back to legacy mode

2. **Two-Layer Message System**
   - `message`: Student-friendly, actionable text
   - `technical_detail`: Original error for debugging (expandable in UI)

3. **Localization-Ready**
   - English messages implemented
   - Russian translations prepared for future activation

---

## Files Created/Modified

### 1. NEW: `app/services/error_messages.py`

New module containing all error handling logic:

```python
# Critical error patterns that trigger student-friendly messages
CRITICAL_ERROR_PATTERNS = [
    "insufficient_quota",
    "rate_limit",
    "invalid_api_key",
    "authentication",
    "billing",
    "exceeded your current quota",
    # ... more patterns
]

# Student-facing messages
STUDENT_ERROR_MESSAGES = {
    "service_unavailable": (
        "We're sorry, but the class cannot take place right now due to "
        "technical difficulties. Please contact the administrator to check "
        "for technical problems."
    ),
    "api_key_missing": (
        "The lesson service is not properly configured. Please contact "
        "the administrator to resolve this issue."
    ),
    "all_fallbacks_failed": (
        "We're experiencing technical difficulties with all available services. "
        "Please contact the administrator and try again later."
    ),
    "connection_lost": (
        "The connection to the lesson service was lost. Please refresh "
        "the page to reconnect, or contact the administrator if the "
        "problem persists."
    ),
}

# Key functions
def is_critical_api_error(error_message: str) -> bool
def classify_api_error(error_message: str) -> str
def get_student_error_message(error_key: str, lang: str = "en") -> str
```

### 2. MODIFIED: `app/api/voice_ws.py`

**Import section (lines 28-32):**
```python
from app.services.error_messages import (
    is_critical_api_error,
    get_student_error_message,
    classify_api_error,
)
```

**API Key Missing Handler (lines 160-170):**
```python
if not api_key:
    logger.error("OpenAI API Key missing")
    friendly_msg = get_student_error_message("api_key_missing")
    await websocket.send_json({
        "type": "system",
        "level": "error",
        "message": friendly_msg,
        "technical_detail": "OpenAI API Key missing",
    })
    await websocket.close(code=1011)
    return
```

**Realtime Session Failure Handler (lines 243-265):**
```python
except Exception as e:
    error_str = str(e)
    # Check if this is a critical error that affects all services
    if is_critical_api_error(error_str) or "Critical API error" in error_str:
        error_key = classify_api_error(error_str)
        friendly_msg = get_student_error_message(error_key)
        await websocket.send_json({
            "type": "system",
            "level": "error",
            "message": friendly_msg,
            "technical_detail": error_str,
            "is_critical": True,
        })
        await websocket.close(code=1011)
        return
    # Non-critical: fall through to legacy mode
    await websocket.send_json({
        "type": "system",
        "level": "warning",
        "message": "Realtime connection issue. Switching to standard mode.",
        "technical_detail": error_str,
    })
```

**Realtime Error Event Handler (lines 1247-1281):**
- Added critical error detection for OpenAI realtime error events
- Critical errors: send friendly message, raise to prevent fallback
- Non-critical errors: send warning, allow fallback to legacy mode

**Main Exception Handler (lines 288-311):**
```python
except Exception as e:
    logger.error(f"Main loop error: {e}", exc_info=True)
    error_str = str(e)
    try:
        if is_critical_api_error(error_str):
            error_key = classify_api_error(error_str)
            friendly_msg = get_student_error_message(error_key)
        else:
            friendly_msg = get_student_error_message("all_fallbacks_failed")
        await websocket.send_json({
            "type": "system",
            "level": "error",
            "message": friendly_msg,
            "technical_detail": error_str,
            "is_critical": True,
        })
    except Exception:
        pass  # WebSocket may already be closed
```

### 3. MODIFIED: `frontend/src/pages/Student.tsx`

**New State Variable (line 40):**
```typescript
const [errorMessage, setErrorMessage] = useState<{
    message: string;
    technical?: string
} | null>(null);
```

**Error Message Handler (lines 211-216):**
```typescript
if (msg.level === 'error') {
    setErrorMessage({
        message: msg.message,
        technical: msg.technical_detail
    });
    setConnectionStatus('Error');
}
```

**Error Banner Component (lines 499-537):**
```tsx
{errorMessage && (
    <div style={{
        backgroundColor: '#ff4444',
        color: 'white',
        padding: '15px',
        borderRadius: '8px',
        marginBottom: '15px',
        position: 'relative'
    }}>
        <button onClick={() => setErrorMessage(null)} ...>×</button>
        <div style={{ fontWeight: 'bold', marginBottom: '8px' }}>
            ⚠️ Lesson Interrupted
        </div>
        <div>{errorMessage.message}</div>
        {errorMessage.technical && (
            <details style={{ marginTop: '10px', fontSize: '0.9em', opacity: 0.8 }}>
                <summary style={{ cursor: 'pointer' }}>Technical details</summary>
                <div style={{ marginTop: '5px', fontFamily: 'monospace' }}>
                    {errorMessage.technical}
                </div>
            </details>
        )}
    </div>
)}
```

**Clear Error on New Lesson (line 105):**
```typescript
setErrorMessage(null);  // Clear any previous error
```

---

## Error Message Mapping

| Error Type | Detection Pattern | Student Message |
|------------|-------------------|-----------------|
| **API Key Missing** | Explicit check | "The lesson service is not properly configured. Please contact the administrator to resolve this issue." |
| **Quota Exceeded** | `insufficient_quota`, `exceeded your current quota` | "We're sorry, but the class cannot take place right now due to technical difficulties. Please contact the administrator to check for technical problems." |
| **Rate Limited** | `rate_limit` | Same as quota exceeded |
| **Billing Issues** | `billing` | Same as quota exceeded |
| **Auth Failure** | `unauthorized`, `forbidden`, `authentication` | Same as API key missing |
| **Connection Lost** | `timeout`, `connection refused` | "The connection to the lesson service was lost. Please refresh the page to reconnect, or contact the administrator if the problem persists." |
| **All Fallbacks Failed** | Catch-all | "We're experiencing technical difficulties with all available services. Please contact the administrator and try again later." |

---

## Russian Translations (Ready for Activation)

```python
STUDENT_ERROR_MESSAGES_RU = {
    "service_unavailable": (
        "К сожалению, урок не может состояться из-за технических неполадок. "
        "Пожалуйста, свяжитесь с администратором для проверки технических проблем."
    ),
    "api_key_missing": (
        "Сервис уроков не настроен должным образом. "
        "Пожалуйста, свяжитесь с администратором для решения этой проблемы."
    ),
    # ... etc
}
```

To activate: Pass `lang="ru"` to `get_student_error_message()` based on user's language preference.

---

## UI Before/After

### Before
- Browser `alert()` popup with raw error message
- Connection status changes to "Error"
- No actionable guidance

### After
- Styled red error banner in the chat interface
- Clear "Lesson Interrupted" header
- Friendly, actionable message
- Expandable "Technical details" for debugging
- Dismiss button to close the banner
- Error clears automatically when starting new lesson

---

## Testing Recommendations

### Manual Testing

1. **API Key Missing Test:**
   - Remove or invalidate the OpenAI API key in settings
   - Start a lesson
   - Expected: Friendly error message about configuration

2. **Quota Exceeded Simulation:**
   - Use an API key with depleted quota
   - Start a lesson
   - Expected: Friendly error about technical difficulties

3. **Network Failure Test:**
   - Start a lesson
   - Disconnect network mid-session
   - Expected: Connection lost message

### Automated Testing (Future)

Consider adding unit tests for:
- `is_critical_api_error()` with various error messages
- `classify_api_error()` error classification
- `get_student_error_message()` with different languages

---

## Existing Fallback Behavior (Preserved)

The system's existing multi-layer fallback strategy remains intact:

```
Realtime (gpt-4o/gpt-realtime)
    ↓ (on non-critical error)
Legacy Mode (Whisper + TTS)
    ↓ (on component error)
Fallback Engine (Yandex)
```

**Critical errors bypass fallback** because they typically affect all services (e.g., billing issues affect both Realtime and Legacy modes).

---

## Related Files (Reference)

- `app/services/openai_service.py` - STT/TTS with Yandex fallback
- `app/services/voice_engine.py` - OpenAI voice engine wrapper
- `app/services/smart_brain.py` - Background analysis (non-blocking errors)

---

## Summary

This implementation ensures students receive clear, actionable guidance when technical issues prevent lessons from proceeding, while preserving detailed technical information for administrators to diagnose problems. The system gracefully degrades when possible and fails gracefully with user-friendly messaging when degradation isn't possible.
