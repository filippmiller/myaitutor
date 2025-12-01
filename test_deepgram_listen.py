from deepgram import DeepgramClient

client = DeepgramClient(api_key="test_key")

print("Client attributes:")
print(dir(client))

print("\nListen attributes:")
print(dir(client.listen))

print("\nListen type:")
print(type(client.listen))

# Check what methods/attributes are available
if hasattr(client.listen, 'websocket'):
    print("\n✅ Has websocket")
if hasattr(client.listen, 'asyncwebsocket'):
    print("\n✅ Has asyncwebsocket")
if hasattr(client.listen, 'live'):
    print("\n✅ Has live")
    print("Live type:", type(client.listen.live))
    print("Live dir:", dir(client.listen.live))
