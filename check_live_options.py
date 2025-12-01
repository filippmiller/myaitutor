
try:
    from deepgram import LiveOptions
    print("Imported LiveOptions from deepgram")
except ImportError:
    try:
        from deepgram.clients.live.v1 import LiveOptions
        print("Imported LiveOptions from deepgram.clients.live.v1")
    except ImportError:
        print("Could not import LiveOptions")
