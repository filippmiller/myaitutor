
import asyncio
import json
import logging
import uuid
import time
import os
import base64
import struct
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlmodel import Session, select
import websockets

from app.database import get_session
from app.models import AppSettings, UserAccount, UserProfile, AuthSession, LessonSession, LessonTurn, LessonPauseEvent, DebugSettings
from app.services.tutor_service import build_tutor_system_prompt, should_run_intro_session
from app.services.language_utils import parse_language_mode_marker, strip_language_markers
from app.services.profile_service import apply_intro_profile_updates

# New improved services
from app.services.prompt_builder import build_simple_prompt, PromptBuilder
from app.services.language_enforcement import LanguageEnforcer, validate_language_mode, detect_forbidden_language
from app.services.knowledge_sync import sync_all_for_user, get_knowledge_summary
from app.services.speech_preferences import process_user_speech_preferences

from collections import deque

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory stats
LATENCY_STATS = {
    "tts": deque(maxlen=20),
    "stt": deque(maxlen=20)
}

def get_latency_stats():
    tts_avg = sum(LATENCY_STATS["tts"]) / len(LATENCY_STATS["tts"]) if LATENCY_STATS["tts"] else 0
    stt_avg = sum(LATENCY_STATS["stt"]) / len(LATENCY_STATS["stt"]) if LATENCY_STATS["stt"] else 0
    return {
        "tts_avg_ms": round(tts_avg, 2),
        "stt_avg_ms": round(stt_avg, 2),
        "samples": len(LATENCY_STATS["tts"])
    }

# Prompt logging (per lesson session)
PROMPT_LOG_DIR = os.path.join("static", "prompts")
OPENAI_LOG_DIR = os.path.join("static", "openai_logs")


def save_lesson_prompt_log(data: dict) -> None:
    """Persist a snapshot of the system + greeting prompt for a lesson.

    Stored as JSON in static/prompts/lesson_<lesson_id>_prompt.json so it can be
    inspected from the Admin panel without touching the DB schema.
    """
    try:
        os.makedirs(PROMPT_LOG_DIR, exist_ok=True)
        lesson_id = data.get("lesson_session_id") or "unknown"
        file_path = os.path.join(PROMPT_LOG_DIR, f"lesson_{lesson_id}_prompt.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to write prompt log for lesson {data.get('lesson_session_id')}: {e}")


