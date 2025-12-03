# Voice Analytics & Stack Upgrade (2025-12-03)

## 1. Minute-Based Revenue Analytics

### Overview
We have implemented a new Analytics section in the Admin panel to track revenue and usage minutes.

### Backend
- **Endpoint**: `GET /api/admin/analytics/revenue/minutes`
- **Parameters**:
    - `from_date` (ISO 8601)
    - `to_date` (ISO 8601)
    - `group_by`: `hour` | `day`
- **Logic**: Aggregates `UsageSession` records.
    - `total_minutes`: Sum of `billed_minutes`.
    - `total_revenue`: Sum of `billed_amount_rub`.

### Frontend
- **Page**: Admin -> Analytics
- **Components**: `AdminAnalytics.tsx`
- **Features**:
    - Date range picker.
    - Grouping selector (Day/Hour).
    - Summary cards (Total Revenue, Minutes, Sessions).
    - Bar chart visualization.
    - Detailed data table.

## 2. Voice Stack Upgrade

### Streaming Architecture
We have upgraded the voice stack to support streaming for lower latency.

- **TTS (Text-to-Speech)**:
    - **OpenAI**: Uses `with_streaming_response` to stream audio chunks immediately.
    - **Yandex**: Refactored `YandexVoiceEngine` to pipe PCM stream through `ffmpeg` and yield MP3 chunks in real-time.
    - **Frontend**: `Student.tsx` queues received audio chunks and plays them sequentially.

- **STT (Speech-to-Text)**:
    - **OpenAI Realtime**: Uses WebSocket streaming (default for English).
    - **Legacy/Yandex**: Uses VAD + File Upload (currently). Future upgrade can use Yandex Streaming STT (already partially implemented in `YandexService` but requires protocol shift in `voice_ws.py`).

### Latency Monitoring
- **Instrumentation**: `voice_ws.py` now logs TTS and STT latency.
- **Stats**: In-memory stats are collected (last 20 samples).
- **Admin View**: "Voice Stack Health" panel in Analytics page shows current provider, model, streaming status, and average latency.

### Configuration
- **Settings**: Admin -> Settings allows configuring OpenAI Key.
- **User Preferences**: Users can select preferred TTS engine (OpenAI/Yandex) and Voice ID.

## 3. Verification
- **Analytics**: Verified backend endpoint returns correct aggregations.
- **Voice**: Verified code paths for streaming TTS are implemented. Frontend supports binary audio queuing.
