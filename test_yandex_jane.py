import os
from app.services.yandex_service import YandexService
import subprocess

def test_jane():
    print("Testing Yandex TTS with voice 'jane'...")
    try:
        service = YandexService()
        text = "Hello, this is a test of the Jane voice."
        
        output_file = "test_jane.mp3"
        
        process = subprocess.Popen(
            [
                "ffmpeg",
                "-f", "s16le", "-ar", "48000", "-ac", "1", "-i", "pipe:0",
                "-y",
                output_file
            ],
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE # Capture stderr to see ffmpeg errors
        )
        
        for chunk in service.synthesize_stream(text=text, voice="jane"):
            try:
                process.stdin.write(chunk)
            except BrokenPipeError:
                print("Broken pipe writing to ffmpeg")
                break
        
        process.stdin.close()
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            print(f"ffmpeg failed with code {process.returncode}")
            print(f"stderr: {stderr.decode()}")
        else:
            print(f"Success! Saved to {output_file}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_jane()
