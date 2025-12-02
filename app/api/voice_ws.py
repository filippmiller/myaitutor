
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
async def voice_websocket(
    websocket: WebSocket,
    # session: Session = Depends(get_session), # Remove dependency to avoid pre-handler failures
):
    await websocket.accept()
    logger.info(f"WebSocket connection accepted from {websocket.client}")
    
    # Manually create session
    from app.database import engine
    session = Session(engine)
    
    # Define variables outside try to ensure finally works
    converter = None
    
    try:
        # 1. Load Settings
        try:
            settings = session.exec(select(AppSettings)).first()
            if not settings or not settings.openai_api_key:
                logger.error("OpenAI API Key missing in settings")
                await websocket.close(code=1008, reason="OpenAI API Key missing")
                return
        except Exception as e:
            logger.error(f"Database error loading settings: {e}")
            await websocket.close(code=1011, reason="Database error")
            return

        # 2. Initialize Services
        try:
            # Check for ffmpeg first
            import shutil
            if not shutil.which("ffmpeg"):
                logger.error("ffmpeg not found in system path")
                await websocket.close(code=1011, reason="Server configuration error: ffmpeg missing")
                return

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
        
        # Queues for async processing
        audio_queue = asyncio.Queue()
        
        async def receive_audio_loop():
            try:
                while True:
                    data = await websocket.receive_bytes()
                    if not data:
                        break
                    # Write to converter
                    if converter:
                        converter.write(data)
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.error(f"Error in receive_loop: {e}")
            finally:
                if converter:
                    converter.close()

        async def stt_loop():
            """Reads from converter stdout and sends to Yandex STT"""
            def audio_generator():
                while True:
                    if not converter:
                        break
                    # Read converted PCM data
                    chunk = converter.read(4000)
                    if not chunk:
                        # If process is dead or no data, check if we should stop
                        if converter.process.poll() is not None:
                            break
                        time.sleep(0.01)
                        continue
                    yield chunk

            try:
                # Since my YandexService uses sync gRPC, I must run it in a thread to not block the event loop.
                loop = asyncio.get_event_loop()
                
                # Wrapper to run the sync loop
                def run_sync_stt():
                    responses = yandex_service.recognize_stream(audio_generator())
                    for response in responses:
                        for chunk in response.chunks:
                            if chunk.final:
                                text = chunk.alternatives[0].text
                                if text:
                                    logger.info(f"STT Final: {text}")
                                    asyncio.run_coroutine_threadsafe(process_user_text(text), loop)
                
                await loop.run_in_executor(None, run_sync_stt)
                
            except Exception as e:
                logger.error(f"Error in stt_loop: {e}")

        async def process_user_text(text: str):
            """Handle recognized text: Send to LLM -> TTS -> Client"""
            # 1. Send user text to client (transcript)
            await websocket.send_json({"type": "transcript", "role": "user", "text": text})
            
            # 2. LLM
            conversation_history.append({"role": "user", "content": text})
            
            llm_response = ""
            try:
                import openai
                client = openai.OpenAI(api_key=settings.openai_api_key)
                completion = client.chat.completions.create(
                    model=settings.default_model,
                    messages=conversation_history
                )
                llm_response = completion.choices[0].message.content
            except Exception as e:
                logger.error(f"LLM Error: {e}")
                return

            conversation_history.append({"role": "assistant", "content": llm_response})
            await websocket.send_json({"type": "transcript", "role": "assistant", "text": llm_response})
            
            # 3. TTS
            try:
                # Run TTS generation in executor
                loop = asyncio.get_event_loop()
                def run_tts():
                    return list(yandex_service.synthesize_stream(llm_response))
                
                audio_chunks = await loop.run_in_executor(None, run_tts)
                
                # Helper to add WAV header
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

        # Start loops
        receive_task = asyncio.create_task(receive_audio_loop())
        stt_task = asyncio.create_task(stt_loop())

        await asyncio.gather(receive_task, stt_task)
        
    except Exception as e:
        logger.error(f"Main loop error: {e}")
    finally:
        if converter:
            converter.close()
        session.close()

@router.get("/health")
def health_check():
    return {"status": "ok", "provider": "yandex"}
