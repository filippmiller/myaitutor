import inspect
from deepgram import DeepgramClient

client = DeepgramClient(api_key="test_key")

print("v2.connect signature:")
print(inspect.signature(client.listen.v2.connect))
