from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.database import create_db_and_tables
from app.api import admin, voice, voice_ws, tokens
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
app.include_router(tokens.router, prefix="/api/admin", tags=["tokens"])
app.include_router(voice.router, prefix="/api", tags=["voice"])
app.include_router(voice_ws.router, prefix="/api", tags=["voice_ws"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(progress.router, prefix="/api/progress", tags=["progress"])

# Static files (Audio)
os.makedirs("static/audio", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve Frontend (SPA Support)
if os.path.exists("frontend/dist"):
    # Mount assets (if they exist in dist/assets)
    if os.path.exists("frontend/dist/assets"):
        app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")
    
    # Serve index.html for root and catch-all
    from fastapi.responses import FileResponse
    
    @app.get("/")
    async def read_index():
        return FileResponse("frontend/dist/index.html")

    @app.get("/{full_path:path}")
    async def catch_all(full_path: str):
        # Allow API routes to pass through (already handled above)
        if full_path.startswith("api"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")
            
        # Check if file exists in dist (e.g. favicon.ico)
        file_path = os.path.join("frontend/dist", full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # Otherwise serve index.html for client-side routing
        return FileResponse("frontend/dist/index.html")
else:
    print("Frontend build not found. Run 'npm run build' in frontend/ directory.")

