
import deepgram
from deepgram import DeepgramClient
import inspect

client = DeepgramClient(api_key="test")
v2 = client.listen.v2
print(f"v2: {v2}")
print(f"v2 dir: {dir(v2)}")

if hasattr(v2, 'connect'):
    print(f"v2.connect: {v2.connect}")
    print(f"v2.connect signature: {inspect.signature(v2.connect)}")
