from modal import Image, Stub, asgi_app
from fastapi import FastAPI
import uvicorn

# Create FastAPI app with WebSocket support
web_app = FastAPI()

# Create Modal app and image
app = Stub("realtime-relay", shared_volumes={})
image = (
    Image.debian_slim()
    .pip_install(["fastapi", "uvicorn", "websockets", "requests"])
)

async def test_connection():
    """Test connection to OpenAI Realtime API"""
    logger.info("Testing connection to OpenAI Realtime API...")
    try:
        # Create minimal session config for test
        test_config = {
            "model": "gpt-4",
            "modalities": ["text"]
        }
        token = create_ephemeral_token(test_config)
        relay = RealtimeRelay(token, test_config)
        await relay.connect_upstream()
        await relay.close()
        logger.info("✓ Connection test successful")
        return True
    except Exception as e:
        logger.error(f"✗ Connection test failed: {e}")
        return False

@app.function(
    image=image,
    keep_warm=1
)
@asgi_app(label="realtime-relay")
def fastapi_app():
    # Test connection at startup
    asyncio.run(test_connection())
    return web_app

if __name__ == "__main__":
    app.serve()
