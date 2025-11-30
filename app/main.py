from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.database import create_db_and_tables
from app.api import admin, voice
from app.api.routes import auth, progress
import os

app = FastAPI(title="AIlingva MVP")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database init
@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    os.makedirs("static/audio", exist_ok=True)

# Routes
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(voice.router, prefix="/api", tags=["voice"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(progress.router, prefix="/api/progress", tags=["progress"])

# Static files (Audio)
os.makedirs("static/audio", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve Frontend (Build)
# We will assume frontend is built to /frontend/dist and we serve it.
# For development, we might just rely on Vite server, but for "deployment ready" we serve static.
# Let's check if dist exists, if so serve it.
if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
else:
    # Fallback for local dev if not built
    print("Frontend build not found. Run 'npm run build' in frontend/ directory.")

