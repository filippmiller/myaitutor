
import deepgram
import inspect

print(f"Deepgram version: {getattr(deepgram, '__version__', 'unknown')}")

print("\nTop level attributes of deepgram module:")
for name in dir(deepgram):
    if not name.startswith("_"):
        print(f" - {name}")

try:
    from deepgram import DeepgramClient
    print("\nDeepgramClient imported successfully.")
except ImportError:
    print("\nDeepgramClient NOT found in top level.")

try:
    from deepgram import LiveTranscriptionEvents
    print("LiveTranscriptionEvents imported successfully.")
except ImportError:
    print("LiveTranscriptionEvents NOT found in top level.")

try:
    from deepgram import LiveOptions
    print("LiveOptions imported successfully.")
except ImportError:
    print("LiveOptions NOT found in top level.")
