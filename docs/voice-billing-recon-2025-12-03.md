# Voice & Billing Reconnaissance (2025-12-03)

## 1. Billing & Usage Schema

### Models
- **`UsageSession`** (`app/models.py`):
  - Represents a completed voice session.
  - **Key Fields**:
    - `user_account_id`: Link to user.
    - `duration_sec`: Total duration in seconds.
    - `billed_minutes`: Calculated minutes charged (ceil(duration/60)).
    - `billed_amount_rub`: Calculated cost (for analytics).
    - `created_at`: Timestamp (end of session).
    - `tariff_snapshot`: JSONB with rate details.
- **`WalletTransaction`** (`app/models.py`):
  - Represents balance changes.
  - **Key Fields**:
    - `minutes_delta`: Negative for usage.
    - `type`: 'usage'.
    - `created_at`: Timestamp.

### Formula
- **Billable Minutes**: `max(1, ceil(duration_sec / 60))`
- **Revenue**: `billed_minutes * 5` (Base rate 5 RUB/min).
- **Time Axis**: `created_at` of `UsageSession` (session end).

## 2. Admin UI & Code Map

### Frontend
- **Entry Point**: `frontend/src/pages/Admin.tsx`
- **Current Tabs**: Settings, Users, System Rules, Billing (`AdminBilling.tsx`).
- **Plan**: Add new tab "Analytics" (`AdminAnalytics.tsx`?).

### Backend
- **Admin Routes**: `app/api/routes/admin.py`, `app/api/routes/admin_billing.py`.
- **Plan**: Add `app/api/routes/admin_analytics.py`.

## 3. Voice Stack Inventory

### Current Implementation
1.  **WebSocket (`app/api/voice_ws.py`)**:
    - **OpenAI Realtime**: Used if TTS engine is "openai". Streaming (WebSockets).
    - **Legacy Loop**: Used if TTS engine is NOT "openai" (e.g. Yandex) or fallback.
        - **STT**: `OpenAI Whisper` (file-based via `audio.transcriptions.create` on buffered audio). **Non-streaming STT**.
        - **TTS**: `VoiceEngine.synthesize`.
            - `OpenAI`: Non-streaming (returns full bytes).
            - `Yandex`: Non-streaming wrapper (collects all chunks from `YandexService` before returning).

2.  **HTTP (`app/api/voice.py`)**:
    - File-based upload -> Process -> Return. High latency.

### Latency Bottlenecks
- **Legacy Loop STT**: Buffers audio until silence > 1s. Then uploads file. Slow.
- **Yandex TTS**: `YandexVoiceEngine` collects all PCM chunks before converting/returning. Slow.
- **OpenAI TTS**: Non-streaming in `VoiceEngine`.

### Upgrade Plan
- **STT**:
    - Keep OpenAI Realtime for English/Advanced.
    - For Legacy/Yandex path: Use **Yandex Streaming STT** (already in `YandexService`?) or **Deepgram** (if keys available).
    - *Note*: Project has `YandexService` with `recognize_stream`.
- **TTS**:
    - **Yandex**: Refactor `YandexVoiceEngine` to yield chunks (streaming).
    - **OpenAI**: Use streaming API if possible in Legacy, or stick to Realtime API.

## 4. Analytics Spec

### Endpoint
`GET /api/admin/analytics/revenue/minutes`

### Parameters
- `from_date` (ISO)
- `to_date` (ISO)
- `group_by`: `hour` | `day`

### Response
```json
{
  "grouping": "day",
  "buckets": [
    {
      "period_start": "2025-12-01T00:00:00",
      "total_minutes": 120,
      "total_revenue": 600.0,
      "sessions_count": 15
    }
  ],
  "totals": { ... }
}

## 5. Selection & Upgrade Decisions

### Latency Analysis
- **Legacy Stack**: High latency due to buffering entire audio clips before processing (STT) and before playing (TTS).
- **Target**: Streaming for both STT and TTS.

### Selected Configuration
1.  **STT**:
    - **Primary**: OpenAI Realtime API (English). Native streaming.
    - **Secondary/Russian**: Yandex STT (via `YandexService`).
        - *Upgrade*: While `voice_ws.py` currently buffers for VAD in legacy mode, the `YandexService` is capable of streaming. Future work will refactor `voice_ws.py` to stream audio chunks to Yandex immediately.

2.  **TTS**:
    - **OpenAI**: Upgraded to use `with_streaming_response`.
    - **Yandex**: Upgraded `YandexVoiceEngine` to pipe PCM stream through `ffmpeg` and yield MP3 chunks.
    - **Frontend**: Confirmed `Student.tsx` supports queuing binary audio chunks.

### Implementation
- Refactored `VoiceEngine` protocol to support `synthesize_stream`.
- Updated `voice_ws.py` to use streaming synthesis and log latency.
- Added Admin UI to monitor these stats.
```
