# Codex Agent Instructions

All Codex agents working in this repo should read this file first.

## Dev Setup (Quick)

Full instructions live in `docs/DEV_SETUP.md`. Summary:

1) Backend
```bash
uvicorn app.main:app --reload
```

2) Frontend
```bash
cd frontend
npm install
npm run dev
```

Backend runs on `http://localhost:8000` and frontend on `http://localhost:5173`.

## If Port 8000 Is Busy

Run the backend on a different port and point Vite at it:
```bash
uvicorn app.main:app --reload --port 8010
VITE_API_PROXY_TARGET=http://127.0.0.1:8010 npm run dev -- --port 5175 --strictPort
```

Open `http://localhost:5175`.

## Logs and Debugging

Inventory and locations: `docs/LOGS_AND_DEBUGGING.md`
