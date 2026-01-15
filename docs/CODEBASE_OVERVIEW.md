# AIlingva - Codebase Overview

## 1. Project Overview

**AIlingva** is a full-stack AI English tutoring platform with voice interface designed for Russian-speaking students. It combines real-time conversational learning with intelligent analysis and brain event tracking.

**Core Mission**: Provide personalized English tutoring with real-time voice conversation, progress tracking, and intelligent analysis of student learning patterns.

---

## 2. Tech Stack

### Backend
| Component | Technology |
|-----------|------------|
| Framework | FastAPI (Python) |
| ORM | SQLModel (SQLAlchemy + Pydantic) |
| Server | Uvicorn |
| Database | PostgreSQL (Supabase) / SQLite (dev) |
| Migrations | Alembic |
| AI Services | OpenAI (GPT, Whisper, TTS), Yandex Cloud (STT/TTS) |
| Voice Processing | FFmpeg, WebRTC codecs |
| Auth | JWT + Session cookies |
| Security | Passlib (bcrypt/argon2) |

### Frontend
| Component | Technology |
|-----------|------------|
| Framework | React 18 + TypeScript |
| Build Tool | Vite |
| Routing | React Router v6 |
| Icons | Lucide React |
| State | React Context API |

### Infrastructure
- **Containerization**: Docker (multi-stage build)
- **Deployment**: Railway/Cloud-native

---

## 3. Directory Structure

```
C:\dev\ailingva\
├── app/                          # FastAPI backend
│   ├── main.py                   # Entry point
│   ├── models.py                 # Database models (30+)
│   ├── database.py               # DB engine & sessions
│   ├── security.py               # Password hashing, JWT
│   ├── api/
│   │   ├── admin.py              # Admin settings
│   │   ├── voice.py              # Voice REST endpoint
│   │   ├── voice_ws.py           # WebSocket streaming
│   │   └── routes/               # Modular API endpoints
│   │       ├── auth.py           # Register/Login/Logout
│   │       ├── billing.py        # Wallet, transactions
│   │       ├── progress.py       # Learning progress
│   │       ├── admin_tutor.py    # Pipeline monitoring
│   │       └── admin_voice_rules.py
│   └── services/                 # Business logic
│       ├── openai_service.py     # ChatGPT, STT/TTS
│       ├── brain_service.py      # Analysis pipeline
│       ├── tutor_service.py      # Lesson management
│       ├── billing_service.py    # Wallet & minutes
│       └── ...
├── frontend/                     # React application
│   ├── src/
│   │   ├── App.tsx               # Main routing
│   │   ├── pages/
│   │   │   ├── Admin.tsx         # Admin panel
│   │   │   ├── Student.tsx       # Learning interface
│   │   │   └── AuthPage.tsx      # Login/Register
│   │   ├── components/           # UI components
│   │   ├── context/              # Auth context
│   │   └── api/                  # API clients
│   └── dist/                     # Built frontend
├── alembic/                      # DB migrations
├── static/                       # Audio, logs, prompts
├── supabase/                     # Supabase config
└── docs/                         # Documentation
```

---

## 4. Key Features

### Voice Chat System
- Real-time bidirectional WebSocket streaming
- STT via OpenAI Whisper or Yandex Cloud
- TTS via OpenAI or Yandex Cloud
- Audio queue management with playback sync

### Adaptive Learning
- **Weak Words**: Track words student struggles with
- **Known Words**: Repository of mastered vocabulary
- **Progress Tracking**: Sessions, messages, XP points
- **Session Summaries**: Practiced words, grammar notes

### Multi-Pipeline Architecture
| Pipeline | Purpose |
|----------|---------|
| STREAMING | Real-time voice conversation |
| ANALYSIS | Brain events for learning insights |

### Brain Events System
- Detects weak words and grammar patterns
- Generates tutor rules dynamically
- Tracks learning progress with snapshots

### Admin Panel
- OpenAI API key & model configuration
- User management with roles
- Billing packages & transactions
- Analytics dashboard
- Voice-based rule generation
- Pipeline monitoring dashboard

### Billing & Monetization
- Wallet system (5 RUB/minute base)
- Tiered discount packages
- Referral program
- Trial bonus (60 free minutes)

---

## 5. Database Models

### Authentication
- `UserAccount` - Email, password, role
- `AuthSession` - Session tracking with expiry

### Learning
- `UserProfile` - Name, level, goals, voice prefs
- `UserState` - Weak/known words, progress, XP
- `LessonSession` - Lesson sessions
- `LessonTurn` - Conversation turns

### Multi-Pipeline
- `TutorLesson` - Numbered lessons
- `TutorLessonTurn` - Turns with pipeline type
- `TutorBrainEvent` - Analysis events
- `TutorStudentKnowledge` - Knowledge snapshots
- `TutorRule` - Dynamic tutor rules

### Billing
- `BillingPackage` - Discount packages
- `WalletTransaction` - All transactions
- `UsageSession` - Session billing
- `Referral` - Referral tracking

---

## 6. API Routes

| Route | Purpose |
|-------|---------|
| `POST /api/auth/register` | Create account |
| `POST /api/auth/login` | Login |
| `POST /api/auth/logout` | Logout |
| `GET /api/auth/me` | Current user |
| `POST /api/voice_chat` | Voice REST endpoint |
| `WS /ws/voice` | Real-time voice streaming |
| `GET /api/progress/progress` | Learning progress |
| `GET /api/billing/balance` | Wallet balance |
| `GET /api/admin/tutor/lessons` | Lesson monitoring |
| `GET /api/admin/analytics/*` | Analytics data |

---

## 7. External Services

### OpenAI
- **Chat Completions**: gpt-4o-mini (default)
- **Whisper**: Speech-to-text
- **TTS**: 6 voice options (alloy, echo, fable, onyx, nova, shimmer)

### Yandex Cloud
- **STT**: Russian STT with profanity filtering
- **TTS**: Multiple Russian voices (alena, etc.)

### Supabase
- PostgreSQL hosting for production

---

## 8. Development

### Local Setup
```bash
# Backend
uvicorn app.main:app --reload  # http://localhost:8000

# Frontend
cd frontend && npm run dev    # http://localhost:5173
```

### Docker Build
```bash
docker build -t ailingva .
docker run -p 8000:8000 ailingva
```

### Environment Variables
| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection |
| `YANDEX_KEY_ID` | Yandex Cloud API key ID |
| `YANDEX_KEY` | Yandex Cloud API key |
| `SECRET_KEY` | JWT signing key |

---

## 9. Code Patterns

- **Service Layer**: Business logic in `services/`
- **Router Modules**: Domain-specific route files
- **Dependency Injection**: FastAPI `Depends()` for auth/DB
- **SQLModel**: Pydantic + SQLAlchemy combined
- **Async/Await**: Full async for WebSocket & file I/O
- **JSON Fields**: Flexible storage for preferences/events

---

## 10. Statistics

| Metric | Count |
|--------|-------|
| Database Models | 30+ |
| API Route Modules | 10+ |
| Frontend Components | 13+ |
| `openai_service.py` | 353 lines |
| `brain_service.py` | 407 lines |
| `voice_ws.py` | 300+ lines |

---

*Generated: 2026-01-15*
