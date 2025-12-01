import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlmodel import Session, select
from app.database import get_session
from app.models import AppSettings, UserAccount, LessonSession, LessonTurn, UserProfile, SessionMessage
from app.services.auth_service import verify_session_id
from app.services.openai_service import SYSTEM_TUTOR_PROMPT
try:
    from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
except ImportError:
    try:
        from deepgram import DeepgramClient
        from deepgram.clients.live.v1 import LiveTranscriptionEvents, LiveOptions
    except ImportError:
        print("CRITICAL: Could not import Deepgram classes")
        raise
except Exception as e:
    print(f"!!!!!!!!!!!!!! DEEPGRAM IMPORT ERROR: {e}")
    raise e
import openai
import os
import aiohttp

router = APIRouter()

@router.websocket("/voice-lesson/ws")
async def voice_lesson_ws(
    websocket: WebSocket,
    session: Session = Depends(get_session)
):
    await websocket.accept()
    
    # 1. Authentication (via query param 'token' which is the session_id)
    token = websocket.query_params.get("token")
    user = None
    if token:
        try:
            user_id = verify_session_id(token, session)
            if user_id:
                user = session.get(UserAccount, user_id)
        except Exception as e:
            print(f"Auth error: {e}")
            pass
            
    if not user:
        print("WebSocket Auth Failed")
        await websocket.close(code=1008, reason="Unauthorized")
        return

    # 2. Get Settings
    settings = session.get(AppSettings, 1)
    if not settings or not settings.deepgram_api_key or not settings.openai_api_key:
        print("Settings missing")
        await websocket.close(code=1011, reason="Server configuration missing")
        return

    # 3. Create Lesson Session
    lesson_session = LessonSession(user_account_id=user.id)
    session.add(lesson_session)
    session.commit()
    session.refresh(lesson_session)

    # 4. Setup Deepgram
    try:
        # Initialize Deepgram Client
        deepgram = DeepgramClient(settings.deepgram_api_key)
        
        # Create a websocket connection to Deepgram
        dg_connection = deepgram.listen.asyncwebsocket.v("1")

        # OpenAI Client
        openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

        # State
        user_profile = session.exec(select(UserProfile).where(UserProfile.user_account_id == user.id)).first()
        
        async def on_message(self, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return
            
            if result.is_final:
                print(f"User said: {sentence}")
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
                
                print("Calling OpenAI...")
                response = await openai_client.chat.completions.create(
                    model=settings.default_model,
                    messages=messages
                )
                ai_text = response.choices[0].message.content
                print(f"AI said: {ai_text}")
                
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
                            # Send audio binary
                            # We send a text message first to say "audio coming" or just send bytes?
                            # WebSocket can distinguish text vs bytes frames.
                            await websocket.send_bytes(audio_data)
                        else:
                            print(f"TTS Error: {await resp.text()}")

        # Register event handler
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

        # Configure Deepgram Options
        options = LiveOptions(
            model="nova-2", 
            language="en-US", 
            smart_format=True,
            # encoding is omitted to allow auto-detection (e.g. for webm/opus)
        )
        
        # Start Deepgram Connection
        if await dg_connection.start(options) is False:
            print("Failed to start Deepgram connection")
            await websocket.close()
            return

        print("Deepgram connected, listening...")

        # Loop to receive audio from client
        try:
            while True:
                data = await websocket.receive_bytes()
                await dg_connection.send(data)
        except WebSocketDisconnect:
            print("Client disconnected")
        except Exception as e:
            print(f"WS Loop Error: {e}")
        finally:
            await dg_connection.finish()
            lesson_session.status = "completed"
            lesson_session.ended_at = datetime.utcnow()
            session.add(lesson_session)
            session.commit()

    except Exception as e:
        print(f"Setup Error: {e}")
        await websocket.close(code=1011, reason=str(e))
