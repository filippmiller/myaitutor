
# Yandex SpeechKit Integration Plan

## 1. Overview
We are switching from Deepgram to Yandex SpeechKit to support Russian language and better regional availability.

## 2. Requirements
- **Yandex Cloud Account**: Need a service account with `ai.speechkit-stt.user` and `ai.speechkit-tts.user` roles.
- **Credentials**:
    - `YANDEX_FOLDER_ID`
    - `YANDEX_API_KEY` (or IAM Token)
- **Library**: We can use `grpcio` and `yandex-cloud-ml-sdk` (or raw gRPC/REST).

## 3. Architecture Changes
- **STT (Speech-to-Text)**:
    - Use Yandex Streaming API (gRPC) for real-time recognition.
    - Format: OggOpus (preferred) or PCM.
- **LLM**:
    - Continue using OpenAI (`gpt-4o`) for logic, OR switch to YandexGPT if full localization is needed.
    - *Decision*: Stick with OpenAI for now, unless instructed otherwise.
- **TTS (Text-to-Speech)**:
    - Use Yandex SpeechKit TTS (API v3).
    - Voices: `alena`, `filipp`, `ermil`, etc.

## 4. Implementation Steps
1.  [ ] **Cleanup**: Remove Deepgram (Done).
2.  [ ] **Configuration**: Add Yandex credentials to `AppSettings` and `.env`.
3.  [ ] **Backend**:
    - Install `yandex-cloud` or `grpcio-tools`.
    - Implement `YandexSTTClient` wrapping the gRPC stream.
    - Implement `YandexTTSClient`.
4.  [ ] **Frontend**:
    - Ensure audio recording format is compatible (WebM/Opus is usually fine, Yandex supports OggOpus).
    - Update UI to reflect the new provider.

## 5. Next Actions
- Please provide `YANDEX_FOLDER_ID` and `YANDEX_API_KEY`.
- Confirm if we should also switch LLM to YandexGPT or keep OpenAI.
