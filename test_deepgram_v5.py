from deepgram import DeepgramClient, DeepgramClientOptions

print(f"DeepgramClient: {DeepgramClient}")
print(f"DeepgramClientOptions: {DeepgramClientOptions}")

# Test initialization
try:
    config = DeepgramClientOptions(api_key="test_key")
    client = DeepgramClient("", config)
    print("✅ Initialization successful")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
