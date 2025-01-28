import asyncio
import json
import logging
from modal import Image, Stub, asgi_app
from fastapi import FastAPI
import uvicorn
from relay_server import RealtimeRelay, create_ephemeral_token

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

from fastapi import WebSocket, WebSocketDisconnect
from typing import List

# Keep track of active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

manager = ConnectionManager()

@web_app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            event = json.loads(data)
            
            # Handle session initialization
            if event.get("type") == "init_session":
                # Test connection at startup
                await test_connection()
                
            # Forward event to client
            await websocket.send_text(json.dumps(event))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in manager.active_connections:
            manager.disconnect(websocket)

@app.function(
    image=image,
    keep_warm=1,
    allow_concurrent_inputs=True  # Allow multiple WebSocket connections
)
@asgi_app(label="realtime-relay")
def fastapi_app():
    return web_app

if __name__ == "__main__":
    app.serve()
