# +-----------------------------------------+
# | relay_server.py                         |
# +-----------------------------------------+
import os
import json
import asyncio
import websockets
import requests
import logging

logger = logging.getLogger(__name__)
import uuid
import aiohttp
from typing import Optional, List, Dict, Any

from tool_registry_client import ToolRegistryClient

################################################################################
# Configuration
################################################################################

# Required environment variables
REQUIRED_ENV_VARS = {
    "OPENAI_API_KEY": "OpenAI API key for creating ephemeral tokens",
    "TOOL_REGISTRY_URL": "URL of the Tool Registry service",
}

# Check for required environment variables
missing_vars = []
for var, description in REQUIRED_ENV_VARS.items():
    if not os.environ.get(var):
        missing_vars.append(f"{var} - {description}")

if missing_vars:
    print("Error: Missing required environment variables:")
    for var in missing_vars:
        print(f"- {var}")
    exit(1)

# Initialize configurations
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
TOOL_REGISTRY_URL = os.environ["TOOL_REGISTRY_URL"]

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
        print("Tool Registry client initialized successfully")
        return tool_registry
    except Exception as e:
        print(f"Warning: Failed to initialize Tool Registry client: {e}")
        print("Continuing without tool support...")
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

        print(f"Connecting upstream to {base_url} ...")
        self.upstream_ws = await websockets.connect(base_url, additional_headers=headers)
        print("Upstream connected.")

    async def close(self):
        if self.upstream_ws:
            await self.upstream_ws.close()

################################################################################
# Relay server: local <-> Realtime
################################################################################

async def handle_client(client_ws, tool_registry=None):
    """
    Handles a single local client that connects to the relay server.
    1. Expects first message to contain the desired session config (JSON).
    2. Creates ephemeral token + new RealtimeRelay instance
    3. Connects upstream
    4. Then concurrently:
       - Listen for messages from local client, forward them to Realtime
       - Listen for messages from Realtime, forward them to local client
    """
    relay = None
    try:
        print("New client connected, waiting for init message...")
        # Step 1: Wait for session init from local with timeout
        try:
            init_msg_str = await asyncio.wait_for(client_ws.recv(), timeout=5.0)
            print(f"Received init message: {init_msg_str[:100]}...")
        except asyncio.TimeoutError:
            print("Timeout waiting for init message")
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
            For every message from the local CLI, forward it upstream.
            """
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
                    
                    # Pass through all events to upstream
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
                        print(f"Session created with config: {data.get('session', {})}")
                        
                    # Handle errors
                    elif data.get("type") == "error":
                        error_msg = data.get('error', {}).get('message', 'Unknown error')
                        print(f"Error from OpenAI: {error_msg}")
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
                print("WebSocket connection closed")
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
        print(f"[Server Error] {e}")
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
    
    print(r"""
██████╗░██╗░██████╗████████╗██████╗░██╗██████╗░██╗░░░██╗████████╗███████╗██████╗░
██╔══██╗██║██╔════╝╚══██╔══╝██╔══██╗██║██╔══██╗██║░░░██║╚══██╔══╝██╔════╝██╔══██╗
██║░░██║██║╚█████╗░░░░██║░░░██████╔╝██║██████╦╝██║░░░██║░░░██║░░░█████╗░░██║░░██║
██║░░██║██║░╚═══██╗░░░██║░░░██╔══██╗██║██╔══██╗██║░░░██║░░░██║░░░██╔══╝░░██║░░██║
██████╔╝██║██████╔╝░░░██║░░░██║░░██║██║██████╦╝╚██████╔╝░░░██║░░░███████╗██████╔╝
╚═════╝░╚═╝╚═════╝░░░░╚═╝░░░╚═╝░░╚═╝╚═╝╚═════╝░░╚═════╝░░░░╚═╝░░░╚══════╝╚═════╝░

░██████╗██╗░░░██╗░██████╗████████╗███████╗███╗░░░███╗░██████╗
██╔════╝╚██╗░██╔╝██╔════╝╚══██╔══╝██╔════╝████╗░████║██╔════╝
╚█████╗░░╚████╔╝░╚█████╗░░░░██║░░░█████╗░░██╔████╔██║╚█████╗░
░╚═══██╗░░╚██╔╝░░░╚═══██╗░░░██║░░░██╔══╝░░██║╚██╔╝██║░╚═══██╗
██████╔╝░░░██║░░░██████╔╝░░░██║░░░███████╗██║░╚═╝░██║██████╔╝
╚═════╝░░░░╚═╝░░░╚═════╝░░░░╚═╝░░░╚══════╝╚═╝░░░░░╚═╝╚═════╝░""")
    print("\n")
    print(f"Starting relay server on ws://localhost:{LOCAL_SERVER_PORT}")
    
    try:
        server = await websockets.serve(
            lambda ws: handle_client(ws, tool_registry), 
            "localhost", 
            LOCAL_SERVER_PORT, 
            compression=None
        )
        await asyncio.Future()  # run forever
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        print("Server shutting down.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Relay server shutting down.")
