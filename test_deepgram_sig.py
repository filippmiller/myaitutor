from deepgram import DeepgramClient

# Check what arguments DeepgramClient accepts
import inspect
print("DeepgramClient signature:")
print(inspect.signature(DeepgramClient.__init__))

# Try simple initialization
try:
    client = DeepgramClient(api_key="test_key")
    print("✅ Simple initialization works!")
except TypeError as e:
    print(f"❌ Simple initialization failed: {e}")

# Try with empty string and dict
try:
    client = DeepgramClient()
    print("✅ No-arg initialization works!")
except TypeError as e:
    print(f"❌ No-arg initialization failed: {e}")
