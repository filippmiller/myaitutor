import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlmodel import Session, select
from app.database import get_session
from app.models import AppSettings, UserAccount, LessonSession, LessonTurn, UserProfile, SessionMessage
from app.services.auth_service import verify_session_id
from app.services.openai_service import SYSTEM_TUTOR_PROMPT
import openai
import os
import aiohttp
import sys
import traceback

# Try to import Deepgram safely
DEEPGRAM_AVAILABLE = False
DeepgramClient = None
LiveTranscriptionEvents = None
LiveOptions = None

try:
    import deepgram
    print(f"Deepgram Module: {deepgram}")
    
    # Attempt to get DeepgramClient
    if hasattr(deepgram, 'DeepgramClient'):
        DeepgramClient = deepgram.DeepgramClient
    else:
        # Try importing from deepgram directly
        from deepgram import DeepgramClient

    # Try to find LiveTranscriptionEvents and LiveOptions
    # They might be in deepgram.clients.live.v1 or just deepgram
    try:
        from deepgram import LiveTranscriptionEvents
    except ImportError:
        try:
            from deepgram.clients.live.v1 import LiveTranscriptionEvents
        except ImportError:
            pass

    try:
        from deepgram import LiveOptions
    except ImportError:
        try:
            from deepgram.clients.live.v1 import LiveOptions
        except ImportError:
            pass

    if DeepgramClient:
        DEEPGRAM_AVAILABLE = True
        print("DeepgramClient loaded successfully")
    else:
        print("DeepgramClient not found")

except Exception as e:
    print(f"Deepgram Setup Error: {e}")
    import traceback
    traceback.print_exc()

if not DEEPGRAM_AVAILABLE:
    print("WARNING: Deepgram SDK not available. Voice features will fail.")


router = APIRouter()

@router.get("/voice-lesson/health")
async def voice_lesson_health(session: Session = Depends(get_session)):
    """Health check for voice lesson prerequisites"""
    from app.services.auth_service import get_current_user
    from fastapi import Request, Depends as FastAPIDepends
    
    result = {
        "deepgram_available": DEEPGRAM_AVAILABLE,
        "deepgram_client": DeepgramClient is not None,
    }
    
    # Check settings
    settings = session.get(AppSettings, 1)
    result["settings_exist"] = settings is not None
    result["deepgram_key_set"] = bool(settings and settings.deepgram_api_key)
    result["openai_key_set"] = bool(settings and settings.openai_api_key)
    
    return result

