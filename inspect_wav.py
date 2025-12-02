
import wave

try:
    with wave.open("test_yandex.wav", "rb") as wf:
        print(f"Channels: {wf.getnchannels()}")
        print(f"Sample width: {wf.getsampwidth()}")
        print(f"Frame rate: {wf.getframerate()}")
        print(f"Frames: {wf.getnframes()}")
        print(f"Duration: {wf.getnframes() / wf.getframerate()}s")
        print(f"Compression type: {wf.getcomptype()} ({wf.getcompname()})")
except Exception as e:
    print(f"Error reading WAV: {e}")
