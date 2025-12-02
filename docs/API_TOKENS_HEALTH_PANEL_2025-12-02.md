# AI Tokens Health Panel - Operator Manual

**Created:** 2025-12-02  
**Purpose:** Monitor and test AI provider API keys

---

## Overview

The AI Tokens Health Panel provides a centralized dashboard to:
- View the status of all AI provider API keys (OpenAI, Yandex SpeechKit)
- Test keys on demand to verify they're working
- See last check time and error messages
- Quick diagnosis of "Brain connection failed" errors

---

## Accessing the Panel

1. Navigate to `/admin` in your browser
2. Scroll down to the **"🔑 AI Tokens Health Panel"** section
3. You'll see a table with all configured providers

---

## Status Indicators

Each provider shows a colored status badge:

- **● OK** (Green) - Token is valid and working
- **● INVALID** (Red) - Wrong key / Unauthorized (HTTP 401)
- **● QUOTA** (Orange) - Rate limit exceeded or quota exhausted (HTTP 429)
- **● ERROR** (Red) - Other unexpected error
- **● UNKNOWN** (Gray) - Token has never been tested

---

## Testing a Token

1. Click the **"🔬 Check Token"** button next to a provider
2. Wait a few seconds for the test to complete
3. The status will update automatically
4. If there's an error, check the "Error" column for details

**What the test does:**
- **OpenAI:** Makes a minimal chat completion request (max_tokens=1) to verify the key works
- **Yandex:** Currently shows "Not yet implemented" (keys are from env vars)

---

## Troubleshooting

### "Failed to generate greeting (OpenAI Error)"

**Diagnosis:**
1. Check the OpenAI row in the Tokens Panel
2. Look at the Status column:
   - If **INVALID**: The API key is wrong or expired
   - If **QUOTA**: You've hit your rate limit or quota
   - If **ERROR**: See the error message for details

**Fix:**
1. Go to https://platform.openai.com/account/api-keys
2. Create a new API key or verify your existing one
3. Update the key in the Admin Settings (top of admin page)
4. Click "Save All Settings"
5. Click "🔬 Check Token" in the Tokens Panel to verify

### "Brain connection failed (OpenAI Error)"

Same as above - this means the OpenAI API call failed during the conversation.

### Yandex SpeechKit Issues

**Note:** Yandex keys are currently loaded from environment variables (`YANDEX_API_KEY`), not the database. 
If you see issues with STT/TTS:
1. Check that `YANDEX_API_KEY` is set in your Railway environment
2. The health check for Yandex is not yet fully implemented

---

## API Endpoints

If you need to integrate programmatically:

### GET `/api/admin/tokens/status`
Returns status of all providers:
```json
{
  "openai": {
    "has_key": true,
    "masked_key": "********abcd",
    "status": "ok",
    "last_checked_at": "2025-12-02T13:30:00Z",
    "last_error": null
  },
  "yandex_speechkit": {
    "has_key": true,
    "masked_key": "********yGl",
    "status": "unknown",
    "last_checked_at": null,
    "last_error": null
  }
}
```

### POST `/api/admin/tokens/test`
Test a specific provider:
```json
{
  "provider": "openai"  // or "yandex_speechkit"
}
```

Response:
```json
{
  "provider": "openai",
  "status": "ok",
  "message": "Key is valid. Test request succeeded with model gpt-4o-mini.",
  "last_checked_at": "2025-12-02T13:30:00Z"
}
```

---

## Security Notes

- API keys are **never** logged in full
- Only the last 4 characters are shown in the UI
- Test requests use minimal tokens to save costs
- All endpoints require admin authentication

---

## Future Enhancements

**Planned:**
- [ ] Automatic periodic health checks
- [ ] Email/Slack notifications for token failures
- [ ] Full Yandex SpeechKit health check implementation
- [ ] Store Yandex keys in database (currently env vars only)
- [ ] Token usage statistics
- [ ] Cost tracking per provider

---

## Support

If you encounter issues:
1. Check the Railway logs for detailed error messages
2. Verify your API keys are valid on the provider's dashboard
3. Ensure you have sufficient quota/credits
4. Check that environment variables are set correctly on Railway
