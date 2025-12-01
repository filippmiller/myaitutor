from deepgram import DeepgramClient

client = DeepgramClient(api_key="test_key")

print("=== Listen attributes ===")
attrs = [a for a in dir(client.listen) if not a.startswith('_')]
for attr in attrs:
    print(f"  {attr}")

print("\n=== Checking specific attributes ===")
if hasattr(client.listen, 'websocket'):
    print("✅ Has websocket")
    print(f"   Type: {type(client.listen.websocket)}")
    
if hasattr(client.listen, 'asyncwebsocket'):
    print("✅ Has asyncwebsocket")
    
if hasattr(client.listen, 'live'):
    print("✅ Has live")
    print(f"   Type: {type(client.listen.live)}")
    
if hasattr(client.listen, 'v1'):
    print("✅ Has v1")
    print(f"   Type: {type(client.listen.v1)}")
    v1_attrs = [a for a in dir(client.listen.v1) if not a.startswith('_')]
    for attr in v1_attrs:
        print(f"     - {attr}")