def append_openai_log(lesson_session_id: int, entry: dict) -> None:
    """Append a single OpenAI traffic record for a lesson as JSONL.

    This is used only when debug logging is enabled, and stores a text-only
    view of the packets we exchange with OpenAI (no raw audio).
    """
    try:
        os.makedirs(OPENAI_LOG_DIR, exist_ok=True)
        from datetime import datetime as _dt

        full_entry = dict(entry)
        full_entry.setdefault("lesson_session_id", lesson_session_id)
        full_entry.setdefault("ts", _dt.utcnow().isoformat())

        file_path = os.path.join(OPENAI_LOG_DIR, f"lesson_{lesson_session_id}.jsonl")
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(full_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Failed to append OpenAI log for lesson {lesson_session_id}: {e}")


router = APIRouter()

@router.websocket("/ws/echo")
async def echo_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        pass

@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info(f"WebSocket connection accepted from {websocket.client}")
    logger.info("Voice WS Version: 2025-12-05 Realtime (gpt-realtime) + Fallback + Pause/Resume")
    
    # Manually create session
    from app.database import engine
    session = Session(engine)
    
    user: Optional[UserAccount] = None
    profile: Optional[UserProfile] = None
    api_key = None
    settings: Optional[AppSettings] = None
    lesson_session: Optional[LessonSession] = None
    is_resume: bool = False
    debug_voice_logging: bool = False
    
    try:
        # 0. Authenticate User
        session_id = websocket.cookies.get("session_id")
        if session_id:
            auth_session = session.get(AuthSession, session_id)
            from datetime import datetime
            if auth_session and not auth_session.is_revoked and auth_session.expires_at > datetime.utcnow():
                 user = session.get(UserAccount, auth_session.user_id)
        
        if not user:
            logger.warning("Unauthenticated WebSocket connection")
        else:
            profile = session.exec(select(UserProfile).where(UserProfile.user_account_id == user.id)).first()
            logger.info(f"Authenticated user: {user.email}")

        # 1. Load Settings - PREFER env var over database (env var is more current)
        settings = session.get(AppSettings, 1)
        env_api_key = os.getenv("OPENAI_API_KEY")
        db_api_key = settings.openai_api_key if settings and settings.openai_api_key else None

        # Prioritize env var (Railway sets this), fallback to database
        if env_api_key:
            api_key = env_api_key
            logger.info("Using API key from environment variable")
        elif db_api_key:
            api_key = db_api_key
            logger.info("Using API key from database")
        else:
            api_key = None

        if api_key:
            api_key = api_key.strip().strip("'").strip('"')
        
        if not api_key:
            logger.error("OpenAI API Key missing")
            await websocket.send_json({"type": "system", "level": "error", "message": "OpenAI API Key missing."})
            await websocket.close(code=1011)
            return

        # 1c. Load debug settings
        try:
            dbg = session.get(DebugSettings, 1)
            debug_voice_logging = bool(dbg and dbg.voice_logging_enabled)
        except Exception as e:
            logger.error(f"Failed to load DebugSettings: {e}")
            debug_voice_logging = False

        # 1b. Inspect query params for resume of an existing lesson session
        qs = websocket.query_params
        lesson_session_id_param = qs.get("lesson_session_id")
        resume_flag = qs.get("resume")
        if lesson_session_id_param:
            try:
                lesson_session_id_val = int(lesson_session_id_param)
                lesson_session = session.get(LessonSession, lesson_session_id_val)
                if not lesson_session:
                    logger.warning(f"LessonSession {lesson_session_id_val} not found; starting a fresh session")
                    lesson_session = None
                else:
                    # Security: ensure the session belongs to this user (if authenticated)
                    if user and lesson_session.user_account_id != user.id:
                        logger.warning(
                            f"User {user.id} attempted to resume lesson_session {lesson_session.id} not owned by them"
                        )
                        lesson_session = None
                    else:
                        is_resume = bool(resume_flag and resume_flag != "0")
                        logger.info(
                            f"Resuming existing LessonSession {lesson_session.id} (is_resume={is_resume}, status={lesson_session.status})"
                        )
            except ValueError:
                logger.warning(f"Invalid lesson_session_id query param: {lesson_session_id_param}")

        # Determine Preferences
        tts_engine_name = "openai"
        voice_id = "alloy"
        if profile:
            tts_engine_name = profile.preferred_tts_engine or "openai"
            voice_id = profile.preferred_voice_id or "alloy"
            # Legacy fallback
            if not profile.preferred_voice_id:
                try:
                    prefs = json.loads(profile.preferences)
                    legacy_voice = prefs.get("preferred_voice")
                    if legacy_voice:
                        voice_id = legacy_voice
                        if legacy_voice in ['alisa', 'alena', 'filipp', 'jane', 'madirus', 'omazh', 'zahar', 'ermil']:
                            tts_engine_name = "yandex"
                except:
                    pass

        # 2. Try Realtime Session (if OpenAI is selected)
        # Only use Realtime if engine is OpenAI. If user wants Yandex, go straight to legacy.
        use_realtime = (tts_engine_name == "openai")
        
        if use_realtime:
            try:
                logger.info("Attempting OpenAI Realtime Session with model 'gpt-realtime' (audio+text)...")
                await run_realtime_session(
                    websocket,
                    api_key,
                    voice_id,
                    profile,
                    session,
                    user=user,
                    lesson_session=lesson_session,
                    is_resume=is_resume,
                    debug_logging=debug_voice_logging,
                )
                return # If successful and finishes normally
            except Exception as e:
                logger.error(f"Realtime Session failed: {e}", exc_info=True)
                await websocket.send_json({"type": "system", "level": "warning", "message": f"Realtime connection failed: {str(e)}. Switching to standard mode."})
                # Fall through to legacy
        
        # 3. Legacy Session (Whisper/Yandex)
        logger.info("Starting Legacy Session (Whisper/Yandex)...")
        if not profile:
             logger.warning("No user profile found, using default settings for legacy session.")
             # Create a dummy/default profile if needed or handle inside run_legacy_session
             # For now, we'll let it proceed but we should be aware.
             
        await run_legacy_session(
            websocket,
            api_key,
            tts_engine_name,
            voice_id,
            profile,
            settings,
            session,
            user=user,
            lesson_session=lesson_session,
            is_resume=is_resume,
            debug_logging=debug_voice_logging,
        )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Main loop error: {e}", exc_info=True)
    finally:
        session.close()
        logger.info("Cleanup complete")


async def run_realtime_session(
    websocket: WebSocket,
    api_key: str,
    voice_id: str,
    profile: UserProfile | None,
    session: Session,
    user: UserAccount | None = None,
    lesson_session: LessonSession | None = None,
    is_resume: bool = False,
    debug_logging: bool = False,
):
    """Manage a session with the latest OpenAI Realtime API (gpt-realtime).

    A single logical lesson can be resumed multiple times; we reuse the same
    LessonSession row and track pauses separately in LessonPauseEvent.
    """
    import subprocess
    import shutil
    from datetime import datetime
    from openai import AsyncOpenAI
    
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg not found")

    def _scrub_audio_fields(obj):
        """Remove or shorten large base64/audio fields for debug logging."""
        if isinstance(obj, dict):
            new = {}
            for k, v in obj.items():
                if k in {"audio", "delta", "audio_base64"} and isinstance(v, str) and len(v) > 120:
                    new[k] = f"[base64 audio, {len(v)} chars]"
                else:
                    new[k] = _scrub_audio_fields(v)
            return new
        if isinstance(obj, list):
            return [_scrub_audio_fields(x) for x in obj]
        return obj

    async def _send_debug(direction: str, channel: str, payload: dict):
        if not debug_logging:
            return
        try:
            clean = _scrub_audio_fields(payload)
            debug_packet = {
                "type": "debug",
                "direction": direction,
                "channel": channel,
                "payload": clean,
            }
            # Send to frontend live
            await websocket.send_json(debug_packet)
            # Persist to file per-lesson
            try:
                append_openai_log(lesson_session.id, {
                    "direction": direction,
                    "channel": channel,
                    "payload": clean,
                })
            except Exception as log_err:
                logger.error(f"Failed to append_openai_log: {log_err}")
        except Exception as e:
            logger.error(f"Failed to send debug packet: {e}")

    # Ensure we have AppSettings for default model (used for summaries)
    settings: Optional[AppSettings] = session.get(AppSettings, 1)

    # Create or reuse LessonSession
    if lesson_session is None:
        lesson_session = LessonSession(
            user_account_id=profile.user_account_id if profile else (user.id if user else None),
            started_at=datetime.utcnow(),
            language_mode=None,  # Will be set by interaction
            status="active",
        )
        session.add(lesson_session)
        session.commit()
        session.refresh(lesson_session)
        logger.info(f"Created Realtime LessonSession {lesson_session.id}")
    else:
        # Mark resumed
        lesson_session.status = "active"
        session.add(lesson_session)
        # Close the latest open LessonPauseEvent for this session, if any
        try:
            last_pause = session.exec(
                select(LessonPauseEvent)
                .where(LessonPauseEvent.lesson_session_id == lesson_session.id)
                .where(LessonPauseEvent.resumed_at == None)  # type: ignore
                .order_by(LessonPauseEvent.paused_at.desc())
            ).first()
            if last_pause:
                # We do not store last_resumed_at on LessonSession to avoid schema changes;
                # use the pause event for analytics instead.
                last_pause.resumed_at = datetime.utcnow()
                session.add(last_pause)
        except Exception as e:
            logger.error(f"Failed to mark LessonPauseEvent as resumed: {e}")
        session.commit()
        logger.info(f"Reusing existing LessonSession {lesson_session.id} (resume={is_resume})")

    # Determine whether this lesson should run intro/onboarding mode
    intro_mode = should_run_intro_session(session, profile, lesson_session.id)
    logger.info(f"Intro mode for lesson {lesson_session.id}: {intro_mode}, is_resume: {is_resume}")

    # 🆕 Sync knowledge before building prompt
    if user:
        try:
            sync_all_for_user(session, user.id)
            knowledge_summary = get_knowledge_summary(session, user.id)
            logger.info(f"Knowledge synced: {knowledge_summary}")
        except Exception as e:
            logger.error(f"Knowledge sync failed: {e}", exc_info=True)

    # 🆕 Initialize language enforcer
    language_enforcer = LanguageEnforcer(mode=None)

    # Build System Prompt using NEW simplified builder (with fallback to old builder)
    try:
        system_prompt = build_simple_prompt(
            db_session=session,
            profile=profile,
            lesson_session_id=lesson_session.id,
            is_resume=is_resume,
        )
        logger.info("Using NEW simplified prompt builder")
    except Exception as e:
        logger.error(f"New prompt builder failed, falling back to old: {e}", exc_info=True)
        system_prompt = build_tutor_system_prompt(
            session,
            profile,
            lesson_session_id=lesson_session.id,
            is_resume=is_resume,
        )
    
    # Log system prompt details
    logger.info("=" * 80)
    logger.info("SYSTEM PROMPT BUILT:")
    logger.info(f"  Student Name: {profile.name if profile else 'None'}")
    logger.info(f"  Student Level: {profile.english_level if profile else 'None'}")
    logger.info(f"  Lesson Session ID: {lesson_session.id}")
    logger.info(f"  System Prompt Length: {len(system_prompt)} characters")
    logger.info(f"  System Prompt (First 500 chars):\n{system_prompt[:500]}")
    logger.info("=" * 80)

    # 🆕 Initialize Multi-Pipeline Manager with SMART BRAIN
    from app.services.lesson_pipeline_manager import LessonPipelineManager

    pipeline_manager = None
    if user:
        try:
            # Pass API key to enable smart brain (LLM-powered analysis)
            pipeline_manager = LessonPipelineManager(session, user, api_key=api_key)
            tutor_lesson = pipeline_manager.start_lesson(legacy_session_id=lesson_session.id)
            logger.info(
                f"✅ Multi-Pipeline Manager initialized - "
                f"Lesson #{tutor_lesson.lesson_number}, "
                f"First lesson: {tutor_lesson.is_first_lesson}, "
                f"Smart brain: {pipeline_manager.smart_brain is not None}"
            )
        except Exception as e:
            logger.error(f"❌ Failed to initialize pipeline manager: {e}", exc_info=True)
            # Continue without pipeline manager (graceful degradation)

    # Notify frontend about the logical lesson ID so it can resume later
    try:
        await websocket.send_json(
            {
                "type": "lesson_info",
                "lesson_session_id": lesson_session.id,
                "debug_enabled": debug_logging,
            }
        )
    except Exception as e:
        logger.error(f"Failed to send lesson_info to frontend: {e}")

    # Prepare prompt log snapshot (we'll fill greeting + STT config later)
    prompt_log_data = {
        "mode": "realtime",
        "lesson_session_id": lesson_session.id,
        "user_account_id": profile.user_account_id if profile else (user.id if user else None),
        "user_email": getattr(user, "email", None) if user else None,
        "student_name": profile.name if profile else None,
        "english_level": profile.english_level if profile else None,
        "tts_engine": "openai",
        "voice_id": voice_id,
        "stt_language": None,
        "system_prompt": system_prompt,
        "greeting_event_prompt": None,
        "created_at": datetime.utcnow().isoformat(),
    }

    # Persist the initial snapshot immediately so Lesson Prompts always has at
    # least the system prompt, even если greeting по какой-то причине не
    # сработал.
    try:
        save_lesson_prompt_log(prompt_log_data)
    except Exception as e:
        logger.error(f"Failed to write initial prompt log for lesson {lesson_session.id}: {e}")

    # 1. Connect to OpenAI Realtime (latest model alias)
    url = "wss://api.openai.com/v1/realtime?model=gpt-realtime"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    
    async with websockets.connect(url, additional_headers=headers) as openai_ws:
        logger.info("Connected to OpenAI Realtime API (model=gpt-realtime)")
        
        # 2. Configure Session
        # Use audio PCM16 24kHz in and out; enable server-side VAD.
        # Define tools for profile updates (so they're not vocalized)
        profile_update_tool = {
            "type": "function",
            "name": "update_profile",
            "description": "Save student profile information collected during the intro conversation. Call this function whenever you learn something new about the student (their name, your name, level, goals, etc). This allows silent data collection without speaking the data aloud.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tutor_name": {
                        "type": "string",
                        "description": "The name the student chose for the tutor (e.g., 'Mike', 'Kate', 'Варя')"
                    },
                    "student_name": {
                        "type": "string",
                        "description": "The student's preferred name"
                    },
                    "addressing_mode": {
                        "type": "string",
                        "enum": ["ty", "vy"],
                        "description": "How to address the student: 'ty' (informal ты) or 'vy' (formal вы)"
                    },
                    "english_level_scale_1_10": {
                        "type": "integer",
                        "description": "Student's self-assessed English level from 1 (nothing) to 10 (fluent)"
                    },
                    "goals": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Why the student needs English (work, travel, etc.)"
                    },
                    "topics_interest": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Topics the student is interested in"
                    },
                    "correction_style": {
                        "type": "string",
                        "enum": ["often", "soft", "on_request"],
                        "description": "How the student prefers to be corrected"
                    },
                    "intro_completed": {
                        "type": "boolean",
                        "description": "Set to true when the intro/onboarding is complete"
                    }
                },
                "required": []
            }
        }

        session_update = {
            "type": "session.update",
            "session": {
                # Required in latest Realtime API
                "type": "realtime",
                "model": "gpt-realtime",
                # New-style Realtime audio configuration
                "output_modalities": ["audio"],
                "instructions": system_prompt,
                # Add tools for silent profile updates (only during intro)
                "tools": [profile_update_tool] if intro_mode else [],
                "tool_choice": "auto" if intro_mode else "none",
                "audio": {
                    "input": {
                        "format": {
                            "type": "audio/pcm",
                            "rate": 24000,
                        },
                        # Let the server handle VAD based on semantics
                        "turn_detection": {
                            "type": "semantic_vad",
                        },
                    },
                    "output": {
                        "format": {
                            "type": "audio/pcm",
                            "rate": 24000,
                        },
                        "voice": voice_id if voice_id in [
                            "alloy",
                            "echo",
                            "shimmer",
                            "ash",
                            "ballad",
                            "coral",
                            "sage",
                            "verse",
                        ]
                        else "alloy",
                    },
                },
            },
        }
        await openai_ws.send(json.dumps(session_update))
        logger.info("Realtime: session.update sent to OpenAI with system prompt")
        await _send_debug("to_openai", "realtime", session_update)
        
        # Wait a moment for OpenAI to process session.update
        await asyncio.sleep(0.5)
        logger.info("Realtime: Session should be ready, sending ready signal to frontend")
        
        # Send ready signal to frontend
        await websocket.send_json(
            {
                "type": "system",
                "level": "info",
                "message": "Session ready. You can now start the lesson.",
            }
        )
        
        # 3. Audio Converters
        # Frontend (WebM) -> PCM 24k (OpenAI)
        # We need a converter that outputs 24000Hz, 1 channel, s16le
        input_converter = subprocess.Popen(
            [
                ffmpeg_path,
                "-i",
                "pipe:0",
                "-f",
                "s16le",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "24000",
                "-ac",
                "1",
                "pipe:1",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        
        # 4. Loops
        loop = asyncio.get_running_loop()
        greeting_triggered = False  # Flag to prevent multiple greeting triggers
        stt_language = "en-US"  # Logged from config message
        
        async def _generate_pause_summary() -> Optional[str]:
            """Generate a 1–2 sentence summary of the lesson so far for resume."""
            try:
                turns = session.exec(
                    select(LessonTurn)
                    .where(LessonTurn.session_id == lesson_session.id)
                    .order_by(LessonTurn.id)
                ).all()
                if not turns:
                    return None

                dialogue_lines = []
                for t in turns:
                    speaker_label = "Tutor" if t.speaker == "assistant" else "Student"
                    dialogue_lines.append(f"{speaker_label}: {t.text}")
                dialogue_text = "\n".join(dialogue_lines)

                client = AsyncOpenAI(api_key=api_key)
                model_name = (settings.default_model if settings and settings.default_model else "gpt-4o-mini")
                system_msg = (
                    "You are summarizing an English lesson between a tutor and a student. "
                    "Given the dialogue so far, write 1–2 short sentences in English that can follow "
                    "the phrase 'Before the break, ...'. Focus on what was practiced (topics, grammar, skills)."
                )
                user_msg = (
                    "Dialogue so far:\n" + dialogue_text + "\n\n" +
                    "Write 1–2 short sentences (in English) that summarize what they have done so far."
                )
                messages = [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ]
                await _send_debug("to_openai", "pause_summary", {"model": model_name, "messages": messages})
                completion = await client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=120,
                )
                summary = completion.choices[0].message.content or ""
                await _send_debug("from_openai", "pause_summary", {"summary": summary})
                return summary.strip()
            except Exception as e:
                logger.error(f"Failed to generate pause summary: {e}", exc_info=True)
                return None

        async def frontend_to_openai():
            """Read from frontend WebSocket, convert, send to OpenAI."""
            nonlocal greeting_triggered, prompt_log_data, stt_language, intro_mode
            try:
                while True:
                    message = await websocket.receive()
                    if "bytes" in message:
                        data = message["bytes"]
                        # Write to ffmpeg
                        input_converter.stdin.write(data)
                        input_converter.stdin.flush()
                    elif "text" in message:
                        # Handle control messages
                        try:
                            logger.info(f"Realtime: Received text message: {message['text']}")
                            data = json.loads(message["text"])
                            
                            # Handle config message
                            if data.get("type") == "config":
                                stt_language = data.get("stt_language", "en-US")
                                prompt_log_data["stt_language"] = stt_language
                                logger.info(f"Realtime: Config received - STT Language: {stt_language}")
                                # In Realtime mode, OpenAI handles STT internally, but we log it for reference
                                await _send_debug("from_frontend", "config", data)
                            
                            elif data.get("type") == "system_event" and data.get("event") == "lesson_started":
                                if greeting_triggered:
                                    logger.warning("Realtime: lesson_started received again, but greeting already sent - ignoring")
                                    continue
                                
                                greeting_triggered = True
                                logger.info("Realtime: Received lesson_started. Triggering greeting...")
                                
                                try:
                                    user_name = profile.name if profile and profile.name else "Student"

                                    if intro_mode and is_resume:
                                        # 🆕 Resuming an intro lesson that wasn't completed
                                        # Get the pause summary to provide context
                                        pause_summary = None
                                        try:
                                            last_pause = session.exec(
                                                select(LessonPauseEvent)
                                                .where(LessonPauseEvent.lesson_session_id == lesson_session.id)
                                                .order_by(LessonPauseEvent.paused_at.desc())
                                                .limit(1)
                                            ).first()
                                            if last_pause and last_pause.summary_text:
                                                pause_summary = last_pause.summary_text
                                        except Exception:
                                            pass

                                        context_hint = f" Before the break: {pause_summary}" if pause_summary else ""
                                        greeting_text = (
                                            f"System Event: RESUMING Onboarding.{context_hint} "
                                            f"The student ({user_name}) paused during the intro and is now back. "
                                            "Welcome them back warmly and CONTINUE where you left off. "
                                            "Do NOT restart the onboarding from the beginning. "
                                            "Check what info you still need (name, level, goals) and ask about that. "
                                            "Use the update_profile function to save any new information."
                                        )
                                    elif intro_mode:
                                        # First-ever lesson: trigger dedicated onboarding flow
                                        greeting_text = (
                                            "System Event: First-Time Onboarding. This is the student's very first "
                                            "lesson with you. Run the onboarding flow described in your system "
                                            "instructions: greet them warmly, explain that you are an AI English "
                                            "tutor, then follow the steps to choose your name, their preferred "
                                            "name, age (optional), ты/вы, style, goals, interests, languages, "
                                            "correction style and self-assessed level. "
                                            "Use the update_profile function to save each piece of info SILENTLY."
                                        )
                                    else:
                                        # System prompt already includes Universal Greeting Protocol
                                        # Trigger first interaction - OpenAI will follow the system prompt automatically
                                        greeting_text = (
                                            "System Event: Lesson Starting Now. This is the FIRST interaction with the "
                                            f"student. The student's name is {user_name}. Follow the Universal Greeting "
                                            "Protocol strictly: greet them warmly using their name, mention any last "
                                            "session summary if available, and start an immediate activity without "
                                            "asking meta-questions."
                                        )
                                    
                                    # Update prompt log with the concrete greeting event prompt
                                    prompt_log_data["greeting_event_prompt"] = greeting_text
                                    save_lesson_prompt_log(prompt_log_data)
                                    
                                    greeting_trigger = {
                                        "type": "conversation.item.create",
                                        "item": {
                                            "type": "message",
                                            "role": "user",
                                            "content": [{"type": "input_text", "text": greeting_text}],
                                        },
                                    }
                                    logger.info(
                                        "Realtime: Sending greeting trigger message (length: %d chars)",
                                        len(greeting_text),
                                    )
                                    await openai_ws.send(json.dumps(greeting_trigger))
                                    await _send_debug("to_openai", "realtime_greeting", greeting_trigger)
                                    
                                    # Immediately request a response based on the updated conversation
                                    response_request = {
                                        "type": "response.create",
                                        "response": {
                                            # Session is already configured for audio output; no need for modalities here.
                                            "instructions": (
                                                f"Greet the user {user_name} warmly and start the lesson immediately. "
                                                "Do not ask if they are ready."
                                            ),
                                        },
                                    }
                                    logger.info("Realtime: Requesting greeting response creation...")
                                    await openai_ws.send(json.dumps(response_request))
                                    logger.info("Realtime: Greeting response request sent")
                                    await _send_debug("to_openai", "realtime_greeting", response_request)
                                except Exception as greeting_error:
                                    logger.error(f"Realtime: Failed to trigger greeting: {greeting_error}", exc_info=True)
                                    await websocket.send_json({
                                        "type": "system",
                                        "level": "warning",
                                        "message": f"Failed to trigger greeting: {str(greeting_error)}. The lesson will continue, but you may need to speak first."
                                    })

                            elif data.get("type") == "system_event" and data.get("event") == "lesson_paused":
                                # Pause the lesson: generate a short summary, store it, and close connections.
                                logger.info("Realtime: Received lesson_paused. Generating summary and marking session paused...")
                                from datetime import datetime as _dt
                                try:
                                    summary = await _generate_pause_summary()
                                    now = _dt.utcnow()

                                    # Update LessonSession status only (no new columns)
                                    lesson_session.status = "paused"
                                    session.add(lesson_session)

                                    # Create LessonPauseEvent
                                    pause_event = LessonPauseEvent(
                                        lesson_session_id=lesson_session.id,
                                        paused_at=now,
                                        summary_text=summary,
                                    )
                                    session.add(pause_event)
                                    session.commit()

                                    payload = {
                                        "type": "system",
                                        "level": "info",
                                        "message": "Lesson paused.",
                                    }
                                    if summary:
                                        payload["resume_hint"] = summary
                                    await websocket.send_json(payload)
                                except Exception as pause_error:
                                    logger.error(f"Realtime: Failed to handle lesson_paused: {pause_error}", exc_info=True)
                                    try:
                                        await websocket.send_json({
                                            "type": "system",
                                            "level": "error",
                                            "message": "Failed to pause lesson cleanly. You may need to restart.",
                                        })
                                    except Exception:
                                        pass
                                finally:
                                    # Close both OpenAI and frontend websockets to fully pause billing/streaming.
                                    try:
                                        await openai_ws.close()
                                    except Exception:
                                        pass
                                    try:
                                        await websocket.close(code=1000, reason="lesson_paused")
                                    except Exception:
                                        pass
                                    # Break receive loop
                                    return
                        except Exception as e:
                            logger.error(f"Realtime: Error handling text message: {e}")
            except WebSocketDisconnect:
                logger.info("Realtime: Frontend disconnected (WebSocketDisconnect)")
            except RuntimeError as e:
                if "disconnect message" in str(e):
                    logger.info("Realtime: Frontend disconnected (RuntimeError)")
                else:
                    logger.error(f"Frontend->OpenAI RuntimeError: {e}")
            except Exception as e:
                logger.error(f"Frontend->OpenAI Error: {e}")
            except Exception as e:
                logger.error(f"Frontend->OpenAI Error: {e}")
            finally:
                input_converter.stdin.close()

        async def converter_reader():
            """Reads converted audio from ffmpeg stdout and sends to OpenAI."""
            try:
                while True:
                    # Read 24k PCM chunks (e.g. 100ms = 2400 * 2 bytes = 4800)
                    chunk = await loop.run_in_executor(None, input_converter.stdout.read, 4800)
                    if not chunk:
                        break
                    
                    # Send to OpenAI
                    event = {
                        "type": "input_audio_buffer.append",
                        "audio": base64.b64encode(chunk).decode("utf-8")
                    }
                    await openai_ws.send(json.dumps(event))
            except Exception as e:
                logger.error(f"Converter Reader Error: {e}")

        async def openai_to_frontend():
            """Read from OpenAI, forward text/audio to frontend."""
            audio_delta_count = 0
            try:
                async for message in openai_ws:
                    event = json.loads(message)
                    event_type = event.get("type")
                    
                    await _send_debug("from_openai", "realtime", event)
                    
                    # Log ALL events for debugging
                    if event_type in ("response.audio.delta", "response.output_audio.delta"):
                        audio_delta_count += 1
                        if audio_delta_count % 10 == 0:  # Log every 10th audio delta
                            logger.info(f"Realtime: Received {audio_delta_count} audio deltas so far...")
                    else:
                        logger.info(f"Realtime: OpenAI event received - type: {event_type}")
                    
                    if event_type in ("response.audio.delta", "response.output_audio.delta"):
                        # Received Audio Delta (PCM 24k Base64)
                        b64_audio = event.get("delta")
                        if b64_audio:
                            pcm_data = base64.b64decode(b64_audio)
                            # Wrap in WAV (24k) and send
                            wav_data = add_wav_header(pcm_data, sample_rate=24000)
                            await websocket.send_bytes(wav_data)
                            logger.debug(f"Realtime: Audio delta sent to frontend ({len(wav_data)} bytes)")
                        else:
                            logger.warning("Realtime: audio delta received but delta is empty")
                            
                    elif event_type in (
                        "response.audio_transcript.delta",
                        "response.output_audio_transcript.delta",
                    ):
                        # Received Text Delta
                        delta = event.get("delta")
                        if delta:
                            logger.info(f"Realtime: Audio transcript delta received: '{delta[:50]}...'")
                            await websocket.send_json({"type": "transcript", "role": "assistant", "text": delta})
                        else:
                            logger.warning("Realtime: audio transcript delta received but delta is empty")
                            
                    elif event_type == "conversation.item.input_audio_transcription.completed":
                        # User transcript final
                        transcript = event.get("transcript")
                        if transcript:
                            await websocket.send_json({"type": "transcript", "role": "user", "text": transcript})
                            # Save User Turn (legacy)
                            turn = LessonTurn(
                                session_id=lesson_session.id,
                                speaker="user",
                                text=transcript
                            )
                            session.add(turn)
                            session.commit()
                            
                            # 🆕 Save to new pipeline
                            if pipeline_manager:
                                try:
                                    pipeline_manager.save_turn(
                                        user_text=transcript,
                                        tutor_text=None
                                    )
                                except Exception as pm_err:
                                    logger.error(f"Pipeline manager failed to save user turn: {pm_err}")

                            # 🆕 Detect speech preferences (e.g., "speak slowly")
                            if user:
                                try:
                                    new_rule = process_user_speech_preferences(session, user.id, transcript)
                                    if new_rule:
                                        logger.info(f"🎯 Created speech preference rule: {new_rule.title}")
                                        # Inject the rule into active session immediately
                                        # This ensures the tutor applies it RIGHT NOW, not just next lesson
                                        rule_injection = (
                                            "\n\n🚨 NEW STUDENT PREFERENCE (apply immediately):\n"
                                            f"{new_rule.description}\n"
                                            "Apply this to ALL your responses from now on!"
                                        )
                                        inject_event = {
                                            "type": "conversation.item.create",
                                            "item": {
                                                "type": "message",
                                                "role": "system",
                                                "content": [{"type": "input_text", "text": rule_injection}],
                                            },
                                        }
                                        await openai_ws.send(json.dumps(inject_event))
                                        logger.info("🎯 Injected speech preference into active session")
                                except Exception as pref_err:
                                    logger.error(f"Failed to process speech preferences: {pref_err}")

                    elif event_type == "session.updated":
                        # Session update confirmed by OpenAI
                        logger.info("Realtime: Session updated confirmed by OpenAI - system prompt is now active")

                    elif event_type == "input_audio_buffer.speech_started":
                        # 🆕 VAD detected user started speaking
                        logger.info("Realtime: VAD - User started speaking")

                    elif event_type == "input_audio_buffer.speech_stopped":
                        # 🆕 VAD detected user stopped speaking
                        logger.info("Realtime: VAD - User stopped speaking")

                    elif event_type == "input_audio_buffer.committed":
                        # 🆕 Audio buffer was committed for processing
                        logger.debug("Realtime: Audio buffer committed for processing")
                    
                    elif event_type == "conversation.item.created":
                        # Conversation item created (legacy handler kept for compatibility).
                        item = event.get("item", {})
                        item_id = item.get("id")
                        item_type = item.get("type")
                        logger.info(f"Realtime: Conversation item created (ID: {item_id}, Type: {item_type})")
                    
                    elif event_type == "response.created":
                        # Response started - tutor is about to speak
                        response = event.get("response", {})
                        response_id = response.get("id")
                        logger.info(f"Realtime: Response created (ID: {response_id})")
                        logger.info(f"Realtime: Response created details: {json.dumps(response, default=str)}")

                        # 🆕 Clear input buffer when tutor starts speaking to prevent echo
                        try:
                            clear_buffer_event = {"type": "input_audio_buffer.clear"}
                            await openai_ws.send(json.dumps(clear_buffer_event))
                            logger.debug("Realtime: Cleared input audio buffer on response.created")
                        except Exception as clear_err:
                            logger.warning(f"Failed to clear input audio buffer: {clear_err}")
                        
                    elif event_type == "response.done":
                        # Response completed
                        response = event.get("response", {})
                        response_id = response.get("id")
                        status = response.get("status")
                        status_details = response.get("status_details")
                        logger.info(f"Realtime: Response done (ID: {response_id}, Status: {status})")
                        if status != "completed":
                            logger.error(f"Realtime: Response failed/cancelled details: {json.dumps(response, default=str)}")
                        else:
                            logger.info(f"Realtime: Response usage: {json.dumps(response.get('usage'), default=str)}")

                        # 🆕 CRITICAL: Clear input audio buffer after response to prevent accumulation
                        # This fixes voice stuttering during long lessons
                        try:
                            clear_buffer_event = {"type": "input_audio_buffer.clear"}
                            await openai_ws.send(json.dumps(clear_buffer_event))
                            logger.debug("Realtime: Cleared input audio buffer after response.done")
                        except Exception as clear_err:
                            logger.warning(f"Failed to clear input audio buffer: {clear_err}")
                        
                    elif event_type == "response.output_item.added":
                        # Output item added (for tracking)
                        item = event.get("item", {})
                        item_id = item.get("id")
                        item_type = item.get("type")
                        logger.info(f"Realtime: Output item added (ID: {item_id}, Type: {item_type})")
                        logger.info(f"Realtime: Output item structure: {json.dumps(item, default=str)[:500]}")
                        
                        # Check if transcript is in the added item
                        content = item.get("content", [])
                        for part in content:
                            if "transcript" in part:
                                logger.info(f"Realtime: Found transcript in added item: {part.get('transcript', '')[:100]}")
                            if "text" in part:
                                logger.info(f"Realtime: Found text in added item: {part.get('text', '')[:100]}")
                    
                    elif event_type == "response.output_item.done":
                        # Item done, extract transcript and save it
                        logger.info(f"Realtime: response.output_item.done received, extracting transcript...")
                        item = event.get("item", {})
                        content = item.get("content", [])
                        transcript = None
                        
                        logger.info(f"Realtime: Item content structure: {json.dumps(item, default=str)[:500]}")
                        
                        if content:
                            for part in content:
                                logger.info(f"Realtime: Processing content part: type={part.get('type')}, keys={list(part.keys())}")
                                if part.get("type") == "audio" and "transcript" in part:
                                    transcript = part["transcript"]
                                    logger.info(f"Realtime: Found transcript in audio part: '{transcript[:100]}...'")
                                    break
                                elif part.get("type") == "text" and "text" in part:
                                    transcript = part["text"]
                                    logger.info(f"Realtime: Found transcript in text part: '{transcript[:100]}...'")
                                    break
                        else:
                            logger.warning(f"Realtime: response.output_item.done has no content array")
                            
                        if not transcript:
                            logger.warning(f"Realtime: response.output_item.done - no transcript found in item structure")
                        
                        if transcript:
                            # 🆕 LANGUAGE VALIDATION - Check for forbidden languages
                            forbidden_lang = detect_forbidden_language(transcript)
                            if forbidden_lang:
                                logger.error(f"🚨 LANGUAGE VIOLATION: Response contains {forbidden_lang}!")
                                logger.error(f"Violating text: {transcript[:200]}")
                                # Log to debug channel
                                await websocket.send_json({
                                    "type": "debug",
                                    "level": "warning",
                                    "message": f"Language violation detected: {forbidden_lang}. Response should be English/Russian only."
                                })

                            # Validate against current mode
                            is_valid, reason, action = validate_language_mode(
                                transcript,
                                lesson_session.language_mode
                            )
                            if not is_valid:
                                logger.warning(f"Language mode violation: {reason}")

                            # Always save Assistant Turn (greeting, normal responses, etc.) (legacy)
                            turn = LessonTurn(
                                session_id=lesson_session.id,
                                speaker="assistant",
                                text=transcript
                            )
                            session.add(turn)
                            session.commit()
                            logger.info(f"Realtime: Saved assistant transcript (length: {len(transcript)})")
                            
                            # 🆕 Save to new pipeline
                            if pipeline_manager:
                                try:
                                    pipeline_manager.save_turn(
                                        user_text=None,
                                        tutor_text=transcript
                                    )
                                except Exception as pm_err:
                                    logger.error(f"Pipeline manager failed to save assistant turn: {pm_err}")
                            
                            # Apply onboarding profile updates, if any
                            if profile is not None:
                                try:
                                    apply_intro_profile_updates(session, profile, transcript)
                                except Exception as e:
                                    logger.error(f"Failed to apply intro profile updates: {e}", exc_info=True)
                            
                            # Check for language mode markers (separate from saving)
                            marker = parse_language_mode_marker(transcript)
                            if marker:
                                mode, level_change = marker
                                if mode:
                                    lesson_session.language_mode = mode
                                    lesson_session.language_chosen_at = datetime.utcnow()
                                    if mode == "MIXED":
                                        lesson_session.language_level = 1
                                    session.add(lesson_session)
                                    session.commit()
                                    # 🆕 Update language enforcer
                                    language_enforcer.set_mode(mode)
                                    logger.info(f"Realtime: Language mode set to {mode}")
                                elif level_change == "LEVEL_UP":
                                    if lesson_session.language_level:
                                        lesson_session.language_level = min(lesson_session.language_level + 1, 5)
                                        session.add(lesson_session)
                                        session.commit()
                                        logger.info(f"Realtime: Language level increased to {lesson_session.language_level}")

                    elif event_type == "response.function_call_arguments.done":
                        # 🆕 Handle function calls (e.g., update_profile during intro)
                        call_id = event.get("call_id")
                        func_name = event.get("name")
                        arguments = event.get("arguments", "{}")

                        logger.info(f"Realtime: Function call received - {func_name}({arguments[:100]}...)")

                        if func_name == "update_profile" and profile is not None:
                            try:
                                args = json.loads(arguments)
                                # Build a fake transcript line for apply_intro_profile_updates
                                # This reuses existing logic without duplication
                                for field, value in args.items():
                                    fake_line = f"[PROFILE_UPDATE] {json.dumps({field: value})}"
                                    apply_intro_profile_updates(session, profile, fake_line)
                                logger.info(f"Realtime: Profile updated via function call: {list(args.keys())}")

                                # Send function result back to OpenAI
                                func_result = {
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "function_call_output",
                                        "call_id": call_id,
                                        "output": json.dumps({"status": "success", "updated_fields": list(args.keys())})
                                    }
                                }
                                await openai_ws.send(json.dumps(func_result))
                                logger.info("Realtime: Sent function result back to OpenAI")

                                # Request continuation of the conversation
                                continue_request = {
                                    "type": "response.create",
                                    "response": {}
                                }
                                await openai_ws.send(json.dumps(continue_request))

                            except Exception as func_err:
                                logger.error(f"Failed to process function call: {func_err}", exc_info=True)
                                # Send error result
                                error_result = {
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "function_call_output",
                                        "call_id": call_id,
                                        "output": json.dumps({"status": "error", "message": str(func_err)})
                                    }
                                }
                                await openai_ws.send(json.dumps(error_result))

                    elif event_type == "error":
                        # Treat Realtime errors as fatal so we can fall back cleanly.
                        logger.error(f"OpenAI Realtime Error event: {json.dumps(event, default=str)[:500]}")
                        # Surface a readable message to the frontend for debugging.
                        error_obj = event.get("error") or {}
                        message = error_obj.get("message") or str(event)
                        try:
                            await websocket.send_json(
                                {
                                    "type": "system",
                                    "level": "error",
                                    "message": f"OpenAI Realtime error: {message}",
                                }
                            )
                        except Exception:
                            # If WS to frontend is already closing, just continue shutdown.
                            pass
                        # Raise to trigger fallback to legacy mode in the caller.
                        raise RuntimeError(f"OpenAI Realtime error: {message}")
                    else:
                        # Log unhandled events for debugging
                        logger.warning(
                            "Realtime: Unhandled event type: %s, full event: %s",
                            event_type,
                            json.dumps(event, default=str)[:500],
                        )
                        
            except Exception as e:
                logger.error(f"OpenAI->Frontend Error: {e}")
                raise e  # Trigger fallback

        # Start tasks
        task_frontend_to_openai = asyncio.create_task(frontend_to_openai())
        task_converter_reader = asyncio.create_task(converter_reader())
        task_openai_to_frontend = asyncio.create_task(openai_to_frontend())
        
        tasks = [
            ("frontend_to_openai", task_frontend_to_openai),
            ("converter_reader", task_converter_reader),
            ("openai_to_frontend", task_openai_to_frontend)
        ]
        task_list = [t[1] for t in tasks]
        
        # 5. Run Tasks with Graceful Shutdown
        # Wait for tasks and handle errors gracefully
        try:
            # Wait for any task to complete or fail
            done, pending = await asyncio.wait(
                task_list,
                return_when=asyncio.FIRST_COMPLETED,
                timeout=None
            )
            
            # Find which task completed and check for errors
            completed_task = done.pop() if done else None
            task_name = "unknown"
            for name, task in tasks:
                if task == completed_task:
                    task_name = name
                    break
            
            # Check if task completed normally or with error
            if completed_task:
                try:
                    completed_task.result()  # This will raise if task had exception
                    logger.info(f"Realtime: Task '{task_name}' completed normally. Initiating graceful shutdown...")
                except Exception as task_error:
                    logger.error(f"Realtime: Task '{task_name}' failed with error: {task_error}", exc_info=True)
                    # On error, we still do graceful shutdown but log the error
            else:
                logger.info("Realtime: No tasks completed (unexpected condition).")
            
            # Graceful shutdown: give other tasks a moment to finish current operations
            logger.info(f"Realtime: Graceful shutdown - cancelling {len(pending)} remaining tasks...")
            for task in pending:
                task.cancel()
            
            # Wait briefly for tasks to handle cancellation gracefully
            if pending:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*pending, return_exceptions=True),
                        timeout=2.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Realtime: Some tasks didn't cancel within timeout, forcing termination")
                    
        except Exception as e:
            logger.error(f"Realtime: Unexpected error in task management: {e}", exc_info=True)
            # Emergency shutdown
            for _, task in tasks:
                if not task.done():
                    task.cancel()
        finally:
            # Ensure input converter is closed
            try:
                if input_converter.stdin and not input_converter.stdin.closed:
                    input_converter.stdin.close()
                if input_converter.stdout and not input_converter.stdout.closed:
                    input_converter.stdout.close()
                if input_converter.poll() is None:  # Still running
                    input_converter.terminate()
                    try:
                        input_converter.wait(timeout=1.0)
                    except:
                        input_converter.kill()
            except Exception as cleanup_error:
                logger.error(f"Realtime: Error during converter cleanup: {cleanup_error}")