@router.websocket("/voice-lesson/ws")
async def voice_lesson_ws(
    websocket: WebSocket,
    session: Session = Depends(get_session)
):
    print("=" * 80)
    print("🔌 [WEBSOCKET] New connection attempt")
    await websocket.accept()
    print("✅ [WEBSOCKET] Connection accepted")
    
    # 1. Authentication
    # Try query param first, then cookie
    token = websocket.query_params.get("token")
    if not token:
        token = websocket.cookies.get("session_id")
    
    print(f"🔑 [AUTH] Token found: {bool(token)}")
        
    user = None
    if token:
        try:
            user_id = verify_session_id(token, session)
            if user_id:
                user = session.get(UserAccount, user_id)
                print(f"✅ [AUTH] User authenticated: {user.email if user else 'None'}")
        except Exception as e:
            print(f"❌ [AUTH] Error: {e}")
            pass
            
    if not user:
        print("❌ [AUTH] Authentication failed - closing connection")
        await websocket.close(code=1008, reason="Unauthorized")
        return

    # 2. Get Settings
    settings = session.get(AppSettings, 1)
    if not settings or not settings.deepgram_api_key or not settings.openai_api_key:
        print("❌ [SETTINGS] Missing API keys")
        await websocket.close(code=1011, reason="Server configuration missing")
        return
    
    print(f"✅ [SETTINGS] API keys present - Deepgram: {bool(settings.deepgram_api_key)}, OpenAI: {bool(settings.openai_api_key)}")

    # 3. Create Lesson Session
    lesson_session = LessonSession(user_account_id=user.id)
    session.add(lesson_session)
    session.commit()
    session.refresh(lesson_session)
    print(f"✅ [SESSION] Lesson session created: {lesson_session.id}")

    # 4. Setup Deepgram
    if not DEEPGRAM_AVAILABLE:
        print("❌ [DEEPGRAM] SDK not available")
        await websocket.close(code=1011, reason="Deepgram SDK missing")
        return
    
    print("✅ [DEEPGRAM] SDK available")

    try:
        print("🔧 [DEEPGRAM] Initializing client...")
        # Initialize Deepgram Client (v5+ uses api_key parameter)
        deepgram = DeepgramClient(api_key=settings.deepgram_api_key)
        print("✅ [DEEPGRAM] Client initialized")

    # OpenAI Client
    openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    # State
    user_profile = session.exec(select(UserProfile).where(UserProfile.user_account_id == user.id)).first()

    try:
        print("🔧 [DEEPGRAM] Initializing client...")
        deepgram = DeepgramClient(api_key=settings.deepgram_api_key)
        print("✅ [DEEPGRAM] Client initialized")

        # Configure Deepgram connection
        print("🔧 [DEEPGRAM] Creating connection...")
        
        # Open Deepgram v2 connection as context manager
        with deepgram.listen.v2.connect(
            model="nova-2",
            encoding="linear16",
            sample_rate="16000"
        ) as dg_connection:
            print("✅ [DEEPGRAM] Connection created")

            # Define event handlers
            async def handle_open(_):
                print("🎧 [DEEPGRAM] Connection opened")

            async def handle_message(message):
                try:
                    # Check if it's a transcript message with the expected structure
                    if hasattr(message, 'channel') and hasattr(message.channel, 'alternatives'):
                        sentence = message.channel.alternatives[0].transcript
                        if not sentence or len(sentence) == 0:
                            return
                        
                        if hasattr(message, 'is_final') and message.is_final:
                            print(f"📝 [USER] Said: {sentence}")
                            # 1. Save User Turn
                            user_turn = LessonTurn(
                                session_id=lesson_session.id,
                                speaker="user",
                                text=sentence
                            )
                            session.add(user_turn)
                            session.commit()
                            
                            # 2. Send "User finished speaking" signal to frontend
                            await websocket.send_json({"type": "transcript", "role": "user", "text": sentence})

                            # 3. Call OpenAI
                            messages = [
                                {"role": "system", "content": SYSTEM_TUTOR_PROMPT},
                                {"role": "system", "content": f"Student Name: {user_profile.name if user_profile else 'Student'}. Level: {user_profile.english_level if user_profile else 'A1'}."}
                            ]
                            
                            # Add recent context
                            recent_turns = session.exec(select(LessonTurn).where(LessonTurn.session_id == lesson_session.id).order_by(LessonTurn.created_at.desc()).limit(10)).all()
                            for turn in reversed(recent_turns):
                                messages.append({"role": turn.speaker, "content": turn.text})
                            
                            print("🤖 [OPENAI] Calling...")
                            response = await openai_client.chat.completions.create(
                                model=settings.default_model,
                                messages=messages
                            )
                            ai_text = response.choices[0].message.content
                            print(f"💬 [AI] Said: {ai_text}")
                            
                            # 4. Save Assistant Turn
                            ai_turn = LessonTurn(
                                session_id=lesson_session.id,
                                speaker="assistant",
                                text=ai_text
                            )
                            session.add(ai_turn)
                            session.commit()

                            # 5. Send Text to Frontend
                            await websocket.send_json({"type": "transcript", "role": "assistant", "text": ai_text})

                            # 6. TTS via Deepgram REST API
                            tts_url = f"https://api.deepgram.com/v1/speak?model={settings.deepgram_voice_id}"
                            headers = {
                                "Authorization": f"Token {settings.deepgram_api_key}",
                                "Content-Type": "application/json"
                            }
                            payload = {"text": ai_text}
                            
                            async with aiohttp.ClientSession() as http_session:
                                async with http_session.post(tts_url, headers=headers, json=payload) as resp:
                                    if resp.status == 200:
                                        audio_data = await resp.read()
                                        await websocket.send_bytes(audio_data)
                                        print("🔊 [TTS] Audio sent to client")
                                    else:
                                        print(f"❌ [TTS] Error: {await resp.text()}")
                except Exception as e:
                    print(f"❌ [HANDLER] Error: {e}")
                    traceback.print_exc()

            async def handle_close(_):
                print("🔌 [DEEPGRAM] Connection closed")

            async def handle_error(error):
                print(f"❌ [DEEPGRAM] Error: {error}")

            # Register event handlers
            from deepgram.core.events import EventType
            dg_connection.on(EventType.OPEN, handle_open)
            dg_connection.on(EventType.MESSAGE, handle_message)
            dg_connection.on(EventType.CLOSE, handle_close)
            dg_connection.on(EventType.ERROR, handle_error)

            # Start listening
            dg_connection.start_listening()
            print("🎧 [DEEPGRAM] Listening started")

            # Loop to receive audio from client and forward to Deepgram
            try:
                while True:
                    data = await websocket.receive_bytes()
                    print(f"🎤 [AUDIO] Received {len(data)} bytes from client")
                    # Send audio to Deepgram
                    dg_connection.send(data)
                        
            except WebSocketDisconnect:
                print("🔌 [CLIENT] Disconnected")
            except Exception as e:
                print(f"❌ [LOOP] Error: {e}")
                traceback.print_exc()
            finally:
                # Connection will auto-close when exiting context manager
                lesson_session.status = "completed"
                lesson_session.ended_at = datetime.utcnow()
                session.add(lesson_session)
                session.commit()
                print("✅ [SESSION] Completed")

    except Exception as e:
        print(f"❌ [SETUP] Error: {e}")
        traceback.print_exc()
        await websocket.close(code=1011, reason=str(e))
