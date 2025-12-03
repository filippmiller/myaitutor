# Voice Migration to OpenAI (2025-12-03)

## Overview
This migration shifts the default voice engine for AIlingva from Yandex SpeechKit to OpenAI (Whisper for STT and TTS-1 for synthesis). Yandex is retained as a robust fallback mechanism. The update includes a new `VoiceEngine` abstraction layer, database updates for user preferences, and a revamped Admin UI for voice management.

## Architecture: VoiceEngine
A new abstraction layer `VoiceEngine` (in `app/services/voice_engine.py`) standardizes interactions:
- **OpenAIVoiceEngine**: Uses `openai` python client.
  - STT: `whisper-1`
  - TTS: `tts-1` (Voices: Alloy, Echo, Fable, Onyx, Nova, Shimmer)
- **YandexVoiceEngine**: Uses `yandex-cloud` gRPC.
  - STT: Streaming recognition (converted from WebM via ffmpeg).
  - TTS: Streaming synthesis (converted to MP3 via ffmpeg).

## Configuration
New Environment Variables (implicitly used via `AppSettings` or `os.environ`):
- `OPENAI_API_KEY`: Required for OpenAI services.
- `YANDEX_API_KEY` / `YANDEX_FOLDER_ID`: Required for fallback.

## Database Changes
**UserProfile** table updated with new columns:
- `preferred_tts_engine` (varchar, default 'openai')
- `preferred_stt_engine` (varchar, default 'openai')
- `preferred_voice_id` (varchar, nullable)

*Note: The legacy `preferences` JSON field is still updated for backward compatibility.*

## Admin API
New endpoints in `/api/admin`:
- `GET /voices`: Returns list of available voices grouped by engine.
- `POST /voices/test`: Generates audio for a specific engine/voice/text.
- `POST /users/{id}/voice`: Updates a user's voice preferences.

## Lesson Flow
1. **Start**: User sends audio (WebM).
2. **STT**: System checks `preferred_stt_engine`.
   - Tries primary engine (e.g., OpenAI).
   - If failure, catches exception and tries Yandex.
3. **Processing**: AI Tutor generates text response (OpenAI Chat Completion).
4. **TTS**: System checks `preferred_tts_engine` and `preferred_voice_id`.
   - Tries primary engine.
   - If failure, falls back to Yandex (default voice 'alena').
5. **Response**: Audio saved to static file and URL returned to frontend.

## Fallback Mechanism
The fallback is implemented in `process_voice_interaction`. If an exception occurs during the primary engine's execution (STT or TTS), the system logs the error and immediately attempts the operation using the Yandex engine.

## Manual Testing
1. **Admin Panel**:
   - Go to Admin -> Users -> Details.
   - Select "OpenAI" and "Alloy". Click "Test Voice".
   - Select "Yandex" and "Zahar". Click "Test Voice".
   - Save settings for a user.
2. **Lesson**:
   - Log in as that user.
   - Speak a phrase.
   - Verify the response uses the selected voice.
   - Disconnect internet/invalidate OpenAI key (simulated) to test fallback (check logs).

## Future Improvements
- Add explicit "fallback_enabled" toggle in settings.
- Cache TTS responses for common phrases.
- Add "voice_style" support for engines that support it.
