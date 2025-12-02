
import os
from dotenv import load_dotenv
import grpc
from yandex.cloud.ai.tts.v3 import tts_service_pb2, tts_service_pb2_grpc, tts_pb2

load_dotenv()

def test_tts():
    key_id = os.getenv("YANDEX_KEY_ID")
    api_key = os.getenv("YANDEX_API_KEY")
    
    if not key_id or not api_key:
        print("❌ Missing Yandex credentials")
        return

    print(f"🔑 Testing Yandex Auth with Key ID: {key_id}")

    # Create channel
    channel = grpc.secure_channel(
        'tts.api.cloud.yandex.net:443',
        grpc.ssl_channel_credentials()
    )

    # Create stub
    stub = tts_service_pb2_grpc.SynthesizerStub(channel)

    # Request structure seems to be in tts_pb2 based on import pattern
    # Let's check tts_pb2
    print(f"Dir of tts_pb2: {dir(tts_pb2)}")

    if not hasattr(tts_service_pb2, 'UtteranceSynthesisRequest'):
         # It might be in tts_service_pb2 but imported differently or named differently in this version
         # Actually, usually request messages are in the service proto or a separate messages proto.
         # In yandex-cloud-python, it's often in tts_service_pb2 OR tts_pb2.
         pass

    # Try to construct request using tts_service_pb2 if available, else tts_pb2
    RequestClass = getattr(tts_service_pb2, 'UtteranceSynthesisRequest', None)
    if not RequestClass:
        RequestClass = getattr(tts_pb2, 'UtteranceSynthesisRequest', None)
        
    if not RequestClass:
        print("❌ UtteranceSynthesisRequest not found in pb2 or service_pb2")
        return

    # AudioFormatOptions might be in tts_pb2
    AudioFormatOptions = getattr(tts_pb2, 'AudioFormatOptions', None)
    ContainerAudio = getattr(tts_pb2, 'ContainerAudio', None)
    Hints = getattr(tts_pb2, 'Hints', None)

    request = RequestClass(
        text="Hello, this is a test.",
        output_audio_spec=AudioFormatOptions(
            container_audio=ContainerAudio(
                container_audio_type=ContainerAudio.WAV
            )
        ),
        hints=[
            Hints(voice=str("alena")),
            Hints(role=str("good")),
        ],
        loudness_normalization_type=RequestClass.LUFS
    )

    metadata = (
        ('authorization', f'Api-Key {api_key}'),
    )

    try:
        print("📡 Sending TTS request...")
        it = stub.UtteranceSynthesis(request, metadata=metadata)
        
        audio_data = b''
        for response in it:
            if response.audio_chunk.data:
                audio_data += response.audio_chunk.data
        
        print(f"✅ TTS Success! Received {len(audio_data)} bytes of audio.")
        with open("test_yandex.wav", "wb") as f:
            f.write(audio_data)
        print("💾 Saved to test_yandex.wav")

    except grpc.RpcError as e:
        print(f"❌ RPC Error: {e.code()} - {e.details()}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_tts()
