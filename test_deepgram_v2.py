from deepgram import DeepgramClient
import inspect

client = DeepgramClient(api_key="test_key")

print("=== Testing connection methods ===")

# Try v1.connect
try:
    print("\nTrying client.listen.v1.connect...")
    print(f"Type: {type(client.listen.v1.connect)}")
    print(f"Signature: {inspect.signature(client.listen.v1.connect)}")
    print("✅ v1.connect exists and is callable")
except Exception as e:
    print(f"❌ Error: {e}")

# Try v2.connect  
try:
    print("\nTrying client.listen.v2.connect...")
    print(f"Type: {type(client.listen.v2.connect)}")
    print(f"Signature: {inspect.signature(client.listen.v2.connect)}")
    print("✅ v2.connect exists and is callable")
except Exception as e:
    print(f"❌ Error: {e}")
