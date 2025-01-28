import asyncio
import json
import logging
import uuid
from datetime import datetime
from modal import Image, App, asgi_app
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
web_app = FastAPI(
    title="Realtime Relay",
    description="WebSocket relay for realtime communication",
    version="1.0.0"
)

@web_app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "websocket_path": "/ws"}

# Create Modal app and image
app = App("realtime-relay")
image = (
    Image.debian_slim()
    .pip_install(["fastapi", "uvicorn", "websockets>=12.0", "requests", "python-multipart"])
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
    """Handle WebSocket connections with proper lifecycle management"""
    try:
        await websocket.accept()
        logger.info("New WebSocket connection accepted")
        
        # Send immediate connection acknowledgment
        await websocket.send_text(json.dumps({
            "type": "connection.established",
            "timestamp": str(datetime.now())
        }))
        
        while True:
            try:
                # Use shorter timeout to maintain connection
                data = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
                event = json.loads(data)
                
                # Handle session initialization
                if event.get("type") == "init_session":
                    # Test connection at startup
                    connection_ok = await test_connection()
                    if connection_ok:
                        logger.info("Session initialized successfully")
                        await websocket.send_text(json.dumps({
                            "type": "session.created",
                            "session_id": str(uuid.uuid4()),
                            "status": "ready"
                        }))
                    else:
                        logger.error("Failed to initialize session")
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "error": {
                                "code": "session_init_failed",
                                "message": "Failed to establish OpenAI connection"
                            }
                        }))
                        break  # Exit on failed initialization
                else:
                    # Echo back other events
                    await websocket.send_text(json.dumps(event))
                    
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except:
                    logger.warning("Failed to send ping, closing connection")
                    break
                
    except WebSocketDisconnect:
        logger.info("Client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": {"message": str(e)}
            }))
        except:
            pass
    finally:
        logger.info("Cleaning up WebSocket connection")

@app.function(
    image=image,
    keep_warm=1,
    allow_concurrent_inputs=True,  # Allow multiple WebSocket connections
    timeout=600,  # 10 minute timeout for long-running WebSocket connections
    container_idle_timeout=300  # Keep container alive for 5 minutes after last request
)
@asgi_app()
def fastapi_app():
    """ASGI app for handling WebSocket connections"""
    web_app.root_path = ""  # Ensure proper WebSocket path handling
    return web_app

if __name__ == "__main__":
    app.serve()
