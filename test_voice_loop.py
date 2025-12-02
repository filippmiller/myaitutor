import asyncio
import websockets
import json
import sys

async def test_voice_loop():
    uri = "ws://localhost:8000/api/ws/voice"
    async with websockets.connect(uri) as websocket:
        print(f"Connected to {uri}")

        # 1. Send Config
        await websocket.send(json.dumps({"type": "config", "stt_language": "en-US"}))
        print("Sent config")

        # 2. Send Lesson Started
        await websocket.send(json.dumps({"type": "system_event", "event": "lesson_started"}))
        print("Sent lesson_started")

        # 3. Listen for messages
        try:
            while True:
                message = await websocket.recv()
                if isinstance(message, str):
                    data = json.loads(message)
                    print(f"Received JSON: {data}")
                    if data.get("type") == "transcript" and data.get("role") == "assistant":
                        print("Assistant spoke!")
                else:
                    print(f"Received Audio: {len(message)} bytes")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed: {e.code} {e.reason}")

if __name__ == "__main__":
    try:
        asyncio.run(test_voice_loop())
    except KeyboardInterrupt:
        pass
