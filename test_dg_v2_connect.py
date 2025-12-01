import asyncio
from deepgram import DeepgramClient

async def test_connection():
    client = DeepgramClient(api_key="test_key")
    
    options = {
        "model": "nova-2",
        "language": "en-US",
        "smart_format": True,
    }
    
    print("Creating connection...")
    connection = client.listen.v2.connect(**options)
    
    print(f"Connection type: {type(connection)}")
    print(f"Connection dir: {[x for x in dir(connection) if not x.startswith('_')]}")
    
    # Check if it's an async context manager
    if hasattr(connection, '__aenter__'):
        print("✅ Has __aenter__ - is an async context manager")
    
    # Check if it has send/receive methods
    if hasattr(connection, 'send'):
        print("✅ Has send method")
    if hasattr(connection, 'on'):
        print("✅ Has on method")

asyncio.run(test_connection())
