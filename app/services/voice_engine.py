from typing import Protocol, Optional, AsyncGenerator
import os
from openai import OpenAI
from app.services.yandex_service import YandexService
import subprocess
import asyncio

class VoiceEngine(Protocol):
    async def synthesize(self, text: str, voice_id: str | None = None) -> bytes: ...
    async def synthesize_stream(self, text: str, voice_id: str | None = None) -> AsyncGenerator[bytes, None]: ...
    async def transcribe(self, audio_bytes: bytes) -> str: ...

class OpenAIVoiceEngine:
    def __init__(self, api_key: str, tts_model: str = "tts-1", stt_model: str = "whisper-1"):
        self.client = OpenAI(api_key=api_key)
        self.tts_model = tts_model
        self.stt_model = stt_model

    async def synthesize(self, text: str, voice_id: str | None = None) -> bytes:
        # Default to alloy if not specified or invalid
        valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        voice = voice_id if voice_id in valid_voices else "alloy"
        
        try:
            response = self.client.audio.speech.create(
                model=self.tts_model,
                voice=voice,
                input=text
            )
            return response.content
        except Exception as e:
            print(f"OpenAI TTS Error: {e}")
            raise e

    async def synthesize_stream(self, text: str, voice_id: str | None = None) -> AsyncGenerator[bytes, None]:
        valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        voice = voice_id if voice_id in valid_voices else "alloy"
        
        try:
            # Use the streaming helper
            with self.client.audio.speech.with_streaming_response.create(
                model=self.tts_model,
                voice=voice,
                input=text,
                response_format="mp3"
            ) as response:
                for chunk in response.iter_bytes(chunk_size=4096):
                    if chunk:
                        yield chunk
                        # Yield control to event loop to allow sending
                        await asyncio.sleep(0)
        except Exception as e:
            print(f"OpenAI TTS Stream Error: {e}")
            raise e

    async def transcribe(self, audio_bytes: bytes) -> str:
        # OpenAI requires a file-like object with a name
        import io
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.webm" # Assume webm from frontend
        
        try:
            transcription = self.client.audio.transcriptions.create(
                model=self.stt_model,
                file=audio_file
            )
            return transcription.text
        except Exception as e:
            print(f"OpenAI STT Error: {e}")
            raise e

class YandexVoiceEngine:
    def __init__(self):
        self.service = YandexService()

    async def synthesize(self, text: str, voice_id: str | None = None) -> bytes:
        # Reuse stream implementation
        chunks = []
        async for chunk in self.synthesize_stream(text, voice_id):
            chunks.append(chunk)
        return b"".join(chunks)

    async def synthesize_stream(self, text: str, voice_id: str | None = None) -> AsyncGenerator[bytes, None]:
        voice = voice_id if voice_id else "alena"
        
        try:
            # Start ffmpeg process to convert PCM stream to MP3 stream
            process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-f", "s16le", "-ar", "48000", "-ac", "1", "-i", "pipe:0",
                    "-f", "mp3",
                    "pipe:1"
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            
            loop = asyncio.get_running_loop()
            
            # Queue for chunks to write to ffmpeg
            # We need a separate task to write to stdin because reading from stdout blocks
            
            async def writer():
                try:
                    for pcm_chunk in self.service.synthesize_stream(text=text, voice=voice):
                        # Write to ffmpeg stdin
                        # This is blocking IO in a thread executor
                        await loop.run_in_executor(None, process.stdin.write, pcm_chunk)
                    await loop.run_in_executor(None, process.stdin.close)
                except Exception as e:
                    print(f"Yandex Writer Error: {e}")
                    try: process.stdin.close()
                    except: pass

            asyncio.create_task(writer())
            
            # Read from stdout
            while True:
                # Read small chunks
                chunk = await loop.run_in_executor(None, process.stdout.read, 4096)
                if not chunk:
                    break
                yield chunk
            
            process.wait()
            
        except Exception as e:
            print(f"Yandex TTS Stream Error: {e}")
            raise e

    async def transcribe(self, audio_bytes: bytes) -> str:
        # Yandex STT expects PCM usually, or OGG/OPUS. 
        # Our frontend sends WebM (Opus). Yandex might accept it directly or need conversion.
        # The existing YandexService.recognize_stream expects PCM chunks.
        # So we convert WebM -> PCM first.
        
        try:
            process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-i", "pipe:0",
                    "-f", "s16le", "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "1",
                    "pipe:1"
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            pcm_data, _ = process.communicate(input=audio_bytes)
            
            # Now stream to Yandex
            # We need a generator for chunks
            def chunk_generator(data, chunk_size=4096):
                for i in range(0, len(data), chunk_size):
                    yield data[i:i+chunk_size]
            
            # recognize_stream returns a gRPC response iterator. 
            # We need to extract text.
            full_text = ""
            for response in self.service.recognize_stream(chunk_generator(pcm_data)):
                if response.chunks:
                    full_text += response.chunks[0].alternatives[0].text
            
            return full_text
            
        except Exception as e:
            print(f"Yandex STT Error: {e}")
            raise e

def get_voice_engine(engine_name: str, api_key: str | None = None) -> VoiceEngine:
    if engine_name == "yandex":
        return YandexVoiceEngine()
    else:
        # Default to OpenAI
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OpenAI API Key required for OpenAIVoiceEngine")
        return OpenAIVoiceEngine(api_key=key)
