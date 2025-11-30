# AIlingva - AI English Tutor MVP

Minimal viable product for an AI English tutor with voice interface.

## Features

- **Admin Panel**: Configure OpenAI API Key and Model.
- **Student Profile**: Set name, level, goals, and pains.
- **Voice Chat**: Push-to-talk interface with AI tutor.
- **Adaptive Learning**: AI adapts to your level and tracks weak words (basic implementation).
- **Persistence**: All data stored in SQLite.

## Project Structure

- `app/`: Backend (FastAPI)
  - `main.py`: App entry point.
  - `models.py`: Database models.
  - `api/`: API endpoints.
  - `services/`: Business logic (OpenAI integration).
- `frontend/`: Frontend (React + Vite)
  - `src/pages/`: Admin and Student pages.
  - `src/App.tsx`: Routing.

## Local Development Setup

1. **Backend**:
   ```bash
   # Create virtual env (optional but recommended)
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows

   # Install dependencies
   pip install -r requirements.txt

   # Run server
   uvicorn app.main:app --reload
   ```

2. **Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   Access the app at `http://localhost:5173` (or whatever port Vite uses).
   The frontend proxies `/api` requests to `http://localhost:8000`.

## Deployment on Railway

1. **Repo**: Push this code to a GitHub repository.
2. **Railway Project**: Create a new project on Railway from GitHub.
3. **Service Settings**:
   - **Build Command**: `cd frontend && npm install && npm run build` (Optional, if you want to serve static files from FastAPI, you need to build frontend first. However, for a simple Python deployment on Railway, you might need a custom build command or just deploy as a Python service and commit the build artifacts, or use a multi-stage Dockerfile.
   - **Simpler Railway Approach**:
     - Railway detects Python.
     - Add a `nixpacks.toml` or just rely on auto-detection.
     - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   
   **Important**: To serve the frontend from FastAPI in production, you must build the React app.
   
   **Recommended Build Command for Railway (if using Nixpacks/Buildpacks)**:
   `cd frontend && npm install && npm run build && cd .. && pip install -r requirements.txt`
   
   *Note: You might need to adjust the root directory or build settings depending on how Railway detects the project.*

## Usage Guide

1. **Setup**:
   - Go to `/admin`.
   - Enter your OpenAI API Key.
   - Click Save.

2. **Start Learning**:
   - Go to `/app`.
   - Fill in your profile (Name, Level, Goals).
   - Click "Save Profile".
   - Press and hold "Hold to Speak" button.
   - Speak into your microphone.
   - Release to send.
   - Listen to the AI response and read the text.

## Changing the Model

You can change the OpenAI model (e.g., to `gpt-4-turbo`) in the `/admin` page.

## Files Overview

- `app/models.py`: Defines `UserProfile`, `UserState`, `SessionMessage` tables.
- `app/api/voice.py`: Handles voice chat logic, STT, and TTS.
- `app/services/openai_service.py`: Interacts with OpenAI API.
- `frontend/src/pages/Student.tsx`: Main UI for the student.
