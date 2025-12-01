
import deepgram
from deepgram import DeepgramClient
import inspect

client = DeepgramClient(api_key="test")
v2 = client.listen.v2
sig = inspect.signature(v2.connect)
print(f"Signature: {sig}")
