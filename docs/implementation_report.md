# AIlingva Implementation Report

## Executive Summary

This report details the technical implementation of **AIlingva**, a minimal viable product (MVP) for an AI-powered English tutor application. The system is designed to be a full-stack web application capable of voice-to-voice interaction, utilizing OpenAI's advanced models for Speech-to-Text (STT), Natural Language Processing (LLM), and Text-to-Speech (TTS). The application is container-ready and configured for deployment on Railway.

## 1. Architecture Overview

The application follows a modern decoupled architecture:

*   **Backend**: Python 3.11+ using **FastAPI**. It handles API requests, database interactions, and orchestrates calls to OpenAI services.
*   **Frontend**: TypeScript-based Single Page Application (SPA) built with **React** and **Vite**. It manages the user interface, audio recording, and playback.
*   **Database**: **SQLite** (via SQLModel) for persistent storage of user profiles, chat history, and application settings.
*   **Deployment**: Configured with `nixpacks.toml` for seamless deployment on Railway, serving both the API and the static frontend assets.

## 2. Backend Implementation (`app/`)

### 2.1 Core Framework
*   **FastAPI**: Chosen for its high performance and native support for asynchronous operations, which is crucial for handling audio streams and external API calls.
*   **Uvicorn**: An ASGI web server implementation used to run the FastAPI application.

### 2.2 Data Models (`app/models.py`)
We utilized **SQLModel** to define the database schema, combining Pydantic's validation with SQLAlchemy's ORM capabilities.

*   **`AppSettings`**: Stores global configuration like the OpenAI API Key and the selected model (e.g., `gpt-4o-mini`).
*   **`UserProfile`**: Stores student details: Name, English Level (A1-C1), Goals, and Pains.
*   **`UserState`**: Tracks learning progress, specifically "weak words" (struggled with) and "known words". Stored as JSON strings for flexibility.
*   **`SessionMessage`**: Records the full chat history (User and Assistant roles) for context-aware conversations.

### 2.3 API Endpoints
*   **`POST /api/voice_chat`**: The core loop.
    1.  Receives audio blob (WebM) and `user_id`.
    2.  Validates API Key configuration.
    3.  Transcribes audio using **Whisper** (OpenAI).
    4.  Retrieves conversation history and user profile.
    5.  Generates a response using **GPT-4** (or selected model) with a specialized System Prompt.
    6.  Converts the text response to audio using **OpenAI TTS**.
    7.  Returns the transcription, text response, and audio URL.
*   **`GET/POST /api/admin/settings`**: Allows secure configuration of the OpenAI API Key without redeploying or editing environment variables.
*   **`GET/POST /api/profile`**: Manages the student's personal information and learning goals.

### 2.4 Services (`app/services/openai_service.py`)
Encapsulates all interactions with the OpenAI API.
*   **System Prompt**: A carefully crafted prompt instructs the AI to act as a supportive tutor, adapting its vocabulary to the user's level, correcting mistakes gently, and reusing "weak words" to reinforce learning.

## 3. Frontend Implementation (`frontend/`)

### 3.1 Technology Stack
*   **React 18**: For building a dynamic user interface.
*   **TypeScript**: Ensures type safety and better developer experience.
*   **Vite**: Next-generation frontend tooling for fast builds and hot module replacement.

### 3.2 Key Components
*   **`Student.tsx`**: The main interface.
    *   **Profile Management**: Form to input name, level, etc.
    *   **Voice Recorder**: Implements the `MediaRecorder` API to capture microphone input as blobs.
    *   **Push-to-Talk Logic**: Handles the "Hold to Speak" interaction pattern.
    *   **Audio Playback**: Automatically plays the returned TTS audio.
*   **`Admin.tsx`**: A secure-by-obscurity admin panel to set the API key.
*   **Proxy Configuration**: `vite.config.ts` is set up to proxy `/api` requests to the backend (localhost:8000) during local development, eliminating CORS issues.

## 4. Deployment Strategy

### 4.1 Railway Configuration (`nixpacks.toml`)
We created a custom Nixpacks configuration to handle the multi-language nature of the project (Python + Node.js).
*   **Phases**:
    *   `setup`: Installs Python 3.11 and Node.js.
    *   `build`: Runs `npm run build` for the frontend and `pip install` for the backend.
*   **Start Command**: Launches the FastAPI app, which is configured to serve the built frontend static files from the root URL.

### 4.2 Static File Serving
The FastAPI app (`app/main.py`) is configured to mount the `frontend/dist` directory to the root path `/`. This allows the entire application to run as a single service in production.

## 5. Security & Scalability Considerations

*   **API Key Storage**: Stored in the database for ease of use in this MVP. For a production environment, this should be moved to encrypted secrets or environment variables.
*   **Database**: SQLite is excellent for this MVP. For scaling to thousands of users, the app is ready to switch to PostgreSQL by simply changing the connection string in `database.py`.
*   **Audio Storage**: Currently saves TTS files locally to `static/audio`. In a scaled environment, this should be updated to upload to S3 or similar object storage.

## Conclusion

The implemented solution meets all requirements for a "minimal but alive" MVP. It provides a seamless user experience where a student can configure the app, define their persona, and immediately start a voice conversation with an AI tutor that remembers context and adapts to their level.
