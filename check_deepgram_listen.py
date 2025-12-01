
import deepgram
import inspect

print("Checking deepgram.listen...")
try:
    print(f"deepgram.listen type: {type(deepgram.listen)}")
    print(f"deepgram.listen dir: {dir(deepgram.listen)}")
except Exception as e:
    print(f"Error checking deepgram.listen: {e}")

try:
    from deepgram import LiveTranscriptionEvents
    print("Found LiveTranscriptionEvents in top level")
except ImportError:
    pass

try:
    from deepgram.listen import LiveTranscriptionEvents
    print("Found LiveTranscriptionEvents in deepgram.listen")
except ImportError:
    print("Not found in deepgram.listen")

try:
    from deepgram.listen.v1 import LiveTranscriptionEvents
    print("Found LiveTranscriptionEvents in deepgram.listen.v1")
except ImportError:
    print("Not found in deepgram.listen.v1")
