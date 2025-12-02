
import os
import grpc
from yandex.cloud.ai.stt.v2 import stt_service_pb2, stt_service_pb2_grpc
from yandex.cloud.ai.tts.v3 import tts_service_pb2, tts_service_pb2_grpc, tts_pb2
import subprocess
import threading
import queue

class YandexService:
    def __init__(self):
        self.key_id = os.getenv("YANDEX_KEY_ID")
        self.api_key = os.getenv("YANDEX_API_KEY")
        self.folder_id = os.getenv("YANDEX_FOLDER_ID") # Might be needed for v3, but API key usually suffices
        
        if not self.api_key:
            raise ValueError("YANDEX_API_KEY not found")

        self.ssl_creds = grpc.ssl_channel_credentials()
        
        # STT Channel
        self.stt_channel = grpc.secure_channel('stt.api.cloud.yandex.net:443', self.ssl_creds)
        self.stt_stub = stt_service_pb2_grpc.SttServiceStub(self.stt_channel)
        
        # TTS Channel
        self.tts_channel = grpc.secure_channel('tts.api.cloud.yandex.net:443', self.ssl_creds)
        self.tts_stub = tts_service_pb2_grpc.SynthesizerStub(self.tts_channel)

    def synthesize_stream(self, text: str, voice: str = "alena", role: str = "good"):
        # Try to find the request class dynamically as before
        RequestClass = getattr(tts_service_pb2, 'UtteranceSynthesisRequest', None)
        if not RequestClass:
            RequestClass = getattr(tts_pb2, 'UtteranceSynthesisRequest', None)
            
        if not RequestClass:
            raise ImportError("Could not find UtteranceSynthesisRequest")

        request = RequestClass(
            text=text,
            output_audio_spec=tts_pb2.AudioFormatOptions(
                raw_audio=tts_pb2.RawAudio(
                    audio_encoding=tts_pb2.RawAudio.LINEAR16_PCM,
                    sample_rate_hertz=48000
                )
            ),
            hints=[
                tts_pb2.Hints(voice=str(voice)),
                tts_pb2.Hints(role=str(role)),
            ],
            loudness_normalization_type=RequestClass.LUFS
        )

        metadata = (('authorization', f'Api-Key {self.api_key}'),)
        
        it = self.tts_stub.UtteranceSynthesis(request, metadata=metadata)
        for response in it:
            if response.audio_chunk.data:
                yield response.audio_chunk.data

    def recognize_stream(self, audio_generator, language_code='ru-RU'):
        """
        audio_generator: iterator yielding bytes (PCM 48k, 1ch, 16bit)
        """
        def request_gen():
            # Config message
            config = stt_service_pb2.RecognitionConfig(
                specification=stt_service_pb2.RecognitionSpec(
                    language_code=language_code, # Target language
                    profanity_filter=True,
                    model='general',
                    partial_results=True,
                    audio_encoding='LINEAR16_PCM',
                    sample_rate_hertz=48000,
                    audio_channel_count=1
                )
            )
            yield stt_service_pb2.StreamingRecognitionRequest(config=config)
            
            # Audio chunks
            for chunk in audio_generator:
                yield stt_service_pb2.StreamingRecognitionRequest(audio_content=chunk)

        metadata = (('authorization', f'Api-Key {self.api_key}'),)
        
        return self.stt_stub.StreamingRecognize(request_gen(), metadata=metadata)

class AudioConverter:
    """
    Converts WebM stream to PCM 48kHz 16bit mono using ffmpeg.
    """
    def __init__(self):
        import shutil
        if not shutil.which("ffmpeg"):
            raise FileNotFoundError("ffmpeg not found. Please install ffmpeg.")

        self.process = subprocess.Popen(
            [
                "ffmpeg",
                "-i", "pipe:0",           # Read from stdin
                "-f", "s16le",            # Output format: signed 16-bit little endian
                "-acodec", "pcm_s16le",   # Audio codec
                "-ar", "48000",           # Sample rate
                "-ac", "1",               # Channels: mono
                "pipe:1"                  # Write to stdout
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, # Suppress stderr
            bufsize=0 # Unbuffered
        )
        
    def write(self, data):
        if self.process.stdin:
            try:
                self.process.stdin.write(data)
                self.process.stdin.flush()
            except (BrokenPipeError, ValueError):
                pass

    def read(self, chunk_size=4096):
        if self.process.stdout:
            try:
                return self.process.stdout.read(chunk_size)
            except ValueError: # I/O operation on closed file
                return b''
        return b''

    def close_stdin(self):
        """Signal EOF to ffmpeg so it can finish processing and close stdout naturally."""
        if self.process.stdin:
            try:
                self.process.stdin.close()
            except (BrokenPipeError, ValueError):
                pass

    def close(self):
        """Force close everything."""
        if self.process.stdin:
            try:
                self.process.stdin.close()
            except (BrokenPipeError, ValueError):
                pass
        if self.process.stdout:
            try:
                self.process.stdout.close()
            except (BrokenPipeError, ValueError):
                pass
        self.process.terminate()
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.process.kill()

