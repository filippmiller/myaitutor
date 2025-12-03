
import asyncio
import json
import logging
import uuid
import time
import os
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import AppSettings, UserAccount, UserProfile, AuthSession
from app.services.yandex_service import YandexService, AudioConverter
from app.services.voice_engine import get_voice_engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    logger.info("Voice WS Version: 2025-12-03 Fix Datetime")
    
    # Manually create session
    from app.database import engine
    session = Session(engine)
    
    converter = None
    
    try:
        # 0. Authenticate User
        session_id = websocket.cookies.get("session_id")
        user = None
        profile = None
        
        if session_id:
            auth_session = session.get(AuthSession, session_id)
            # Fix: Compare datetime with datetime
            from datetime import datetime
            if auth_session and not auth_session.is_revoked and auth_session.expires_at > datetime.utcnow():
                 user = session.get(UserAccount, auth_session.user_id)
        
        if not user:
            logger.warning("Unauthenticated WebSocket connection")
            # We could close, but maybe allow anonymous for now? 
            # No, preferences depend on user.
            # Let's try to proceed with defaults if no user, or close.
            # For now, let's proceed with defaults but log it.
        else:
            profile = session.exec(select(UserProfile).where(UserProfile.user_account_id == user.id)).first()
            logger.info(f"Authenticated user: {user.email}")

        # 1. Load Settings
        try:
            settings = session.get(AppSettings, 1)
            api_key = settings.openai_api_key if settings and settings.openai_api_key else os.getenv("OPENAI_API_KEY")
            
            if api_key:
                api_key = api_key.strip().strip("'").strip('"')
            
            if not api_key:
                logger.error("OpenAI API Key missing")
                await websocket.send_json({"type": "system", "level": "error", "message": "OpenAI API Key missing."})
            else:
                masked_key = api_key[:8] + "*" * 10 if api_key else "None"
                logger.info(f"Loaded OpenAI API Key: {masked_key}")
        except Exception as e:
            logger.error(f"Database error loading settings: {e}")
            await websocket.close(code=1011, reason="Database error")
            return

        # 2. Initialize Services
        try:
            # Check for ffmpeg
            import shutil
            ffmpeg_path = shutil.which("ffmpeg")
            if not ffmpeg_path:
                logger.error("ffmpeg not found")
                await websocket.close(code=1011, reason="ffmpeg missing")
                return

            # Initialize Yandex for STT (Streaming) - Keep as default for input for now
            logger.info("Initializing YandexService for STT...")
            yandex_service = YandexService()
            converter = AudioConverter()
            
            # Initialize TTS Engine based on preferences
            tts_engine_name = "openai"
            voice_id = "alloy"
            
            if profile:
                tts_engine_name = profile.preferred_tts_engine or "openai"
                voice_id = profile.preferred_voice_id or "alloy"
                
                # Legacy preference fallback
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
            
            logger.info(f"Selected TTS Engine: {tts_engine_name}, Voice: {voice_id}")
            tts_engine = get_voice_engine(tts_engine_name, api_key=api_key)
            
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}", exc_info=True)
            await websocket.close(code=1011, reason=f"Service init failed: {str(e)}")
            return

        # 3. State
        conversation_history = [
            {"role": "system", "content": (
                "You are a helpful English tutor for a Russian speaker. "
                "The user might speak a mix of English and Russian. "
                "Always respond in English to help them practice, unless they explicitly ask for an explanation in Russian. "
                "Note: The user's speech is transcribed by a Russian STT model, so English words may appear transliterated into Cyrillic. "
                "Keep your answers concise and helpful."
            )}
        ]
        stt_language = "ru-RU"
        
        # Helpers
        async def synthesize_and_send(text: str):
            try:
                logger.info(f"Starting TTS ({tts_engine_name}/{voice_id}) for: {text[:30]}...")
                
                # Use the VoiceEngine abstraction
                # It returns bytes (MP3 for both OpenAI and Yandex implementations)
                audio_bytes = await tts_engine.synthesize(text, voice_id=voice_id)
                
                if not audio_bytes:
                    return

                # Send bytes directly (MP3)
                await websocket.send_bytes(audio_bytes)
                
            except Exception as e:
                logger.error(f"TTS Error: {e}")
                # Fallback to Yandex if OpenAI fails
                if tts_engine_name == "openai":
                    logger.info("Attempting fallback to Yandex TTS...")
                    try:
                        fallback_engine = get_voice_engine("yandex")
                        audio_bytes = await fallback_engine.synthesize(text, voice_id="alena")
                        await websocket.send_bytes(audio_bytes)
                    except Exception as e2:
                        logger.error(f"Fallback TTS Error: {e2}")
                        await websocket.send_json({"type": "system", "level": "error", "message": "TTS Failed"})
                else:
                    await websocket.send_json({"type": "system", "level": "error", "message": "TTS Error"})

        async def generate_greeting():
            try:
                logger.info("Generating greeting...")
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=api_key)
                
                user_name = profile.name if profile else "Student"
                
                system_prompt = (
                    f"You are an English tutor speaking to a student named {user_name}. "
                    "Generate a friendly, short greeting in Russian that invites them to practice English. "
                    "Vary your wording every time. Do not be repetitive."
                )
                
                completion = await client.chat.completions.create(
                    model=settings.default_model,
                    messages=[{"role": "system", "content": system_prompt}]
                )
                greeting = completion.choices[0].message.content
                
                await websocket.send_json({"type": "transcript", "role": "assistant", "text": greeting})
                conversation_history.append({"role": "assistant", "content": greeting})
                await synthesize_and_send(greeting)
                
            except Exception as e:
                logger.error(f"Greeting Error: {e}")
                await websocket.send_json({"type": "system", "level": "error", "message": "Failed to generate greeting."})

        async def process_user_text(text: str):
            await websocket.send_json({"type": "transcript", "role": "user", "text": text})
            conversation_history.append({"role": "user", "content": text})
            
            full_response_text = ""
            current_sentence = ""
            
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=api_key)
                
                stream = await client.chat.completions.create(
                    model=settings.default_model,
                    messages=conversation_history,
                    stream=True
                )
                
                import re
                
                async for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        full_response_text += content
                        current_sentence += content
                        
                        # Check for sentence endings
                        if re.search(r'[.!?]\s', current_sentence):
                            parts = re.split(r'([.!?])', current_sentence)
                            to_process = ""
                            remainder = ""
                            
                            for i in range(0, len(parts) - 1, 2):
                                if i+1 < len(parts):
                                    sentence = parts[i] + parts[i+1]
                                    to_process += sentence
                            
                            if len(parts) % 2 != 0:
                                remainder = parts[-1]
                                
                            if to_process.strip():
                                await websocket.send_json({"type": "transcript", "role": "assistant", "text": to_process})
                                await synthesize_and_send(to_process)
                                
                            current_sentence = remainder

                if current_sentence.strip():
                    await websocket.send_json({"type": "transcript", "role": "assistant", "text": current_sentence})
                    await synthesize_and_send(current_sentence)

            except Exception as e:
                logger.error(f"LLM Error: {e}")
                await websocket.send_json({"type": "system", "level": "error", "message": "Brain connection failed."})
                return

            conversation_history.append({"role": "assistant", "content": full_response_text})

        # Loops
        async def receive_loop():
            nonlocal stt_language
            loop = asyncio.get_running_loop()
            try:
                while True:
                    message = await websocket.receive()
                    if "bytes" in message:
                        data = message["bytes"]
                        if converter:
                            await loop.run_in_executor(None, converter.write, data)
                    elif "text" in message:
                        try:
                            msg = json.loads(message["text"])
                            if msg.get("type") == "config":
                                stt_language = msg.get("stt_language", "ru-RU")
                                logger.info(f"STT Language set to: {stt_language}")
                            elif msg.get("type") == "system_event" and msg.get("event") == "lesson_started":
                                await generate_greeting()
                        except json.JSONDecodeError:
                            pass
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected")
            except Exception as e:
                logger.error(f"Error in receive_loop: {e}", exc_info=True)
            finally:
                if converter:
                    converter.close_stdin()

        # VAD & STT State
        audio_buffer = bytearray()
        is_speaking = False
        silence_start_time = 0
        
        # VAD Constants
        SILENCE_THRESHOLD = 500  # Amplitude threshold (16-bit PCM)
        SILENCE_DURATION = 1.0   # Seconds of silence to trigger STT
        MIN_AUDIO_LENGTH = 0.5   # Minimum speech duration to process
        
        import audioop
        import struct

        async def stt_loop():
            nonlocal audio_buffer, is_speaking, silence_start_time
            
            logger.info("Starting VAD/STT loop (OpenAI Whisper)")
            
            while True:
                if not converter:
                    break
                    
                # Read chunk from converter (PCM s16le 48k mono)
                chunk = await loop.run_in_executor(None, converter.read, 4000)
                if not chunk:
                    if converter.process.poll() is not None:
                        break
                    await asyncio.sleep(0.01)
                    continue
                
                # VAD Logic
                # Calculate RMS (Root Mean Square) amplitude
                try:
                    rms = audioop.rms(chunk, 2) # 2 bytes width
                except Exception:
                    rms = 0
                
                if rms > SILENCE_THRESHOLD:
                    if not is_speaking:
                        is_speaking = True
                        logger.info("Speech detected")
                    silence_start_time = 0
                    audio_buffer.extend(chunk)
                else:
                    if is_speaking:
                        # We were speaking, now it's quiet
                        if silence_start_time == 0:
                            silence_start_time = time.time()
                        
                        audio_buffer.extend(chunk) # Keep recording silence briefly
                        
                        # Check duration
                        if time.time() - silence_start_time > SILENCE_DURATION:
                            # Silence timeout reached -> Process Audio
                            logger.info(f"Silence detected ({SILENCE_DURATION}s). Processing {len(audio_buffer)} bytes...")
                            
                            # Check min length (48000 * 2 bytes * seconds)
                            if len(audio_buffer) > 48000 * 2 * MIN_AUDIO_LENGTH:
                                # Process
                                temp_filename = f"static/audio/input_{uuid.uuid4()}.wav"
                                os.makedirs("static/audio", exist_ok=True)
                                full_path = os.path.join(os.getcwd(), temp_filename)
                                
                                # Write WAV
                                with open(full_path, "wb") as f:
                                    # WAV Header
                                    f.write(b'RIFF' + struct.pack('<I', 36 + len(audio_buffer)) + b'WAVE' + \
                                            b'fmt ' + struct.pack('<I', 16) + struct.pack('<HHIIHH', 1, 1, 48000, 48000 * 1 * 2, 1 * 2, 16) + \
                                            b'data' + struct.pack('<I', len(audio_buffer)))
                                    f.write(audio_buffer)
                                
                                # Transcribe with OpenAI
                                try:
                                    logger.info("Sending to Whisper...")
                                    from openai import AsyncOpenAI
                                    client = AsyncOpenAI(api_key=api_key)
                                    
                                    with open(full_path, "rb") as audio_file:
                                        transcription = await client.audio.transcriptions.create(
                                            model="whisper-1", 
                                            file=audio_file,
                                            language=None # Auto-detect language
                                        )
                                    
                                    text = transcription.text
                                    logger.info(f"Whisper STT: {text}")
                                    
                                    if text and text.strip():
                                        await process_user_text(text)
                                        
                                except Exception as e:
                                    logger.error(f"Whisper STT Error: {e}")
                                finally:
                                    # Cleanup
                                    try:
                                        os.remove(full_path)
                                    except:
                                        pass
                            else:
                                logger.info("Audio too short, discarding.")
                            
                            # Reset
                            audio_buffer = bytearray()
                            is_speaking = False
                            silence_start_time = 0
                    else:
                        # Just silence, do nothing (or keep small buffer for context if needed, but simple VAD is fine)
                        pass

        # Start loops
        receive_task = asyncio.create_task(receive_loop())
        stt_task = asyncio.create_task(stt_loop())

        await asyncio.gather(receive_task, stt_task)
        
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Main loop error: {e}", exc_info=True)
    finally:
        logger.info("Cleaning up resources...")
        if converter:
            converter.close()
        session.close()
        logger.info("Cleanup complete")

@router.get("/health")
def health_check():
    return {"status": "ok", "provider": "yandex"}
