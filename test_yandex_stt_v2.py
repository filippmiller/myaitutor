
import os
from dotenv import load_dotenv
import grpc
from yandex.cloud.ai.stt.v2 import stt_service_pb2, stt_service_pb2_grpc

load_dotenv()

def test_stt_v2():
    key_id = os.getenv("YANDEX_KEY_ID")
    api_key = os.getenv("YANDEX_API_KEY")
    
    if not key_id or not api_key:
        print("❌ Missing Yandex credentials")
        return

    print(f"🔑 Testing Yandex STT v2 Auth with Key ID: {key_id}")

    # Create channel
    channel = grpc.secure_channel(
        'stt.api.cloud.yandex.net:443',
        grpc.ssl_channel_credentials()
    )

    # Create stub
    stub = stt_service_pb2_grpc.SttServiceStub(channel)

    # Prepare request generator
    def gen():
        # v2 sends config in the first message
        config = stt_service_pb2.RecognitionConfig(
            specification=stt_service_pb2.RecognitionSpec(
                language_code='en-US',
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
        with open("test_yandex_48k.pcm", "rb") as f:
            # No header to skip for raw PCM
            data = f.read()
            chunk_size = 4000
            for i in range(0, len(data), chunk_size):
                yield stt_service_pb2.StreamingRecognitionRequest(
                    audio_content=data[i:i+chunk_size]
                )
                time.sleep(0.01)

    metadata = (
        ('authorization', f'Api-Key {api_key}'),
    )

    try:
        print("📡 Sending STT v2 request...")
        it = stub.StreamingRecognize(gen(), metadata=metadata)
        
        print("🎧 Listening for results...")
        for response in it:
            for chunk in response.chunks:
                if chunk.final:
                    print(f"📝 Final: {chunk.alternatives[0].text}")
                else:
                    pass # print(f"Partial: {chunk.alternatives[0].text}", end='\r')
        
        print("\n✅ STT v2 Finished")

    except grpc.RpcError as e:
        print(f"❌ RPC Error: {e.code()} - {e.details()}")
    except Exception as e:
        print(f"❌ Error: {e}")

import time
if __name__ == "__main__":
    test_stt_v2()
