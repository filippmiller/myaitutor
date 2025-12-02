
import asyncio
import websockets
import sys

async def test_ws():
    uri = "ws://localhost:8000/api/ws/voice"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            await websocket.send(b"test")
            print("Sent data")
            response = await websocket.recv()
            print(f"Received: {response}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(test_ws())
    except ImportError:
        print("websockets not installed. Please install it with: pip install websockets")