async def run_legacy_session(
    websocket: WebSocket,
    api_key: str,
    tts_engine_name: str,
    voice_id: str,
    profile: UserProfile | None,
    settings: AppSettings,
    session: Session,
    user: UserAccount | None = None,
    lesson_session: LessonSession | None = None,
    is_resume: bool = False,
    debug_logging: bool = False,
):
    """Legacy implementation using VAD + Whisper + TTS (OpenAI/Yandex)."""
    # Initialize Services
    def _scrub_audio_fields_legacy(obj):
        if isinstance(obj, dict):
            new = {}
            for k, v in obj.items():
                if k in {"audio", "delta", "audio_base64"} and isinstance(v, str) and len(v) > 120:
                    new[k] = f"[base64 audio, {len(v)} chars]"
                else:
                    new[k] = _scrub_audio_fields_legacy(v)
            return new
        if isinstance(obj, list):
            return [_scrub_audio_fields_legacy(x) for x in obj]
        return obj

    async def _send_debug(direction: str, channel: str, payload: dict):
        if not debug_logging:
            return
        try:
            clean = _scrub_audio_fields_legacy(payload)
            debug_packet = {
                "type": "debug",
                "direction": direction,
                "channel": channel,
                "payload": clean,
            }
            await websocket.send_json(debug_packet)
            try:
                append_openai_log(lesson_session.id, {
                    "direction": direction,
                    "channel": channel,
                    "payload": clean,
                })
            except Exception as log_err:
                logger.error(f"Legacy: Failed to append_openai_log: {log_err}")
        except Exception as e:
            logger.error(f"Legacy: failed to send debug packet: {e}")

    try:
        from app.services.yandex_service import YandexService, AudioConverter
        from app.services.voice_engine import get_voice_engine
        yandex_service = YandexService() # Still used for fallback TTS potentially
        converter = AudioConverter() # ffmpeg 48k
        tts_engine = get_voice_engine(tts_engine_name, api_key=api_key)
    except Exception as e:
        logger.error(f"Legacy init failed: {e}")
        await websocket.close(code=1011)
        return

    # Create or reuse LessonSession
    from datetime import datetime
    if lesson_session is None:
        lesson_session = LessonSession(
            user_account_id=profile.user_account_id if profile else (user.id if user else None),
            started_at=datetime.utcnow(),
            language_mode=None,  # Will be set by interaction
            status="active",
        )
        session.add(lesson_session)
        session.commit()
        session.refresh(lesson_session)
        logger.info(f"Created LessonSession {lesson_session.id}")
    else:
        lesson_session.status = "active"
        session.add(lesson_session)
        # Close last open LessonPauseEvent if any
        try:
            last_pause = session.exec(
                select(LessonPauseEvent)
                .where(LessonPauseEvent.lesson_session_id == lesson_session.id)
                .where(LessonPauseEvent.resumed_at == None)  # type: ignore
                .order_by(LessonPauseEvent.paused_at.desc())
            ).first()
            if last_pause:
                last_pause.resumed_at = datetime.utcnow()
                session.add(last_pause)
        except Exception as e:
            logger.error(f"Legacy: Failed to mark LessonPauseEvent as resumed: {e}")
        session.commit()
        logger.info(f"Legacy: Reusing LessonSession {lesson_session.id} (resume={is_resume})")

    # 🆕 Sync knowledge before building prompt (same as realtime)
    if user:
        try:
            sync_all_for_user(session, user.id)
            logger.info(f"Legacy: Knowledge synced for user {user.id}")
        except Exception as e:
            logger.error(f"Legacy: Knowledge sync failed: {e}", exc_info=True)

    # 🆕 Initialize language enforcer
    legacy_language_enforcer = LanguageEnforcer(mode=None)

    # Build System Prompt using NEW simplified builder (with fallback)
    try:
        system_prompt = build_simple_prompt(
            db_session=session,
            profile=profile,
            lesson_session_id=lesson_session.id,
            is_resume=is_resume,
        )
        logger.info("Legacy: Using NEW simplified prompt builder")
    except Exception as e:
        logger.error(f"Legacy: New prompt builder failed, falling back: {e}", exc_info=True)
        system_prompt = build_tutor_system_prompt(
            session,
            profile,
            lesson_session_id=lesson_session.id,
            is_resume=is_resume,
        )

    # Prepare prompt log snapshot (filled with greeting + STT later)
    prompt_log_data = {
        "mode": "legacy",
        "lesson_session_id": lesson_session.id,
        "user_account_id": profile.user_account_id if profile else (user.id if user else None),
        "user_email": getattr(user, "email", None) if user else None,
        "student_name": profile.name if profile else None,
        "english_level": profile.english_level if profile else None,
        "tts_engine": tts_engine_name,
        "voice_id": voice_id,
        "stt_language": None,
        "system_prompt": system_prompt,
        "greeting_event_prompt": None,
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        save_lesson_prompt_log(prompt_log_data)
    except Exception as e:
        logger.error(f"Legacy: failed to write initial prompt log for lesson {lesson_session.id}: {e}")

    # 🆕 Initialize Multi-Pipeline Manager with SMART BRAIN (same as realtime)
    from app.services.lesson_pipeline_manager import LessonPipelineManager

    pipeline_manager = None
    if user:
        try:
            pipeline_manager = LessonPipelineManager(session, user, api_key=api_key)
            tutor_lesson = pipeline_manager.start_lesson(legacy_session_id=lesson_session.id)
            logger.info(
                f"✅ Legacy: Multi-Pipeline Manager initialized - "
                f"Lesson #{tutor_lesson.lesson_number}, "
                f"First lesson: {tutor_lesson.is_first_lesson}, "
                f"Smart brain: {pipeline_manager.smart_brain is not None}"
            )
        except Exception as e:
            logger.error(f"❌ Legacy: Failed to initialize pipeline manager: {e}", exc_info=True)

    # State
    conversation_history = [
        {"role": "system", "content": system_prompt}
    ]
    
    # VAD State
    audio_buffer = bytearray()
    is_speaking = False
    silence_start_time = 0
    SILENCE_THRESHOLD = 500
    SILENCE_DURATION = 1.0
    MIN_AUDIO_LENGTH = 0.5
    
    import audioop
    loop = asyncio.get_running_loop()

    # Helpers
    async def synthesize_and_send(text: str):
        start_time = time.time()
        first_chunk_sent = False
        try:
            # Use streaming synthesis
            async for chunk in tts_engine.synthesize_stream(text, voice_id=voice_id):
                if chunk:
                    await websocket.send_bytes(chunk)
                    if not first_chunk_sent:
                        latency = (time.time() - start_time) * 1000
                        logger.info(f"TTS Latency ({tts_engine_name}): {latency:.2f}ms")
                        LATENCY_STATS["tts"].append(latency)
                        first_chunk_sent = True
        except Exception as e:
            logger.error(f"TTS Error: {e}")

    async def process_user_text(text: str):
        stt_end_time = time.time()
        # Estimate STT latency (approximate, since we don't have exact start of speech here easily without more state)
        # But we can log that we got text.
        logger.info(f"STT Text: {text}")
        
        await websocket.send_json({"type": "transcript", "role": "user", "text": text})
        conversation_history.append({"role": "user", "content": text})
        
        # Save User Turn (legacy)
        turn = LessonTurn(
            session_id=lesson_session.id,
            speaker="user",
            text=text
        )
        session.add(turn)
        session.commit()
        
        # 🆕 Save to new pipeline
        if pipeline_manager:
            try:
                pipeline_manager.save_turn(user_text=text, tutor_text=None)
            except Exception as pm_err:
                logger.error(f"Legacy: Pipeline manager failed to save user turn: {pm_err}")
        
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            
            llm_start_time = time.time()
            stream = await client.chat.completions.create(
                model=settings.default_model,
                messages=conversation_history,
                stream=True
            )
            
            full_resp = ""
            curr_sent = ""
            import re
            
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    full_resp += content
                    curr_sent += content
                    # Simple sentence splitting
                    if re.search(r'[.!?]\s', curr_sent):
                        # Strip markers before sending to user
                        clean_sent = strip_language_markers(curr_sent)
                        if clean_sent.strip():
                            await websocket.send_json({"type": "transcript", "role": "assistant", "text": clean_sent})
                            await synthesize_and_send(clean_sent)
                        curr_sent = ""
            
            # Handle remaining text
            if curr_sent:
                clean_sent = strip_language_markers(curr_sent)
                if clean_sent.strip():
                    await websocket.send_json({"type": "transcript", "role": "assistant", "text": clean_sent})
                    await synthesize_and_send(clean_sent)
                
            conversation_history.append({"role": "assistant", "content": full_resp})
            
            # Save Assistant Turn (legacy)
            turn = LessonTurn(
                session_id=lesson_session.id,
                speaker="assistant",
                text=full_resp
            )
            session.add(turn)
            session.commit()
            
            # 🆕 Save to new pipeline
            if pipeline_manager:
                try:
                    pipeline_manager.save_turn(user_text=None, tutor_text=full_resp)
                except Exception as pm_err:
                    logger.error(f"Legacy: Pipeline manager failed to save assistant turn: {pm_err}")
            
            # Check for language mode markers
            marker = parse_language_mode_marker(full_resp)
            if marker:
                mode, level_change = marker
                if mode:
                    lesson_session.language_mode = mode
                    lesson_session.language_chosen_at = datetime.utcnow()
                    if mode == "MIXED":
                        lesson_session.language_level = 1
                    session.add(lesson_session)
                    session.commit()
                    logger.info(f"Language mode set to {mode} for session {lesson_session.id}")
                elif level_change == "LEVEL_UP":
                    if lesson_session.language_level:
                        lesson_session.language_level = min(lesson_session.language_level + 1, 5)
                        session.add(lesson_session)
                        session.commit()
                        logger.info(f"Language level increased to {lesson_session.language_level}")
            
        except Exception as e:
            logger.error(f"LLM Error: {e}")

    # Loops
    async def _generate_pause_summary_legacy() -> Optional[str]:
        """Generate a 1–2 sentence summary for legacy session."""
        try:
            turns = session.exec(
                select(LessonTurn)
                .where(LessonTurn.session_id == lesson_session.id)
                .order_by(LessonTurn.id)
            ).all()
            if not turns:
                return None

            dialogue_lines = []
            for t in turns:
                speaker_label = "Tutor" if t.speaker == "assistant" else "Student"
                dialogue_lines.append(f"{speaker_label}: {t.text}")
            dialogue_text = "\n".join(dialogue_lines)

            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            model_name = settings.default_model
            system_msg = (
                "You are summarizing an English lesson between a tutor and a student. "
                "Given the dialogue so far, write 1–2 short sentences in English that can follow "
                "the phrase 'Before the break, ...'. Focus on what was practiced (topics, grammar, skills)."
            )
            user_msg = (
                "Dialogue so far:\n" + dialogue_text + "\n\n" +
                "Write 1–2 short sentences (in English) that summarize what they have done so far."
            )
            completion = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=120,
            )
            summary = completion.choices[0].message.content or ""
            return summary.strip()
        except Exception as e:
            logger.error(f"Legacy: Failed to generate pause summary: {e}", exc_info=True)
            return None

    async def receive_loop():
        try:
            while True:
                message = await websocket.receive()
                if "bytes" in message:
                    data = message["bytes"]
                    await loop.run_in_executor(None, converter.write, data)
                elif "text" in message:
                    try:
                        logger.info(f"Legacy: Received text message: {message['text']}")
                        data = json.loads(message["text"])
                        
                        # Handle config message
                        if data.get("type") == "config":
                            stt_language = data.get("stt_language", "en-US")
                            prompt_log_data["stt_language"] = stt_language
                            logger.info(f"Legacy: Config received - STT Language: {stt_language}")
                            # Store in session state if needed (currently not used in Legacy VAD+Whisper mode)
                        
                        elif data.get("type") == "system_event" and data.get("event") == "lesson_started":
                            logger.info("Legacy: Received lesson_started. Generating greeting...")
                            
                            try:
                                # Generate dynamic greeting using LLM
                                from openai import AsyncOpenAI
                                client = AsyncOpenAI(api_key=api_key)
                                
                                user_name = profile.name if profile and profile.name else "Student"
                                greeting_system_message = (
                                    f"System Event: Lesson Started. The student's name is {user_name}. "
                                    "Generate a greeting that follows the Universal Greeting Protocol. Brief, warm, "
                                    "NO meta-questions. Start an activity immediately."
                                )
                                greeting_prompt = conversation_history + [
                                    {"role": "system", "content": greeting_system_message}
                                ]
                                
                                # Update prompt log with the concrete greeting event prompt
                                prompt_log_data["greeting_event_prompt"] = greeting_system_message
                                save_lesson_prompt_log(prompt_log_data)
                                
                                try:
                                    completion = await client.chat.completions.create(
                                        model=settings.default_model,
                                        messages=greeting_prompt,
                                        max_tokens=150
                                    )
                                    greeting_text = completion.choices[0].message.content
                                    logger.info(f"Legacy: Greeting generated successfully (length: {len(greeting_text)})")
                                except Exception as e:
                                    logger.error(f"Legacy Greeting Generation Error: {e}", exc_info=True)
                                    greeting_text = "Hello! I am your AI tutor. Let's start our lesson."
                                    await websocket.send_json({
                                        "type": "system",
                                        "level": "warning",
                                        "message": "Greeting generation failed, using default greeting."
                                    })

                                # Send text
                                await websocket.send_json({"type": "transcript", "role": "assistant", "text": greeting_text})
                                conversation_history.append({"role": "assistant", "content": greeting_text})
                                
                                # Save Assistant Turn (Greeting)
                                turn = LessonTurn(
                                    session_id=lesson_session.id,
                                    speaker="assistant",
                                    text=greeting_text
                                )
                                session.add(turn)
                                session.commit()
                                
                                # Send audio
                                await synthesize_and_send(greeting_text)
                                logger.info("Legacy: Greeting sent successfully (text + audio)")
                            except Exception as e:
                                logger.error(f"Legacy: Failed to process greeting: {e}", exc_info=True)
                                await websocket.send_json({
                                    "type": "system",
                                    "level": "error",
                                    "message": f"Failed to generate greeting: {str(e)}. Please try speaking first."
                                })

                        elif data.get("type") == "system_event" and data.get("event") == "lesson_paused":
                            # Pause in legacy mode: generate summary, store, and close.
                            logger.info("Legacy: Received lesson_paused. Generating summary and marking session paused...")
                            from datetime import datetime as _dt
                            try:
                                summary = await _generate_pause_summary_legacy()
                                now = _dt.utcnow()

                                # Only update status; pause metadata lives in LessonPauseEvent
                                lesson_session.status = "paused"
                                session.add(lesson_session)

                                pause_event = LessonPauseEvent(
                                    lesson_session_id=lesson_session.id,
                                    paused_at=now,
                                    summary_text=summary,
                                )
                                session.add(pause_event)
                                session.commit()

                                payload = {
                                    "type": "system",
                                    "level": "info",
                                    "message": "Lesson paused.",
                                }
                                if summary:
                                    payload["resume_hint"] = summary
                                await websocket.send_json(payload)
                            except Exception as pause_error:
                                logger.error(f"Legacy: Failed to handle lesson_paused: {pause_error}", exc_info=True)
                                try:
                                    await websocket.send_json({
                                        "type": "system",
                                        "level": "error",
                                        "message": "Failed to pause lesson cleanly. You may need to restart.",
                                    })
                                except Exception:
                                    pass
                            finally:
                                try:
                                    await websocket.close(code=1000, reason="lesson_paused")
                                except Exception:
                                    pass
                                converter.close_stdin()
                                return
                    except Exception as e:
                        logger.error(f"Legacy: Error handling text message: {e}")
        except WebSocketDisconnect:
            pass
        finally:
            converter.close_stdin()

    async def stt_loop():
        nonlocal audio_buffer, is_speaking, silence_start_time
        while True:
            chunk = await loop.run_in_executor(None, converter.read, 4000)
            if not chunk:
                if converter.process.poll() is not None:
                    break
                await asyncio.sleep(0.01)
                continue
            
            # VAD
            try:
                rms = audioop.rms(chunk, 2)
            except:
                rms = 0
            
            if rms > SILENCE_THRESHOLD:
                if not is_speaking:
                    is_speaking = True
                silence_start_time = 0
                audio_buffer.extend(chunk)
            else:
                if is_speaking:
                    if silence_start_time == 0:
                        silence_start_time = time.time()
                    audio_buffer.extend(chunk)
                    
                    if time.time() - silence_start_time > SILENCE_DURATION:
                        if len(audio_buffer) > 48000 * 2 * MIN_AUDIO_LENGTH:
                            # Process
                            temp_filename = f"static/audio/input_{uuid.uuid4()}.wav"
                            os.makedirs("static/audio", exist_ok=True)
                            full_path = os.path.join(os.getcwd(), temp_filename)
                            
                            with open(full_path, "wb") as f:
                                f.write(add_wav_header(audio_buffer))
                            
                            try:
                                from openai import AsyncOpenAI
                                client = AsyncOpenAI(api_key=api_key)
                                with open(full_path, "rb") as af:
                                    transcription = await client.audio.transcriptions.create(
                                        model="whisper-1", file=af
                                    )
                                text = transcription.text
                                if text.strip():
                                    await process_user_text(text)
                            except Exception as e:
                                logger.error(f"Whisper Error: {e}")
                            finally:
                                try: os.remove(full_path)
                                except: pass
                        
                        audio_buffer = bytearray()
                        is_speaking = False
                        silence_start_time = 0

    await asyncio.gather(receive_task := asyncio.create_task(receive_loop()), stt_task := asyncio.create_task(stt_loop()))
    converter.close()

