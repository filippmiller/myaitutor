from deepgram import DeepgramClient

client = DeepgramClient(api_key="test_key")

print("=== v1.connect attributes ===")
attrs = [a for a in dir(client.listen.v1.connect) if not a.startswith('_')]
for attr in attrs:
    print(f"  {attr}")

# Check if there's websocket method
if hasattr(client.listen.v1.connect, 'websocket'):
    print("\n✅ v1.connect has websocket()")
    
if hasattr(client.listen.v1, 'websocket'):
    print("\n✅ v1 has websocket attribute")
    ws_attrs = [a for a in dir(client.listen.v1.websocket) if not a.startswith('_')]
    for attr in ws_attrs:
        print(f"     - {attr}")
