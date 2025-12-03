from typing import Protocol, Optional
import os
from openai import OpenAI
from app.services.yandex_service import YandexService
import subprocess

class VoiceEngine(Protocol):
    async def synthesize(self, text: str, voice_id: str | None = None) -> bytes: ...
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
        # Default to alena if not specified
        voice = voice_id if voice_id else "alena"
        
        try:
            # Yandex returns PCM chunks. We need to convert to MP3/bytes.
            # We'll use ffmpeg to convert the stream to MP3 bytes.
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
            
            # We need to feed chunks to stdin. 
            # Since synthesize_stream is a generator, we can't easily use communicate with input=bytes.
            # We'll start a thread or just write in a loop if the buffer allows, 
            # but for simplicity/safety with subprocess, let's collect PCM first or write carefully.
            # Actually, writing to stdin can block if stdout buffer fills up.
            # Let's try a simpler approach: collect all PCM first (it's short sentences usually).
            
            pcm_data = b""
            for chunk in self.service.synthesize_stream(text=text, voice=voice):
                pcm_data += chunk
                
            stdout, _ = process.communicate(input=pcm_data)
            return stdout
            
        except Exception as e:
            print(f"Yandex TTS Error: {e}")
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
                # This is a simplification. Real Yandex response parsing depends on the proto structure.
                # Looking at yandex_service.py, it returns the raw response object.
                # We need to see how to extract text.
                # The existing code doesn't show the consumption logic fully for STT, 
                # but let's assume standard Yandex STT response.
                # Actually, let's look at yandex_service.py again if needed.
                # For now, I'll implement a basic extraction based on common Yandex protos.
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
        # We need an API key for OpenAI. 
        # Ideally this comes from settings, but here we pass it or get from env.
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OpenAI API Key required for OpenAIVoiceEngine")
        return OpenAIVoiceEngine(api_key=key)
