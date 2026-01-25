# Dev Setup

Clear, end-to-end steps to run the AIlingva app locally.

## Prereqs
- Python 3.12+
- Node.js 18+

## Backend (FastAPI)

Windows (PowerShell):
```powershell
cd C:\dev\ailingva
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

macOS/Linux:
```bash
cd /path/to/ailingva
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend will be at `http://localhost:8000`.

## Frontend (Vite + React)

Windows (PowerShell):
```powershell
cd C:\dev\ailingva\frontend
npm install
npm run dev
```

macOS/Linux:
```bash
cd /path/to/ailingva/frontend
npm install
npm run dev
```

Frontend will be at `http://localhost:5173`.

## When Port 8000 Is Busy

If something else is already using port 8000, run the backend on a different port and point Vite at it.

Example (backend on 8010, frontend on 5175):
```powershell
# Backend
uvicorn app.main:app --reload --port 8010

# Frontend (PowerShell)
$env:VITE_API_PROXY_TARGET='http://127.0.0.1:8010'
npm run dev -- --port 5175 --strictPort
```

Open `http://localhost:5175` in the browser.

## Quick Smoke Checks
- Backend docs: `http://localhost:8000/docs` (or your backend port)
- Frontend auth page: `http://localhost:5173/auth` (or your frontend port)
