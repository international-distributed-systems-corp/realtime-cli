#!/usr/bin/env python3
"""
Realtime CLI integration for Claude Computer Use
"""
import asyncio
import websockets
import json
import uuid
import pyaudio
import logging
import base64
import requests
from getpass import getpass
from queue import Queue, Empty
from typing import Optional
from enum import Enum, auto
from computer_use_demo.tools import ToolCollection, ComputerTool, BashTool, EditTool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ResponseState(Enum):
    IDLE = auto()
    PROCESSING = auto() 
    RESPONDING = auto()

class AudioState:
    def __init__(self):
        self.is_recording = False
        self.is_playing = False
        self.queue = Queue()
        self.player = None
        self.channels = 1
        self.sample_rate = 24000
        self.chunk_size = 1024

class SessionState:
    def __init__(self):
        self.current_response_id = None
        self.response_state = ResponseState.IDLE
        self.audio = AudioState()

# Environment URLs  
PROD_URL = "wss://arthurcolle--realtime-relay.modal.run"
DEV_URL = "wss://arthurcolle--realtime-relay-dev.modal.run"

async def login(base_url: str) -> str:
    """Login and get access token"""
    email = input("Email: ")
    password = getpass("Password: ")
    
    response = requests.post(
        f"{base_url}/token",
        data={"username": email, "password": password}
    )
    
    if response.status_code != 200:
        raise Exception(f"Login failed: {response.text}")
        
    return response.json()["access_token"]

# Audio settings
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1 
RATE = 24000

# Import computer use tools
from computer_use_demo.tools import ToolCollection, ComputerTool, BashTool, EditTool

# Initialize tool collection
tool_collection = ToolCollection(
    ComputerTool(),
    BashTool(),
    EditTool(),
)

# Default session config
DEFAULT_SESSION_CONFIG = {
    "model": "claude-3-sonnet-20240229",
    "modalities": ["text", "audio"],
    "instructions": """You are a helpful AI assistant with computer control capabilities.
You can control the computer using mouse, keyboard and run commands.
Use the computer tools naturally as part of our conversation.""",
    "voice": "alloy", 
    "input_audio_format": "pcm16",
    "output_audio_format": "pcm16",
    "input_audio_transcription": {
        "model": "whisper-1"
    },
    "turn_detection": {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 500,
        "create_response": True
    },
    "tools": tool_collection.to_params(),
    "tool_choice": "auto"
}

def audio_callback(in_data, frame_count, time_info, status):
    """Callback for audio recording"""
    if STATE.audio.is_recording and hasattr(STATE.audio, 'queue'):
        STATE.audio.queue.put(in_data)
    return (in_data, pyaudio.paContinue)

async def start_recording(ws):
    """Start recording and streaming audio"""
    STATE.audio.is_recording = True
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                   channels=CHANNELS,
                   rate=RATE,
                   input=True,
                   frames_per_buffer=CHUNK,
                   stream_callback=audio_callback)
    stream.start_stream()
    
    while STATE.audio.is_recording:
        try:
            audio_data = STATE.audio.queue.get_nowait()
            event = {
                "event_id": f"evt_{uuid.uuid4().hex[:6]}",
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(audio_data).decode('utf-8')
            }
            await ws.send(json.dumps(event))
        except Empty:
            await asyncio.sleep(0.01)
    
    stream.stop_stream()
    stream.close()
    p.terminate()

async def handle_server_events(ws):
    """Handle incoming server events"""
    try:
        async for msg_str in ws:
            try:
                event = json.loads(msg_str)
                event_type = event.get("type")
                
                logger.debug(f"Received event: {event_type}")
                
                if event_type == "error":
                    print(f"\nError: {event['error'].get('message')}")
                    STATE.response_state = ResponseState.IDLE
                    STATE.audio.is_recording = True
                    
                elif event_type == "session.created":
                    print("Session ready!")
                    
                elif event_type == "response.created":
                    STATE.current_response_id = event["response"]["id"]
                    STATE.response_state = ResponseState.RESPONDING
                    
                elif event_type == "response.text.delta":
                    if (STATE.response_state == ResponseState.RESPONDING and 
                        event["response_id"] == STATE.current_response_id):
                        print(event["delta"], end='', flush=True)

                elif event_type == "response.done":
                    if STATE.response_state == ResponseState.RESPONDING:
                        print("\n")
                        STATE.current_response_id = None
                        STATE.response_state = ResponseState.IDLE
                        STATE.audio.is_recording = True
                        
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    print(f"\nYou: {event['transcript']}")
                    
                elif event_type == "tool_use":
                    # Handle tool use
                    result = await tool_collection.run(
                        name=event["name"],
                        tool_input=event["input"]
                    )
                    
                    # Send tool result back
                    await ws.send(json.dumps({
                        "type": "tool_result",
                        "tool_use_id": event["id"],
                        "content": [
                            {
                                "type": "text",
                                "text": result.output or result.error or ""
                            }
                        ] + ([{
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": result.base64_image
                            }
                        }] if result.base64_image else [])
                    }))
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON: {msg_str}")
            except Exception as e:
                logger.error(f"Error handling event: {str(e)}")
                
    except websockets.ConnectionClosed:
        print("\nConnection closed")

async def start_realtime_session(env: str = 'prod'):
    """Start a realtime session with Claude"""
    global STATE
    STATE = SessionState()
    
    relay_url = PROD_URL if env == 'prod' else DEV_URL
    print(f"Connecting to {relay_url}...")
    
    try:
        # Get authentication token
        token = await login(relay_url)
        
        async with websockets.connect(
            f"{relay_url}/ws",
            additional_headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
        ) as ws:
            # Wait for connection
            msg_str = await ws.recv()
            event = json.loads(msg_str)
            
            if event.get("type") == "error":
                raise Exception(f"Connection failed: {event.get('error',{}).get('message')}")
            elif event.get("type") != "connection.established":
                raise Exception(f"Expected connection.established, got {event.get('type')}")
                
            # Initialize session
            print("Initializing session...")
            await ws.send(json.dumps({
                "type": "init_session",
                "session_config": DEFAULT_SESSION_CONFIG
            }))
            
            msg_str = await ws.recv()
            event = json.loads(msg_str)
            
            if event.get("type") == "error":
                raise Exception(f"Session init failed: {event.get('error',{}).get('message')}")
            elif event.get("type") != "session.created":
                raise Exception(f"Expected session.created, got {event.get('type')}")
            
            print("Session created! Start speaking...")
            
            # Start conversation
            STATE.audio.is_recording = True
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(start_recording(ws)),
                    asyncio.create_task(handle_server_events(ws))
                ],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    finally:
        if STATE.audio.player:
            STATE.audio.player.stop()

async def register(base_url: str):
    """Register a new user"""
    email = input("Email: ")
    password = getpass("Password: ")
    
    response = requests.post(
        f"{base_url}/register",
        json={"email": email, "password": password}
    )
    
    if response.status_code != 200:
        raise Exception(f"Registration failed: {response.text}")
    print("Registration successful! Please login.")

if __name__ == "__main__":
    try:
        import argparse
        parser = argparse.ArgumentParser(description='Realtime CLI')
        parser.add_argument('--env', choices=['prod', 'dev'], default='prod',
                          help='Environment to connect to')
        parser.add_argument('--register', action='store_true',
                          help='Register a new user')
        args = parser.parse_args()
        
        base_url = PROD_URL if args.env == 'prod' else DEV_URL
        
        if args.register:
            asyncio.run(register(base_url))
        else:
            asyncio.run(start_realtime_session(args.env))
    except KeyboardInterrupt:
        print("\nSession ended.")
