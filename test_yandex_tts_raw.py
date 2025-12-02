
import os
from dotenv import load_dotenv
import grpc
from yandex.cloud.ai.tts.v3 import tts_service_pb2, tts_service_pb2_grpc, tts_pb2

load_dotenv()

def test_tts_raw():
    key_id = os.getenv("YANDEX_KEY_ID")
    api_key = os.getenv("YANDEX_API_KEY")
    
    if not key_id or not api_key:
        print("❌ Missing Yandex credentials")
        return

    print(f"🔑 Testing Yandex TTS Raw with Key ID: {key_id}")

    channel = grpc.secure_channel(
        'tts.api.cloud.yandex.net:443',
        grpc.ssl_channel_credentials()
    )
    stub = tts_service_pb2_grpc.SynthesizerStub(channel)

    # Use tts_pb2 for options if needed, or tts_service_pb2 if they are there
    # Based on previous run, tts_pb2 has AudioFormatOptions
    
    # Try to find the request class
    RequestClass = getattr(tts_service_pb2, 'UtteranceSynthesisRequest', None)
    if not RequestClass:
        RequestClass = getattr(tts_pb2, 'UtteranceSynthesisRequest', None)
        
    if not RequestClass:
        print("❌ UtteranceSynthesisRequest not found")
        return

    request = RequestClass(
        text="Hello, this is a test of Yandex SpeechKit.",
        output_audio_spec=tts_pb2.AudioFormatOptions(
            raw_audio=tts_pb2.RawAudio(
                audio_encoding=tts_pb2.RawAudio.LINEAR16_PCM,
                sample_rate_hertz=48000
            )
        ),
        hints=[
            tts_pb2.Hints(voice=str("alena")),
            tts_pb2.Hints(role=str("good")),
        ],
        loudness_normalization_type=RequestClass.LUFS
    )

    metadata = (('authorization', f'Api-Key {api_key}'),)

    try:
        print("📡 Sending TTS request...")
        it = stub.UtteranceSynthesis(request, metadata=metadata)
        
        audio_data = b''
        for response in it:
            if response.audio_chunk.data:
                audio_data += response.audio_chunk.data
        
        print(f"✅ TTS Success! Received {len(audio_data)} bytes of audio.")
        with open("test_yandex_48k.pcm", "wb") as f:
            f.write(audio_data)
        print("💾 Saved to test_yandex_48k.pcm")

    except grpc.RpcError as e:
        print(f"❌ RPC Error: {e.code()} - {e.details()}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_tts_raw()
