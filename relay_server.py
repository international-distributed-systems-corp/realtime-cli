# +-----------------------------------------+
# | relay_server.py                         |
# +-----------------------------------------+
import os
import json
import asyncio
import websockets
import requests
import logging
from datetime import datetime

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Define event types
SERVER_EVENTS = {
    'server.start': 'Server started',
    'server.stop': 'Server stopped',
    'client.connect': 'Client connected',
    'client.disconnect': 'Client disconnected',
    'session.create': 'Session created',
    'session.end': 'Session ended',
    'error.token': 'Token error',
    'error.connection': 'Connection error',
    'error.relay': 'Relay error'
}

CLIENT_EVENTS = {
    'init_session': 'Session initialization',
    'function.call': 'Function call',
    'function.response': 'Function response',
    'error': 'Error event',
    'rate_limits.updated': 'Rate limits updated',
    'session.created': 'Session created'
}
import uuid
import aiohttp
from typing import Optional, List, Dict, Any

from tool_registry_client import ToolRegistryClient

################################################################################
# Configuration
################################################################################

# The standard API key that can create ephemeral tokens.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("Error: Set OPENAI_API_KEY in your environment.")
    exit(1)

# The port on which our local relay will listen for the CLI:
LOCAL_SERVER_PORT = 9000

################################################################################
# Helper: Create ephemeral token
################################################################################

async def initialize_tool_registry():
    """Initialize the Tool Registry client"""
    try:
        # Create client instance
        tool_registry = ToolRegistryClient(base_url=TOOL_REGISTRY_URL)
        logger.debug("Tool Registry client initialized")
        return tool_registry
    except Exception as e:
        logger.warning(f"Failed to initialize Tool Registry client: {e}")
        return None

def create_ephemeral_token(session_config: dict) -> str:
    """
    Uses your standard OpenAI API key to request an ephemeral Realtime token.
    Strips out any non-supported fields from session config.
    """
    # Only include supported fields
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
    
    url = "https://api.openai.com/v1/realtime/sessions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "realtime=v1"
    }
    
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed ephemeral token: {resp.text}")
    data = resp.json()
    return data["client_secret"]["value"]

################################################################################
# Relay Connection
################################################################################