def add_wav_header(pcm_data, sample_rate=48000, channels=1, sampwidth=2):
    header = b'RIFF' + struct.pack('<I', 36 + len(pcm_data)) + b'WAVE' + \
             b'fmt ' + struct.pack('<I', 16) + struct.pack('<HHIIHH', 1, channels, sample_rate, sample_rate * channels * sampwidth, channels * sampwidth, sampwidth * 8) + \
             b'data' + struct.pack('<I', len(pcm_data))
    return header + pcm_data

@router.get("/health")
def health_check():
    return {"status": "ok", "provider": "openai-realtime"}


# ========================= Admin AI Realtime Assistant =========================

@router.websocket("/ws/admin-ai")
async def admin_ai_websocket(websocket: WebSocket):
    """Realtime voice channel for the Admin AI Assistant.

    This reuses the same cookies-based auth as the student voice WS, but only
    allows admins. Audio is sent from the browser as WebM, converted to PCM via
    ffmpeg (AudioConverter), chunked with simple VAD, transcribed with
    whisper-1 and then passed into the existing Admin AI pipeline
    (process_admin_message). Responses are played back with tts-1.
    """
    await websocket.accept()
    logger.info("Admin AI WebSocket connection accepted")

    from app.database import engine
    session = Session(engine)

    user: Optional[UserAccount] = None

    try:
        # 0. Authenticate via session cookie
        session_id = websocket.cookies.get("session_id")
        if session_id:
            auth_session = session.get(AuthSession, session_id)
            from datetime import datetime
            if auth_session and not auth_session.is_revoked and auth_session.expires_at > datetime.utcnow():
                user = session.get(UserAccount, auth_session.user_id)

        if not user or user.role != "admin":
            await websocket.send_json({
                "type": "system",
                "level": "error",
                "message": "Admin authentication required",
            })
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return

        # 1. Load OpenAI settings - PREFER env var over database
        settings = session.get(AppSettings, 1)
        env_key = os.getenv("OPENAI_API_KEY")
        db_key = settings.openai_api_key if settings and settings.openai_api_key else None
        api_key = env_key if env_key else db_key
        if api_key:
            api_key = api_key.strip().strip("'").strip('"')
        if not api_key:
            await websocket.send_json({
                "type": "system",
                "level": "error",
                "message": "OpenAI API key missing.",
            })
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return

        await run_admin_assistant_session(websocket, api_key, user, session)

    except WebSocketDisconnect:
        logger.info("Admin AI WebSocket disconnected")
    except Exception as e:
        logger.error(f"Admin AI main loop error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "system",
                "level": "error",
                "message": f"Admin AI error: {e}",
            })
        except Exception:
            pass
    finally:
        session.close()
        logger.info("Admin AI cleanup complete")


