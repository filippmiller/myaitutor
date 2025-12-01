
import deepgram
from deepgram import DeepgramClient
import inspect

print(f"Deepgram version: {deepgram.__version__}")

try:
    client = DeepgramClient(api_key="test")
    print(f"Client: {client}")
    print(f"Client dir: {dir(client)}")
    
    if hasattr(client, 'listen'):
        print(f"client.listen: {client.listen}")
        print(f"client.listen dir: {dir(client.listen)}")
        
        if hasattr(client.listen, 'v2'):
             print("client.listen.v2 exists")
        else:
             print("client.listen.v2 DOES NOT exist")

        if hasattr(client.listen, 'live'):
             print("client.listen.live exists")
             print(f"client.listen.live dir: {dir(client.listen.live)}")
             if hasattr(client.listen.live, 'v'):
                 print("client.listen.live.v exists")

except Exception as e:
    print(f"Error: {e}")