async def list_tools() -> List[Dict[str, Any]]:
    """List all available tools from the registry"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{TOOL_REGISTRY_URL}/tools") as response:
                if response.status == 200:
                    return await response.json()
                return []
    except Exception as e:
        logger.warning(f"Failed to fetch tools: {e}")
        return []

class RealtimeRelay:
    """
    Manages a single upstream connection to the OpenAI Realtime API.
    We store the ephemeral token, the local <-> Realtime websockets,
    and any relevant session metadata.
    """
    def __init__(self, ephemeral_token: str, session_config: dict):
        self.ephemeral_token = ephemeral_token
        self.session_config = session_config
        self.upstream_ws = None  # websockets.client.WebSocketClientProtocol

    async def connect_upstream(self):
        """
        Connect to the Realtime API over WebSocket using ephemeral token.
        """
        # Build the Realtime wss URL
        # We can append "?model=..." if not specified in the session config.
        # But if session_config includes "model", the ephemeral session should
        # already be locked to that model. It's optional to pass again in the URL.
        base_url = "wss://api.openai.com/v1/realtime"
        # For safety, specify the model if we know it:
        model = self.session_config.get("model", None)
        if model:
            base_url += f"?model={model}"

        headers = {
            "Authorization": f"Bearer {self.ephemeral_token}",
            "OpenAI-Beta": "realtime=v1"
        }

        self.upstream_ws = await websockets.connect(base_url, additional_headers=headers)

    async def close(self):
        if self.upstream_ws:
            await self.upstream_ws.close()

################################################################################
# Relay server: local <-> Realtime
################################################################################

async def handle_client(client_ws, tool_registry=None):
    """
    Handles a single local client with advanced error recovery and monitoring.
    1. Expects first message to contain the desired session config (JSON).
    2. Creates ephemeral token + new RealtimeRelay instance
    3. Connects upstream
    4. Then concurrently:
       - Listen for messages from local client, forward them to Realtime
       - Listen for messages from Realtime, forward them to local client
    """
    relay = None
    try:
        client_id = str(uuid.uuid4())[:8]
        logger.info(f"New client connected [id={client_id}]", extra={'event': 'client.connect', 'client_id': client_id})

        # Step 1: Wait for session init from local with timeout
        try:
            init_msg_str = await asyncio.wait_for(client_ws.recv(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning(f"Session init timeout [id={client_id}]", extra={'event': 'error.timeout', 'client_id': client_id})
            return
        init_msg = json.loads(init_msg_str)
        
        if init_msg.get("type") != "init_session":
            error_event = {
                "event_id": f"evt_{uuid.uuid4().hex[:6]}",
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "code": "invalid_event",
                    "message": "First message must have type=init_session",
                    "param": "type"
                }
            }
            await client_ws.send(json.dumps(error_event))
            return

        session_config = init_msg.get("session_config", {})
        try:
            ephemeral_token = create_ephemeral_token(session_config)
        except Exception as e:
            error_event = {
                "event_id": f"evt_{uuid.uuid4().hex[:6]}",
                "type": "error",
                "error": {
                    "type": "token_error",
                    "code": "token_creation_failed",
                    "message": str(e),
                    "param": None
                }
            }
            await client_ws.send(json.dumps(error_event))
            return

        relay = RealtimeRelay(ephemeral_token, session_config)
        await relay.connect_upstream()

        # Load available tools and update session config
        if tool_registry:
            try:
                tools = await tool_registry.list_tools()
                if tools:
                    session_config.setdefault("tools", []).extend(tools)
            except Exception as e:
                logger.warning(f"Failed to load tools: {e}")
        
        # Step 2: Start bi-directional relay
        async def relay_local_to_upstream():
            """
            Advanced message relay with retry logic and monitoring
            """
            metrics = {
                'messages_sent': 0,
                'retry_count': 0,
                'errors': {},
                'latency': []
            }
            while True:
                try:
                    data_str = await asyncio.wait_for(client_ws.recv(), timeout=1.0)
                    data = json.loads(data_str)
                    
                    # Ensure event_id exists
                    if "event_id" not in data:
                        data["event_id"] = f"evt_{uuid.uuid4().hex[:6]}"
                    
                        
                    # Add timeout to upstream send
                    await asyncio.wait_for(relay.upstream_ws.send(json.dumps(data)), timeout=2.0)
                except asyncio.TimeoutError:
                    continue

                try:
                    # Handle function calls
                    if data.get("type") == "function.call":
                        try:
                            result = await tool_registry.call_function(
                                data["name"],
                                data["parameters"]
                            )
                            response = {
                                "event_id": f"evt_{uuid.uuid4().hex[:6]}",
                                "type": "function.response",
                                "response_id": data.get("response_id"),
                                "result": result
                            }
                            await client_ws.send(json.dumps(response))
                        except Exception as e:
                            error = {
                                "event_id": f"evt_{uuid.uuid4().hex[:6]}",
                                "type": "error",
                                "error": {
                                    "type": "function_error",
                                    "code": "function_call_failed",
                                    "message": str(e)
                                }
                            }
                            await client_ws.send(json.dumps(error))
                    else:
                        await relay.upstream_ws.send(json.dumps(data))
                except json.JSONDecodeError:
                    error_event = {
                        "event_id": f"evt_{uuid.uuid4().hex[:6]}",
                        "type": "error",
                        "error": {
                            "type": "invalid_request_error",
                            "code": "invalid_json",
                            "message": "Invalid JSON payload",
                            "param": None
                        }
                    }
                    await client_ws.send(json.dumps(error_event))

        async def relay_upstream_to_local():
            """
            For every message from the Realtime API, forward it to the local client.
            """
            rate_limits = None
            try:
                async for data_str in relay.upstream_ws:
                    data = json.loads(data_str)
                    
                    
                    # Track rate limits
                    if data.get("type") == "rate_limits.updated":
                        rate_limits = data.get("rate_limits", [])
                        
                    # Handle session creation
                    elif data.get("type") == "session.created":
                        pass  # No special handling needed for session creation
                        
                    # Handle errors
                    elif data.get("type") == "error":
                        error_msg = data.get('error', {}).get('message', 'Unknown error')
                        logger.error(f"OpenAI API error: {error_msg}")
                        # Ensure proper error response format
                        error_response = {
                            "event_id": f"evt_{uuid.uuid4().hex[:6]}",
                            "type": "error",
                            "error": {
                                "type": "openai_error",
                                "code": "api_error",
                                "message": error_msg
                            }
                        }
                        await client_ws.send(json.dumps(error_response))
                    else:
                        await client_ws.send(data_str)
                    
            except websockets.ConnectionClosed:
                logger.debug("WebSocket connection closed")
                return
            except Exception as e:
                error_event = {
                    "event_id": f"evt_{uuid.uuid4().hex[:6]}",
                    "type": "error",
                    "error": {
                        "type": "relay_error",
                        "code": "relay_failed",
                        "message": str(e),
                        "param": None
                    }
                }
                try:
                    await client_ws.send(json.dumps(error_event))
                except Exception as send_error:
                    print(f"Failed to send error event: {send_error}")
                return

        done, pending = await asyncio.wait(
            [asyncio.create_task(relay_local_to_upstream()),
             asyncio.create_task(relay_upstream_to_local())],
            return_when=asyncio.FIRST_EXCEPTION
        )
        # If any subtask fails, cancel the other
        for task in pending:
            task.cancel()

    except (asyncio.CancelledError, websockets.ConnectionClosed):
        pass
    except Exception as e:
        logger.error(f"Server error: {e}")
        # Attempt to inform the client
        err_evt = {
            "type": "server_relay_error",
            "error": str(e)
        }
        try:
            await client_ws.send(json.dumps(err_evt))
        except:
            pass
    finally:
        await client_ws.close()

async def main():
    # Initialize Tool Registry
    tool_registry = await initialize_tool_registry()
    
    logger.info(f"Starting relay server on ws://localhost:{LOCAL_SERVER_PORT}", 
               extra={'event': 'server.start', 'port': LOCAL_SERVER_PORT})
    
    try:
        server = await websockets.serve(
            lambda ws: handle_client(ws, tool_registry), 
            "localhost", 
            LOCAL_SERVER_PORT, 
            compression=None
        )
        await asyncio.Future()  # run forever
    except Exception as e:
        logger.error(f"Server error: {e}", extra={'event': 'error.server', 'error': str(e)})
    finally:
        logger.info("Server shutting down.", extra={'event': 'server.stop'})

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Relay server shutting down.", extra={'event': 'server.stop', 'reason': 'keyboard_interrupt'})
