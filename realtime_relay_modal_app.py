import asyncio
import json
import logging
import uuid
import os
import websockets
import requests
from auth.middleware import AuthMiddleware, security
from datetime import datetime
from modal import Image, App, asgi_app
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.security import HTTPAuthorizationCredentials
from typing import List, Optional

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
    version="1.0.0",
    root_path="",
    root_path_in_servers=False
)

# Initialize auth middleware
auth = AuthMiddleware()

# Create Modal app and image
app = App("realtime-relay")
image = (
    Image.debian_slim()
    .pip_install([
        "fastapi", "uvicorn", "websockets>=12.0", "requests", "python-multipart",
        "motor>=3.3.0", "bcrypt", "pydantic[email]", "pymongo>=4.5.0"
    ])
)

class RealtimeRelay:
    """
    Manages a single upstream connection to the OpenAI Realtime API.
    """
    def __init__(self, ephemeral_token: str, session_config: dict):
        self.ephemeral_token = ephemeral_token
        self.session_config = session_config
        self.upstream_ws = None

    async def connect_upstream(self):
        """Connect to the Realtime API over WebSocket using ephemeral token."""
        base_url = "wss://api.openai.com/v1/realtime"
        model = self.session_config.get("model", None)
        if model:
            base_url += f"?model={model}"

        headers = {
            "Authorization": f"Bearer {self.ephemeral_token}",
            "OpenAI-Beta": "realtime=v1"
        }

        logger.info(f"Connecting upstream to {base_url} ...")
        self.upstream_ws = await websockets.connect(base_url, additional_headers=headers)
        logger.info("Upstream connected.")

    async def close(self):
        if self.upstream_ws:
            await self.upstream_ws.close()

from modal import Secret
@app.function(secrets=[Secret.from_name("distributed-systems")])
def create_ephemeral_token(session_config: dict) -> str:
    """Create ephemeral token for Realtime API access."""
    payload = {
        k: session_config[k]
        for k in [
            "model", "modalities", "instructions", "voice",
            "input_audio_format", "output_audio_format",
            "input_audio_transcription", "turn_detection",
            "tools", "tool_choice", "temperature",
            "max_response_output_tokens"
        ]
        if k in session_config
    }
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    url = "https://api.openai.com/v1/realtime/sessions"
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "realtime=v1"
    }

    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed ephemeral token: {resp.text}")
    data = resp.json()
    return data["client_secret"]["value"]

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

manager = ConnectionManager()

async def handle_client(websocket: WebSocket, relay: Optional[RealtimeRelay] = None):
    """Handle bi-directional relay between client and OpenAI."""
    try:
        async def relay_local_to_upstream():
            while True:
                data_str = await websocket.receive_text()
                data = json.loads(data_str)
                if "event_id" not in data:
                    data["event_id"] = f"evt_{uuid.uuid4().hex[:6]}"
                await relay.upstream_ws.send(json.dumps(data))

        async def relay_upstream_to_local():
            try:
                async for data_str in relay.upstream_ws:
                    await websocket.send_text(data_str)
            except websockets.ConnectionClosed:
                pass

        done, pending = await asyncio.wait(
            [asyncio.create_task(relay_local_to_upstream()),
             asyncio.create_task(relay_upstream_to_local())],
            return_when=asyncio.FIRST_EXCEPTION
        )
        for task in pending:
            task.cancel()

    except Exception as e:
        logger.error(f"Relay error: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": {"message": str(e)}
            }))
        except:
            pass

@web_app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections with proper lifecycle management"""
    relay = None
    try:
        await websocket.accept()
        logger.info("New WebSocket connection accepted")

        # Send connection acknowledgment
        await websocket.send_text(json.dumps({
            "type": "connection.established",
            "timestamp": str(datetime.now())
        }))

        # Wait for init message
        data = await websocket.receive_text()
        init_msg = json.loads(data)

        if init_msg.get("type") != "init_session":
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": {
                    "code": "invalid_init",
                    "message": "First message must be init_session"
                }
            }))
            return

        # Create relay connection
        session_config = init_msg.get("session_config", {})
        try:
            token = create_ephemeral_token(session_config)
            relay = RealtimeRelay(token, session_config)
            await relay.connect_upstream()
            
            # Start bi-directional relay
            await handle_client(websocket, relay)

        except Exception as e:
            logger.error(f"Failed to initialize relay: {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": {
                    "code": "relay_init_failed",
                    "message": str(e)
                }
            }))

    except WebSocketDisconnect:
        logger.info("Client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        if relay:
            await relay.close()
        logger.info("Cleaning up WebSocket connection")

@app.function(
    image=image,
    keep_warm=1,
    allow_concurrent_inputs=True,
    timeout=600,
    container_idle_timeout=300,
)
@asgi_app(label="realtime-relay")
def fastapi_app():
    """ASGI app for handling WebSocket connections"""
    return web_app

if __name__ == "__main__":
    app.serve()
