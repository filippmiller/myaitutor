
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
from app.models import AppSettings, UserAccount, UserProfile, AuthSession
from app.services.yandex_service import YandexService, AudioConverter
from app.services.voice_engine import get_voice_engine

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
    logger.info("Voice WS Version: 2025-12-03 Realtime + Fallback")
    
    # Manually create session
    from app.database import engine
    session = Session(engine)
    
    user = None
    profile = None
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
                logger.info("Attempting OpenAI Realtime Session...")
                await run_realtime_session(websocket, api_key, voice_id, profile)
                return # If successful and finishes normally
            except Exception as e:
                logger.error(f"Realtime Session failed: {e}", exc_info=True)
                await websocket.send_json({"type": "system", "level": "warning", "message": "Realtime connection failed. Switching to standard mode."})
                # Fall through to legacy
        
        # 3. Legacy Session (Whisper/Yandex)
        logger.info("Starting Legacy Session (Whisper/Yandex)...")
        await run_legacy_session(websocket, api_key, tts_engine_name, voice_id, profile, settings)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Main loop error: {e}", exc_info=True)
    finally:
        session.close()
        logger.info("Cleanup complete")


async def run_realtime_session(websocket: WebSocket, api_key: str, voice_id: str, profile: UserProfile | None):
    """
    Manages a session with OpenAI Realtime API.
    """
    import subprocess
    import shutil
    
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg not found")

    # 1. Connect to OpenAI
    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1"
    }
    
    async with websockets.connect(url, additional_headers=headers) as openai_ws:
        logger.info("Connected to OpenAI Realtime API")
        
        # 2. Configure Session
        user_name = profile.name if profile else "Student"
        system_instructions = (
            f"You are a helpful English tutor for a Russian speaker named {user_name}. "
            "The user might speak a mix of English and Russian. "
            "Always respond in English to help them practice, unless they explicitly ask for an explanation in Russian. "
            "Be patient, friendly, and concise. "
            "Do not translate everything, just reply naturally."
        )
        
        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": system_instructions,
                "voice": voice_id if voice_id in ["alloy", "echo", "shimmer", "ash", "ballad", "coral", "sage", "verse"] else "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                }
            }
        }
        await openai_ws.send(json.dumps(session_update))
        
        # 3. Audio Converters
        # Frontend (WebM) -> PCM 24k (OpenAI)
        # We need a converter that outputs 24000Hz, 1 channel, s16le
        input_converter = subprocess.Popen(
            [
                ffmpeg_path,
                "-i", "pipe:0",
                "-f", "s16le", "-acodec", "pcm_s16le", "-ar", "24000", "-ac", "1",
                "pipe:1"
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        
        # 4. Loops
        loop = asyncio.get_running_loop()
        
        async def frontend_to_openai():
            """Read from frontend WebSocket, convert, send to OpenAI."""
            try:
                while True:
                    message = await websocket.receive()
                    if "bytes" in message:
                        data = message["bytes"]
                        # Write to ffmpeg
                        input_converter.stdin.write(data)
                        input_converter.stdin.flush()
                    elif "text" in message:
                        # Handle control messages if any
                        pass
            except WebSocketDisconnect:
                pass
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
            try:
                async for message in openai_ws:
                    event = json.loads(message)
                    event_type = event.get("type")
                    
                    if event_type == "response.audio.delta":
                        # Received Audio Delta (PCM 24k Base64)
                        b64_audio = event.get("delta")
                        if b64_audio:
                            pcm_data = base64.b64decode(b64_audio)
                            # Wrap in WAV (24k) and send
                            wav_data = add_wav_header(pcm_data, sample_rate=24000)
                            await websocket.send_bytes(wav_data)
                            
                    elif event_type == "response.audio_transcript.delta":
                        # Received Text Delta
                        delta = event.get("delta")
                        if delta:
                            await websocket.send_json({"type": "transcript", "role": "assistant", "text": delta})
                            
                    elif event_type == "conversation.item.input_audio_transcription.completed":
                        # User transcript final
                        transcript = event.get("transcript")
                        if transcript:
                            await websocket.send_json({"type": "transcript", "role": "user", "text": transcript})
                            
                    elif event_type == "error":
                        logger.error(f"OpenAI Realtime Error: {event}")
                        
            except Exception as e:
                logger.error(f"OpenAI->Frontend Error: {e}")
                raise e # Trigger fallback

        # Start tasks
        tasks = [
            asyncio.create_task(frontend_to_openai()),
            asyncio.create_task(converter_reader()),
            asyncio.create_task(openai_to_frontend())
        ]
        
        # Send initial greeting trigger?
        # Realtime API doesn't auto-greet unless instructed.
        # We can send a text item to trigger response.
        await openai_ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello, I am ready for the lesson."}]
            }
        }))
        await openai_ws.send(json.dumps({"type": "response.create"}))

        await asyncio.gather(*tasks)


async def run_legacy_session(websocket: WebSocket, api_key: str, tts_engine_name: str, voice_id: str, profile: UserProfile | None, settings: AppSettings):
    """
    Legacy implementation using VAD + Whisper + TTS (OpenAI/Yandex).
    """
    # Initialize Services
    try:
        yandex_service = YandexService() # Still used for fallback TTS potentially
        converter = AudioConverter() # ffmpeg 48k
        tts_engine = get_voice_engine(tts_engine_name, api_key=api_key)
    except Exception as e:
        logger.error(f"Legacy init failed: {e}")
        await websocket.close(code=1011)
        return

    # State
    conversation_history = [
        {"role": "system", "content": (
            "You are a helpful English tutor for a Russian speaker. "
            "Always respond in English to help them practice. "
            "Keep your answers concise."
        )}
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
                        await websocket.send_json({"type": "transcript", "role": "assistant", "text": curr_sent})
                        await synthesize_and_send(curr_sent)
                        curr_sent = ""
            
            if curr_sent:
                await websocket.send_json({"type": "transcript", "role": "assistant", "text": curr_sent})
                await synthesize_and_send(curr_sent)
                
            conversation_history.append({"role": "assistant", "content": full_resp})
            
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
                    # Handle config/start events if needed
                    pass
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
