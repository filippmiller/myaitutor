
import asyncio
import json
import logging
import uuid
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import AppSettings, UserAccount, UserProfile
# from app.api.deps import get_current_user_ws # Removed - file doesn't exist yet
# from app.services.openai_service import OpenAIService # Not a class, just functions
from app.services.yandex_service import YandexService, AudioConverter

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
    
    # Manually create session
    from app.database import engine
    session = Session(engine)
    
    converter = None
    
    try:
        # 1. Load Settings
        try:
            settings = session.exec(select(AppSettings)).first()
            if not settings or not settings.openai_api_key:
                logger.error("OpenAI API Key missing in settings")
                await websocket.send_json({"type": "system", "level": "error", "message": "OpenAI API Key missing. Please configure it in settings."})
                # Don't close immediately, let user see error
        except Exception as e:
            logger.error(f"Database error loading settings: {e}")
            await websocket.close(code=1011, reason="Database error")
            return

        # 2. Initialize Services
        try:
            # Check for ffmpeg first
            import shutil
            ffmpeg_path = shutil.which("ffmpeg")
            if not ffmpeg_path:
                logger.error("ffmpeg not found in system path")
                await websocket.close(code=1011, reason="Server configuration error: ffmpeg missing")
                return
            logger.info(f"ffmpeg found at: {ffmpeg_path}")

            logger.info("Initializing YandexService...")
            yandex_service = YandexService()
            logger.info("YandexService initialized")
            
            converter = AudioConverter()
            logger.info("AudioConverter initialized")
            
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            await websocket.close(code=1011, reason=f"Configuration error: {str(e)}")
            return
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}", exc_info=True)
            await websocket.close(code=1011, reason=f"Service init failed: {str(e)}")
            return

        # 3. State
        conversation_history = [
            {"role": "system", "content": "You are a helpful English tutor for a Russian speaker. Keep your answers concise and helpful."}
        ]
        stt_language = "ru-RU" # Default
        
        # Helpers
        async def synthesize_and_send(text: str):
            try:
                logger.info(f"Starting TTS for: {text[:30]}...")
                loop = asyncio.get_event_loop()
                def run_tts():
                    return list(yandex_service.synthesize_stream(text))
                
                audio_chunks = await loop.run_in_executor(None, run_tts)
                if not audio_chunks:
                    return

                # WAV Header helper
                import struct
                def add_wav_header(pcm_data, sample_rate=48000, channels=1, sampwidth=2):
                    header = b'RIFF' + struct.pack('<I', 36 + len(pcm_data)) + b'WAVE' + \
                             b'fmt ' + struct.pack('<I', 16) + struct.pack('<HHIIHH', 1, channels, sample_rate, sample_rate * channels * sampwidth, channels * sampwidth, sampwidth * 8) + \
                             b'data' + struct.pack('<I', len(pcm_data))
                    return header + pcm_data

                full_audio = b''.join(audio_chunks)
                wav_audio = add_wav_header(full_audio)
                await websocket.send_bytes(wav_audio)
            except Exception as e:
                logger.error(f"TTS Error: {e}")
                await websocket.send_json({"type": "system", "level": "error", "message": "TTS Error"})

        async def generate_greeting():
            try:
                logger.info("Generating greeting...")
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=settings.openai_api_key)
                
                system_prompt = (
                    "You are an English tutor speaking to a student named Filipp. "
                    "Generate a friendly, short greeting in Russian that invites him to practice English. "
                    "Vary your wording every time. Do not be repetitive."
                )
                
                completion = await client.chat.completions.create(
                    model=settings.default_model,
                    messages=[{"role": "system", "content": system_prompt}]
                )
                greeting = completion.choices[0].message.content
                
                # Send transcript
                await websocket.send_json({"type": "transcript", "role": "assistant", "text": greeting})
                
                # Add to history
                conversation_history.append({"role": "assistant", "content": greeting})
                
                # Speak
                await synthesize_and_send(greeting)
                
            except Exception as e:
                logger.error(f"Greeting Error: {e}")
                await websocket.send_json({"type": "system", "level": "error", "message": "Failed to generate greeting (OpenAI Error)."})

        async def process_user_text(text: str):
            # 1. Send transcript
            await websocket.send_json({"type": "transcript", "role": "user", "text": text})
            
            # 2. LLM
            conversation_history.append({"role": "user", "content": text})
            
            llm_response = ""
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=settings.openai_api_key)
                completion = await client.chat.completions.create(
                    model=settings.default_model,
                    messages=conversation_history
                )
                llm_response = completion.choices[0].message.content
            except Exception as e:
                logger.error(f"LLM Error: {e}")
                await websocket.send_json({"type": "system", "level": "error", "message": "Brain connection failed (OpenAI Error)."})
                return

            conversation_history.append({"role": "assistant", "content": llm_response})
            await websocket.send_json({"type": "transcript", "role": "assistant", "text": llm_response})
            
            # 3. TTS
            await synthesize_and_send(llm_response)

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
                            # Run blocking write in executor to avoid freezing main loop
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

        async def stt_loop():
            def audio_generator():
                logger.info("Starting audio_generator")
                while True:
                    if not converter:
                        break
                    chunk = converter.read(4000)
                    if not chunk:
                        if converter.process.poll() is not None:
                            logger.info("Converter process finished")
                            break
                        time.sleep(0.01)
                        continue
                    yield chunk
                logger.info("audio_generator finished")

            try:
                loop = asyncio.get_event_loop()
                def run_sync_stt():
                    try:
                        logger.info(f"Starting recognize_stream with lang={stt_language}")
                        responses = yandex_service.recognize_stream(audio_generator(), language_code=stt_language)
                        for response in responses:
                            for chunk in response.chunks:
                                if chunk.final:
                                    text = chunk.alternatives[0].text
                                    if text:
                                        logger.info(f"STT Final: {text}")
                                        asyncio.run_coroutine_threadsafe(process_user_text(text), loop)
                        logger.info("recognize_stream finished successfully")
                    except Exception as e:
                        logger.error(f"Yandex STT Error: {e}")
                    except BaseException as e:
                        logger.critical(f"Yandex STT CRITICAL Error: {e}", exc_info=True)
                
                await loop.run_in_executor(None, run_sync_stt)
            except Exception as e:
                logger.error(f"Error in stt_loop: {e}")

        # Start loops
        receive_task = asyncio.create_task(receive_loop())
        stt_task = asyncio.create_task(stt_loop())

        await asyncio.gather(receive_task, stt_task)
        
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Main loop error: {e}", exc_info=True)
    except BaseException as e:
        logger.critical(f"Main loop CRITICAL error: {e}", exc_info=True)
    finally:
        logger.info("Cleaning up resources...")
        if converter:
            converter.close()
        session.close()
        logger.info("Cleanup complete")

@router.get("/health")
def health_check():
    return {"status": "ok", "provider": "yandex"}
