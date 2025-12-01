
import deepgram
import inspect

print("Checking deepgram.types...")
try:
    import deepgram.types as types
    print(f"deepgram.types dir: {dir(types)}")
except Exception as e:
    print(f"Error checking deepgram.types: {e}")

try:
    from deepgram.types import LiveOptions
    print("Found LiveOptions in deepgram.types")
except ImportError:
    print("Not found in deepgram.types")
