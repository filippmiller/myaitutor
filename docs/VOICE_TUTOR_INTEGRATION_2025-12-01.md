# Voice Tutor Integration (OpenAI + Deepgram) - 2025-12-01

## Overview
This document describes the integration of OpenAI (Intelligence) and Deepgram (STT/TTS) into the AIlingva Tutor application.
The goal is to provide a low-latency, real-time voice lesson experience using WebSockets.

## Architecture

### Data Flow
1.  **User Audio** (Browser Microphone) -> **WebSocket** -> **Backend**
2.  **Backend** -> **Deepgram Live STT** (Streaming)
3.  **Deepgram STT** -> **Transcript Text** -> **Backend**
4.  **Backend** -> **OpenAI Chat Completion** (Context + Tutor Prompt) -> **Assistant Text**
5.  **Backend** -> **Deepgram TTS** (REST API) -> **Assistant Audio**
6.  **Backend** -> **WebSocket** -> **Frontend** (Text & Audio Playback)

### Components

#### 1. Database Models (`app/models.py`)
-   **AppSettings**: Stores API Keys and configuration.
    -   `openai_api_key`: OpenAI API Key.
    -   `deepgram_api_key`: Deepgram API Key.
    -   `deepgram_voice_id`: Voice ID for TTS (default: `aura-asteria-en`).
-   **LessonSession**: Tracks a voice lesson session.
    -   `status`: active/completed.
    -   `started_at`, `ended_at`.
-   **LessonTurn**: Tracks individual speech turns.
    -   `speaker`: "user" or "assistant".
    -   `text`: Transcribed text or AI response.

#### 2. Backend API
-   **Admin Settings** (`/api/admin/settings`): Configure keys and voice.
-   **Test Endpoints**:
    -   `/api/admin/test-openai`: Verifies OpenAI connection.
    -   `/api/admin/test-deepgram`: Verifies Deepgram connection.
-   **WebSocket Endpoint** (`/api/voice-lesson/ws`):
    -   Handles real-time audio streaming.
    -   Manages Deepgram Live connection.
    -   Orchestrates the conversation flow.

#### 3. Frontend
-   **Admin Page**: UI to input keys and test connections.
-   **Student Page**:
    -   "Start Live Lesson" button.
    -   Captures microphone audio (WebM/Opus).
    -   Streams to WebSocket.
    -   Displays live transcript.
    -   Plays back assistant audio automatically.

## Usage Flow

1.  **Setup**:
    -   Go to `/admin`.
    -   Enter OpenAI API Key.
    -   Enter Deepgram API Key.
    -   Click "Save".
    -   Use "Test" buttons to verify.

2.  **Start Lesson**:
    -   Go to `/student`.
    -   Click "Start Live Lesson".
    -   Allow microphone access.
    -   Speak into the microphone.

3.  **Interaction**:
    -   Your speech is transcribed in real-time.
    -   The AI Tutor responds with text and audio.
    -   The conversation continues until you click "End Lesson".

## Technical Details

-   **WebSocket Protocol**:
    -   **Client -> Server**: Binary Audio Chunks (WebM/Opus).
    -   **Server -> Client (Text)**: JSON `{"type": "transcript", "role": "user"|"assistant", "text": "..."}`.
    -   **Server -> Client (Audio)**: Binary Audio Data (MP3/WAV from TTS).

-   **Deepgram Configuration**:
    -   STT Model: `nova-2` (fast and accurate).
    -   TTS Voice: Configurable (default `aura-asteria-en`).

## Future Improvements
-   Implement streaming TTS (currently using REST API for simplicity).
-   Add interruption handling (stop audio when user speaks).
-   Save audio recordings to storage (S3/R2).