async def run_admin_assistant_session(
    websocket: WebSocket,
    api_key: str,
    user: UserAccount,
    session: Session,
):
    """Realtime admin assistant using Whisper + Admin AI tools + TTS.

    Audio flow:
    - Browser sends WebM chunks.
    - AudioConverter (ffmpeg) converts to PCM 48k mono.
    - Simple RMS-based VAD cuts utterances.
    - Each utterance -> whisper-1 -> text.
    - Text -> process_admin_message -> AI response + actions_taken.
    - AI response -> tts-1 via existing get_voice_engine("openai").
    - Text + actions are streamed back to the UI as JSON + audio.
    """
    from app.services.yandex_service import AudioConverter
    from app.services.voice_engine import get_voice_engine
    from app.services.admin_ai_service import process_admin_message
    from openai import AsyncOpenAI
    import audioop
    from io import BytesIO

    logger.info("Starting Admin Assistant realtime session")

    try:
        converter = AudioConverter()
        tts_engine = get_voice_engine("openai", api_key=api_key)
    except Exception as e:
        logger.error(f"Admin AI init failed: {e}")
        await websocket.send_json({
            "type": "system",
            "level": "error",
            "message": f"Failed to init audio stack: {e}",
        })
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    admin_conversation_id: Optional[int] = None
    audio_buffer = bytearray()
    is_speaking = False
    silence_start_time = 0.0
    SILENCE_THRESHOLD = 500
    SILENCE_DURATION = 1.0
    MIN_AUDIO_LENGTH = 0.5  # seconds

    loop = asyncio.get_running_loop()
    stt_client = AsyncOpenAI(api_key=api_key)

    async def synthesize_and_send(text: str):
        try:
            async for chunk in tts_engine.synthesize_stream(text, voice_id="alloy"):
                if chunk:
                    await websocket.send_bytes(chunk)
        except Exception as e:
            logger.error(f"Admin AI TTS error: {e}")

    async def handle_admin_turn(text: str):
        nonlocal admin_conversation_id

        # Show final user text in UI
        await websocket.send_json({
            "type": "admin_transcript",
            "role": "human",
            "text": text,
        })

        def _call_process():
            return process_admin_message(
                admin_user_id=user.id,
                message_text=text,
                session=session,
                conversation_id=admin_conversation_id,
            )

        try:
            result = await loop.run_in_executor(None, _call_process)
        except Exception as e:
            logger.error(f"Admin AI process_admin_message error: {e}", exc_info=True)
            await websocket.send_json({
                "type": "system",
                "level": "error",
                "message": f"Admin AI error: {e}",
            })
            return

        admin_conversation_id = result.get("conversation_id", admin_conversation_id)

        if "error" in result:
            ai_text = f"Error: {result['error']}"
            actions = []
        else:
            ai_text = result.get("ai_response") or ""
            actions = result.get("actions_taken") or []

        if ai_text:
            await websocket.send_json({
                "type": "admin_transcript",
                "role": "ai",
                "text": ai_text,
                "actions_taken": actions,
            })
            await synthesize_and_send(ai_text)

    async def receive_loop():
        try:
            while True:
                message = await websocket.receive()
                if "bytes" in message:
                    data = message["bytes"]
                    await loop.run_in_executor(None, converter.write, data)
                elif "text" in message:
                    # Reserved for future control messages (e.g. reset, stop)
                    logger.info(f"Admin AI WS text message: {message['text']}")
        except WebSocketDisconnect:
            logger.info("Admin AI receive_loop: client disconnected")
        finally:
            converter.close_stdin()

    async def stt_loop():
        nonlocal audio_buffer, is_speaking, silence_start_time
        while True:
            chunk = await loop.run_in_executor(None, converter.read, 4000)
            if not chunk:
                if converter.process.poll() is not None:
                    break
                await asyncio.sleep(0.01)
                continue

            try:
                rms = audioop.rms(chunk, 2)
            except Exception:
                rms = 0

            if rms > SILENCE_THRESHOLD:
                if not is_speaking:
                    is_speaking = True
                silence_start_time = 0
                audio_buffer.extend(chunk)
            else:
                if is_speaking:
                    if silence_start_time == 0:
                        silence_start_time = time.time()
                    audio_buffer.extend(chunk)

                    if time.time() - silence_start_time > SILENCE_DURATION:
                        if len(audio_buffer) > 48000 * 2 * MIN_AUDIO_LENGTH:
                            pcm_bytes = bytes(audio_buffer)
                            audio_buffer = bytearray()
                            is_speaking = False
                            silence_start_time = 0

                            wav_bytes = add_wav_header(pcm_bytes, sample_rate=48000)
                            buf = BytesIO(wav_bytes)
                            buf.name = "admin.wav"

                            try:
                                transcription = await stt_client.audio.transcriptions.create(
                                    model="whisper-1",
                                    file=buf,
                                )
                                text = (transcription.text or "").strip()
                                if text:
                                    await handle_admin_turn(text)
                            except Exception as e:
                                logger.error(f"Admin AI whisper error: {e}", exc_info=True)
                                try:
                                    await websocket.send_json({
                                        "type": "system",
                                        "level": "error",
                                        "message": f"STT error: {e}",
                                    })
                                except Exception:
                                    pass
                        else:
                            # Too short utterance; just drop it.
                            audio_buffer = bytearray()
                            is_speaking = False
                            silence_start_time = 0

    try:
        await asyncio.gather(
            asyncio.create_task(receive_loop()),
            asyncio.create_task(stt_loop()),
        )
    finally:
        converter.close()
        logger.info("Admin AI session finished")
