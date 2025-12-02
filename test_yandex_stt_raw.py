
import os
from dotenv import load_dotenv
import grpc
from yandex.cloud.ai.stt.v3 import stt_service_pb2, stt_service_pb2_grpc, stt_pb2
import time

load_dotenv()

def test_stt():
    key_id = os.getenv("YANDEX_KEY_ID")
    api_key = os.getenv("YANDEX_API_KEY")
    
    if not key_id or not api_key:
        print("❌ Missing Yandex credentials")
        return

    print(f"🔑 Testing Yandex STT Auth with Key ID: {key_id}")

    # Create channel
    channel = grpc.secure_channel(
        'stt.api.cloud.yandex.net:443',
        grpc.ssl_channel_credentials()
    )

    # Create stub
    stub = stt_service_pb2_grpc.RecognizerStub(channel)

    # Prepare request generator
    def gen():
        # 1. Session Options
        print("Sending options...")
        # WAV inspection showed: 22050 Hz, 1 channel, 16-bit (width 2)
        # Let's try specifying RAW AUDIO to avoid container issues
        
        yield stt_service_pb2.StreamingRequest(
            session_options=stt_pb2.StreamingOptions(
                recognition_model=stt_pb2.RecognitionModelOptions(
                    audio_format=stt_pb2.AudioFormatOptions(
                        raw_audio=stt_pb2.RawAudio(
                            audio_encoding=stt_pb2.RawAudio.LINEAR16_PCM,
                            sample_rate_hertz=22050,
                            audio_channel_count=1
                        )
                    ),
                    audio_processing_type=stt_pb2.RecognitionModelOptions.REAL_TIME
                )
            )
        )
        
        # 2. Audio Data
        print("Sending audio...")
        with open("test_yandex.wav", "rb") as f:
            # Skip header (44 bytes) for raw PCM
            f.seek(44)
            data = f.read()
            # Send in chunks
            chunk_size = 4000
            for i in range(0, len(data), chunk_size):
                yield stt_service_pb2.StreamingRequest(
                    chunk=stt_pb2.AudioChunk(data=data[i:i+chunk_size])
                )
                time.sleep(0.01)

    metadata = (
        ('authorization', f'Api-Key {api_key}'),
    )

    try:
        print("📡 Sending STT request...")
        it = stub.RecognizeStreaming(gen(), metadata=metadata)
        
        print("🎧 Listening for results...")
        for response in it:
            if response.HasField('final'):
                print(f"📝 Final: {response.final.alternatives[0].text}")
            elif response.HasField('partial'):
                pass
            elif response.HasField('status_code'):
                 print(f"Status: {response.status_code}")
        
        print("\n✅ STT Finished")

    except grpc.RpcError as e:
        print(f"❌ RPC Error: {e.code()} - {e.details()}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_stt()
