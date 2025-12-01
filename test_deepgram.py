
import sys
import traceback

print(f"Python version: {sys.version}")

try:
    import deepgram
    print(f"Deepgram imported. Version: {getattr(deepgram, '__version__', 'unknown')}")
    print(f"Deepgram file: {deepgram.__file__}")
    
    try:
        from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
        print("Successfully imported DeepgramClient, LiveTranscriptionEvents, LiveOptions from deepgram")
    except ImportError as e:
        print(f"Failed to import from top level: {e}")
        
        try:
            from deepgram.clients.live.v1 import LiveTranscriptionEvents
            print("Found LiveTranscriptionEvents in deepgram.clients.live.v1")
        except ImportError as e:
            print(f"Failed to import LiveTranscriptionEvents from v1: {e}")

        try:
            from deepgram.clients.live.v1 import LiveOptions
            print("Found LiveOptions in deepgram.clients.live.v1")
        except ImportError as e:
            print(f"Failed to import LiveOptions from v1: {e}")

except ImportError as e:
    print(f"Failed to import deepgram: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
    traceback.print_exc()
