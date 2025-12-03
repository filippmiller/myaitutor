# Realtime Voice Migration (2025-12-03)

## Overview
This migration upgrades the AIlingva voice experience to use OpenAI's **Realtime API** (Beta). This enables "ChatGPT Voice" quality interactions with:
- **Low Latency**: Streaming audio in and out simultaneously.
- **Mixed Language Support**: Native handling of Russian/English code-switching without manual toggles.
- **Interruptibility**: The model can listen while speaking (though frontend support for echo cancellation is required for perfect experience).

## Architecture

### Previous Architecture (Request/Response)
1. **User** speaks -> Audio Buffer.
2. **VAD** detects silence.
3. **Backend** saves WAV file.
4. **Whisper API** transcribes file (STT).
5. **LLM** generates text.
6. **TTS API** generates audio file.
7. **Backend** sends audio to User.

### New Architecture (Realtime Streaming)
1. **User** opens WebSocket `/ws/voice`.
2. **Backend** opens WebSocket to `wss://api.openai.com/v1/realtime`.
3. **User** streams audio chunks -> **Backend** resamples (48k -> 24k) -> **OpenAI**.
4. **OpenAI** processes VAD, STT, LLM, and TTS in a single continuous session.
5. **OpenAI** streams `audio.delta` (PCM 24k) -> **Backend** wraps in WAV -> **User**.
6. **OpenAI** streams `transcript` events -> **Backend** forwards to User UI.

## Configuration
- **Model**: `gpt-4o-realtime-preview-2024-10-01`
- **Voice**: Configurable via Admin Panel (Alloy, Echo, Shimmer, etc.).
- **Formats**:
  - Input: PCM 16-bit 24kHz Mono.
  - Output: PCM 16-bit 24kHz Mono.

## Fallback Strategy
If the OpenAI Realtime connection fails (network, quota, beta instability):
1. Log the error.
2. Fallback to the **Yandex/Whisper** implementation (previous architecture).
   - STT: Yandex Streaming or Whisper File-based.
   - TTS: Yandex SpeechKit.

## Implementation Details
- **WebSocket Proxy**: `app/api/voice_ws.py` acts as a bridge.
- **Resampling**: `ffmpeg` is used to convert frontend audio (WebM/Opus or PCM 48k) to the required 24k format.
- **Session Management**: On connection, the backend sends a `session.update` event to OpenAI to set the system prompt and voice.

## Known Issues / Limitations
- **Beta API**: The Realtime API is in beta and may have rate limits or instability.
- **Cost**: Realtime API is significantly more expensive than standard Whisper/TTS.
- **Frontend Echo**: If the user uses speakers, the model might hear itself. Headphones recommended.
