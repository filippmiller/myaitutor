
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
from app.models import AppSettings, UserAccount, UserProfile, AuthSession, LessonSession, LessonTurn
from app.services.yandex_service import YandexService, AudioConverter
from app.services.voice_engine import get_voice_engine
from app.services.tutor_service import build_tutor_system_prompt
from app.services.language_utils import parse_language_mode_marker, strip_language_markers

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
    logger.info("Voice WS Version: 2025-12-05 Realtime (gpt-realtime) + Fallback")
    
    # Manually create session
    from app.database import engine
    session = Session(engine)
    
    user: Optional[UserAccount] = None
    profile: Optional[UserProfile] = None
    api_key = None
    settings = None
    
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

        # 1. Load Settings
        settings = session.get(AppSettings, 1)
        api_key = settings.openai_api_key if settings and settings.openai_api_key else os.getenv("OPENAI_API_KEY")
        if api_key:
            api_key = api_key.strip().strip("'").strip('"')
        
        if not api_key:
            logger.error("OpenAI API Key missing")
            await websocket.send_json({"type": "system", "level": "error", "message": "OpenAI API Key missing."})
            await websocket.close(code=1011)
            return

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
                await run_realtime_session(websocket, api_key, voice_id, profile, session, user=user)
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
             
        await run_legacy_session(websocket, api_key, tts_engine_name, voice_id, profile, settings, session, user=user)

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
):
    """Manage a session with the latest OpenAI Realtime API (gpt-realtime)."""
    import subprocess
    import shutil
    from datetime import datetime
    
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg not found")

    # Create LessonSession
    lesson_session = LessonSession(
        user_account_id=profile.user_account_id if profile else (user.id if user else None),
        started_at=datetime.utcnow(),
        language_mode=None,  # Will be set by interaction
    )
    session.add(lesson_session)
    session.commit()
    session.refresh(lesson_session)
    logger.info(f"Created Realtime LessonSession {lesson_session.id}")

    # Build System Prompt
    system_prompt = build_tutor_system_prompt(session, profile, lesson_session_id=lesson_session.id)
    
    # Log system prompt details
    logger.info("=" * 80)
    logger.info("SYSTEM PROMPT BUILT:")
    logger.info(f"  Student Name: {profile.name if profile else 'None'}")
    logger.info(f"  Student Level: {profile.english_level if profile else 'None'}")
    logger.info(f"  Lesson Session ID: {lesson_session.id}")
    logger.info(f"  System Prompt Length: {len(system_prompt)} characters")
    logger.info(f"  System Prompt (First 500 chars):\n{system_prompt[:500]}")
    logger.info("=" * 80)

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

    # 1. Connect to OpenAI Realtime (latest model alias)
    url = "wss://api.openai.com/v1/realtime?model=gpt-realtime"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    
    async with websockets.connect(url, additional_headers=headers) as openai_ws:
        logger.info("Connected to OpenAI Realtime API (model=gpt-realtime)")
        
        # 2. Configure Session
        # Use audio PCM16 24kHz in and out; enable server-side VAD.
        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": system_prompt,
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
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.3,  # Lowered from 0.5 for better sensitivity
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                },
            },
        }
        await openai_ws.send(json.dumps(session_update))
        logger.info("Realtime: session.update sent to OpenAI with system prompt")
        
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
        greeting_item_ready = asyncio.Event()  # Event to signal when greeting conversation item is ready
        greeting_item_id = None  # Store the greeting item ID
        stt_language = "en-US"  # Logged from config message
        
        async def frontend_to_openai():
            """Read from frontend WebSocket, convert, send to OpenAI."""
            nonlocal greeting_triggered, greeting_item_id, prompt_log_data, stt_language
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
                                # Could be used for future enhancements or logging
                            
                            elif data.get("type") == "system_event" and data.get("event") == "lesson_started":
                                if greeting_triggered:
                                    logger.warning("Realtime: lesson_started received again, but greeting already sent - ignoring")
                                    continue
                                
                                greeting_triggered = True
                                logger.info("Realtime: Received lesson_started. Triggering greeting...")
                                
                                try:
                                    # System prompt already includes Universal Greeting Protocol
                                    # Trigger first interaction - OpenAI will follow the system prompt automatically
                                    user_name = profile.name if profile and profile.name else "Student"
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
                                            "content": [{"type": "input_text", "text": greeting_text}]
                                        }
                                    }
                                    logger.info(f"Realtime: Sending greeting trigger message (length: {len(greeting_text)} chars)")
                                    await openai_ws.send(json.dumps(greeting_trigger))
                                    logger.info("Realtime: Waiting for conversation item to be created...")
                                    
                                    # Wait for conversation item to be created (with timeout)
                                    try:
                                        await asyncio.wait_for(greeting_item_ready.wait(), timeout=5.0)
                                        logger.info(f"Realtime: Conversation item ready (ID: {greeting_item_id}), requesting response...")
                                        
                                        # Wait a bit more for item to be fully processed
                                        await asyncio.sleep(0.3)
                                        
                                        # Request response with explicit instructions and modalities
                                        response_request = {
                                            "type": "response.create",
                                            "response": {
                                                "modalities": ["text", "audio"],
                                                "instructions": f"Greet the user {user_name} warmly and start the lesson immediately. Do not ask if they are ready."
                                            }
                                        }
                                        logger.info("Realtime: Requesting response creation with explicit modalities...")
                                        await openai_ws.send(json.dumps(response_request))
                                        logger.info("Realtime: Response request sent successfully")
                                    except asyncio.TimeoutError:
                                        logger.error("Realtime: Timeout waiting for conversation item creation - proceeding anyway")
                                        response_request = {
                                            "type": "response.create",
                                            "response": {
                                                "modalities": ["text", "audio"],
                                                "instructions": f"Greet the user {user_name} warmly and start the lesson immediately."
                                            }
                                        }
                                        await openai_ws.send(json.dumps(response_request))
                                except Exception as greeting_error:
                                    logger.error(f"Realtime: Failed to trigger greeting: {greeting_error}", exc_info=True)
                                    await websocket.send_json({
                                        "type": "system",
                                        "level": "warning",
                                        "message": f"Failed to trigger greeting: {str(greeting_error)}. The lesson will continue, but you may need to speak first."
                                    })
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
            nonlocal greeting_item_id, greeting_item_ready
            audio_delta_count = 0
            try:
                async for message in openai_ws:
                    event = json.loads(message)
                    event_type = event.get("type")
                    
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
                            # Save User Turn
                            turn = LessonTurn(
                                session_id=lesson_session.id,
                                speaker="user",
                                text=transcript
                            )
                            session.add(turn)
                            session.commit()
                            
                    elif event_type == "session.updated":
                        # Session update confirmed by OpenAI
                        logger.info("Realtime: Session updated confirmed by OpenAI - system prompt is now active")
                    
                    elif event_type == "conversation.item.created":
                        # Conversation item created
                        item = event.get("item", {})
                        item_id = item.get("id")
                        item_type = item.get("type")
                        logger.info(f"Realtime: Conversation item created (ID: {item_id}, Type: {item_type})")
                        
                        # Only signal ready for greeting item (first user message)
                        if item_type == "message" and item.get("role") == "user":
                            # Check if this is the greeting item (first user message)
                            # Store current value first to avoid nonlocal scope issue
                            current_id = greeting_item_id
                            if current_id is None:
                                greeting_item_id = item_id
                                logger.info(f"Realtime: Greeting conversation item ready (ID: {item_id}), setting ready event...")
                                greeting_item_ready.set()
                    
                    elif event_type == "response.created":
                        # Response started
                        response = event.get("response", {})
                        response_id = response.get("id")
                        logger.info(f"Realtime: Response created (ID: {response_id})")
                        logger.info(f"Realtime: Response created details: {json.dumps(response, default=str)}")
                        
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
                            # Always save Assistant Turn (greeting, normal responses, etc.)
                            turn = LessonTurn(
                                session_id=lesson_session.id,
                                speaker="assistant",
                                text=transcript
                            )
                            session.add(turn)
                            session.commit()
                            logger.info(f"Realtime: Saved assistant transcript (length: {len(transcript)})")
                            
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
                                    logger.info(f"Realtime: Language mode set to {mode}")
                                elif level_change == "LEVEL_UP":
                                    if lesson_session.language_level:
                                        lesson_session.language_level = min(lesson_session.language_level + 1, 5)
                                        session.add(lesson_session)
                                        session.commit()
                                        logger.info(f"Realtime: Language level increased to {lesson_session.language_level}")

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
):
    """Legacy implementation using VAD + Whisper + TTS (OpenAI/Yandex)."""
    # Initialize Services
    try:
        yandex_service = YandexService() # Still used for fallback TTS potentially
        converter = AudioConverter() # ffmpeg 48k
        tts_engine = get_voice_engine(tts_engine_name, api_key=api_key)
    except Exception as e:
        logger.error(f"Legacy init failed: {e}")
        await websocket.close(code=1011)
        return

    # Create LessonSession
    from datetime import datetime
    lesson_session = LessonSession(
        user_account_id=profile.user_account_id if profile else (user.id if user else None),
        started_at=datetime.utcnow(),
        language_mode=None # Will be set by interaction
    )
    session.add(lesson_session)
    session.commit()
    session.refresh(lesson_session)
    logger.info(f"Created LessonSession {lesson_session.id}")

    # Build System Prompt
    system_prompt = build_tutor_system_prompt(session, profile, lesson_session_id=lesson_session.id)

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
        
        # Save User Turn
        turn = LessonTurn(
            session_id=lesson_session.id,
            speaker="user",
            text=text
        )
        session.add(turn)
        session.commit()
        
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
            
            # Save Assistant Turn
            turn = LessonTurn(
                session_id=lesson_session.id,
                speaker="assistant",
                text=full_resp
            )
            session.add(turn)
            session.commit()
            
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
