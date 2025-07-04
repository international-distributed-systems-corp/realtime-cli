#!/usr/bin/env python3
"""
Command-line interface for the OpenAI Realtime API
"""
import asyncio
import websockets
import json
import uuid
import numpy
import pyaudio
import logging
import threading
import base64
import signal
import argparse
import os
from typing import Optional, Dict, Any
from pathlib import Path
from queue import Queue, Empty


from utils import (
    console,
    print_event,
    StreamingTextAccumulator,
    ProgressSpinner,
    handle_interrupt
)
from events import EventHandler, EventType
from state import SessionState, ResponseState, AudioState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AudioPlayer:
    """Handles playback of received audio from the assistant"""
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.audio_queue = Queue()
        self.is_playing = False
        self.play_thread = None

    def start(self):
        """Start audio playback thread"""
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=RATE,
            output=True,
            frames_per_buffer=CHUNK
        )
        self.is_playing = True
        self.play_thread = threading.Thread(target=self._playback_loop)
        self.play_thread.daemon = True
        self.play_thread.start()

    def _playback_loop(self):
        """Background thread for audio playback"""
        while self.is_playing:
            try:
                audio_data = self.audio_queue.get(timeout=0.1)
                self.stream.write(audio_data)
            except Empty:
                continue

    def play(self, audio_data: bytes):
        """Queue audio data for playback"""
        self.audio_queue.put(audio_data)

    def stop(self):
        """Stop playback and cleanup"""
        self.is_playing = False
        if self.play_thread:
            self.play_thread.join()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()

class AudioManager:
    """Manages both audio recording and playback"""
    def __init__(self, state: SessionState):
        self.state = state
        self.p = pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None
        self.record_thread = None
        self.play_thread = None
        
    def start_recording(self):
        """Initialize and start audio recording"""
        if self.state.audio.is_recording:
            logger.warning("Recording already in progress")
            return
            
        try:
            self.input_stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self.state.audio.channels,
                rate=self.state.audio.sample_rate,
                input=True,
                frames_per_buffer=self.state.audio.chunk_size,
                stream_callback=self._record_callback
            )
            
            self.state.audio.is_recording = True
            self.input_stream.start_stream()
            logger.info("Recording started")
            
        except Exception as e:
            logger.error(f"Failed to start recording: {str(e)}")
            self.state.audio.is_recording = False
            raise
            
    def start_playback(self):
        """Initialize and start audio playback"""
        if self.state.audio.is_playing:
            logger.warning("Playback already in progress")
            return
            
        try:
            self.output_stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self.state.audio.channels,
                rate=self.state.audio.sample_rate,
                output=True,
                frames_per_buffer=self.state.audio.chunk_size
            )
            
            self.state.audio.is_playing = True
            self.play_thread = threading.Thread(target=self._playback_loop)
            self.play_thread.daemon = True
            self.play_thread.start()
            logger.info("Playback started")
            
        except Exception as e:
            logger.error(f"Failed to start playback: {str(e)}")
            self.state.audio.is_playing = False
            raise
            
    def _record_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio recording"""
        if status:
            logger.warning(f"Recording status: {status}")
            
        if self.state.audio.is_recording:
            self.state.audio.input_queue.put(in_data)
            self.state.audio.current_input_buffer.append(in_data)
        return (in_data, pyaudio.paContinue)
        
    def _playback_loop(self):
        """Background thread for audio playback"""
        while self.state.audio.is_playing:
            try:
                audio_data = self.state.audio.output_queue.get(timeout=0.1)
                self.output_stream.write(audio_data)
                self.state.audio.current_output_buffer.append(audio_data)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Playback error: {str(e)}")
                break
                
    def play(self, audio_data: bytes):
        """Queue audio data for playback"""
        if not self.state.audio.is_playing:
            self.start_playback()
        self.state.audio.output_queue.put(audio_data)
        
    def stop_recording(self):
        """Stop recording and cleanup"""
        self.state.audio.is_recording = False
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
            self.input_stream = None
        logger.info("Recording stopped")
        
    def stop_playback(self):
        """Stop playback and cleanup"""
        self.state.audio.is_playing = False
        if self.play_thread:
            self.play_thread.join()
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
            self.output_stream = None
        logger.info("Playback stopped")
        
    def cleanup(self):  
        """Clean up all audio resources"""
        self.stop_recording()
        self.stop_playback()
        self.p.terminate()

# Local server URL
SERVER_URL = "wss://arthurcolle--realtime-relay.modal.run/ws"

# Configuration
AUDIO_CHUNK = 1024
FORMAT = pyaudio.paFloat32
CHANNELS = 1
RATE = 24000  # OpenAI requires 24kHz sample rate for PCM16

# Initialize global state
STATE = SessionState()
STATE.audio.queue = Queue()  # Initialize audio queue
STATE.audio.player = None  # Initialize player attribute

# Enhanced session config
DEFAULT_SESSION_CONFIG = {
    "model": "gpt-4o-realtime-preview-2025-06-03",
    "modalities": ["text", "audio"],
    "instructions": """You are a helpful AI assistant.
You can engage in natural conversation and help users with various tasks.
Be friendly, clear, and concise in your responses.""",
    "voice": "verse",
    "input_audio_format": "pcm16",  # 24kHz, mono, 16-bit PCM, little-endian
    "output_audio_format": "pcm16",  # 24kHz sample rate
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
    "tools": [],
    "tool_choice": "auto"
}

# Audio recording settings
CHUNK = 1024
FORMAT = pyaudio.paInt16  # Changed to paInt16 for PCM16
CHANNELS = 1
RATE = 24000  # OpenAI requires 24kHz sample rate for PCM16

def audio_callback(in_data, frame_count, time_info, status):
    """Callback for audio recording"""
    if STATE.audio.is_recording and hasattr(STATE.audio, 'queue'):
        # Apply ducking if AI is speaking
        if STATE.response_state == ResponseState.RESPONDING:
            # Convert to numpy array for volume adjustment
            audio_data = numpy.frombuffer(in_data, dtype=numpy.int16)
            audio_data = (audio_data * DUCK_RATIO).astype(numpy.int16)
            in_data = audio_data.tobytes()
        STATE.audio.queue.put(in_data)
    return (in_data, pyaudio.paContinue)

# Audio ducking configuration
DUCK_RATIO = 0.3  # Reduce input volume to 30% while AI speaks

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
    
    # Stream audio buffers
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

async def conversation_loop(ws):
    """
    Natural conversation loop for interacting with the Realtime API
    """
    print("\nStarting conversation...")
    print("Just start speaking naturally - I'll listen and respond.")
    print("Press Ctrl+C to end the conversation.\n")

    # Start continuous recording right away
    STATE.audio.is_recording = True
    record_task = asyncio.create_task(start_recording(ws))
    
    try:
        # Keep the conversation going until interrupted
        while True:
            await asyncio.sleep(0.1)
            
    except asyncio.CancelledError:
        print("\nEnding conversation...")
        STATE.audio.is_recording = False
        await record_task


async def handle_server_events(ws):
    """Handle incoming server events and manage state"""
    text_accumulator = StreamingTextAccumulator()
    
    try:
        async for msg_str in ws:
            try:
                event = json.loads(msg_str)
                event_type = event.get("type")
                
                # Debug logging
                print(f"Received event: {event_type}")
                
                # Handle different event types
                if event_type == "error":
                    print(f"\nError: {event['error'].get('message')}")
                    STATE.response_state = ResponseState.IDLE
                    STATE.audio.is_recording = True  # Resume listening
                    
                elif event_type == "session.created":
                    print("Ready to chat!")
                    
                elif event_type == "response.created":
                    STATE.current_response_id = event["response"]["id"]
                    STATE.response_state = ResponseState.RESPONDING
                    text_accumulator.start()
                    
                elif event_type == "response.text.delta":
                    if (STATE.response_state == ResponseState.RESPONDING and 
                        event["response_id"] == STATE.current_response_id):
                        text_accumulator.update(event["delta"])
                        print(event["delta"], end='', flush=True)

                elif event_type == "tool_use":
                    print(f"\nTool use not supported in local relay mode")

                elif event_type == "response.audio_transcript.delta":
                    if (STATE.response_state == ResponseState.RESPONDING and 
                        event["response_id"] == STATE.current_response_id):
                        text_accumulator.transcript += event['delta']
                        # Clear screen and redisplay full transcript
                        print("\033[H\033[J")  # Clear screen
                        print("\nYou: [Listening...]")
                        print(f"\nAssistant Transcript:\n{text_accumulator.transcript}")
                        
                elif event_type == "response.audio.delta":
                    if (STATE.response_state == ResponseState.RESPONDING and 
                        event["response_id"] == STATE.current_response_id):
                        # Decode and play audio
                        audio_data = base64.b64decode(event["delta"])
                        if STATE.audio.player is None:
                            STATE.audio.player = AudioPlayer()
                            STATE.audio.player.start()
                        STATE.audio.player.play(audio_data)
                        
                elif event_type == "response.done":
                    if STATE.response_state == ResponseState.RESPONDING:
                        text_accumulator.stop()
                        text_accumulator.transcript = ""  # Clear transcript for next response
                        print("\n")  # Add newline after assistant response
                        STATE.current_response_id = None
                        STATE.response_state = ResponseState.IDLE
                        if STATE.audio.player:
                            STATE.audio.player.stop()
                            STATE.audio.player = None
                        # Resume listening after AI is done speaking
                        STATE.audio.is_recording = True
                        
                elif event_type == "input_audio_buffer.speech_started":
                    STATE.response_state = ResponseState.PROCESSING
                    
                elif event_type == "input_audio_buffer.speech_stopped":
                    pass  # Let the server handle turn detection
                    
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    print(f"\nYou: {event['transcript']}")
                
            except json.JSONDecodeError:
                print(f"\nInvalid JSON: {msg_str}")
            except Exception as e:
                print(f"\nError handling event: {str(e)}")
                
    except websockets.ConnectionClosed:
        print("\nConnection to relay closed")

async def main():
    """Main entry point"""
    relay_url = SERVER_URL
    
    try:
        print(f"Connecting to relay at {relay_url} ...")
        
        async with websockets.connect(
            relay_url,
            additional_headers={"Content-Type": "application/json"}
        ) as ws:
            # Set up signal handler
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(handle_interrupt(ws)))
            
            # Wait for connection.established and session.created events
            try:
                # First wait for connection.established
                msg_str = await asyncio.wait_for(ws.recv(), timeout=10.0)  # Increased timeout
                event = json.loads(msg_str)
                print(f"Received initialization response: {event}")
                
                if event.get("type") == "error":
                    error_msg = event.get('error', {}).get('message', 'Unknown error')
                    raise Exception(f"Session initialization failed: {error_msg}")
                elif event.get("type") != "connection.established":
                    raise Exception(f"Expected connection.established, got {event.get('type')}")
                    
                # Send init_session message after connection established
                print("Connection established, initializing session...")
                init_msg = {
                    "type": "init_session",
                    "session_config": DEFAULT_SESSION_CONFIG
                }
                print(f"Sending init message: {json.dumps(init_msg, indent=2)}")
                await ws.send(json.dumps(init_msg))
                
                # Then wait for session.created
                print("Waiting for session.created response...")
                msg_str = await asyncio.wait_for(ws.recv(), timeout=30.0)  # Increased timeout further
                event = json.loads(msg_str)
                print(f"Received session response: {event}")
                
                if event.get("type") == "error":
                    error_msg = event.get('error', {}).get('message', 'Unknown error')
                    raise Exception(f"Session initialization failed: {error_msg}")
                elif event.get("type") != "session.created":
                    raise Exception(f"Expected session.created, got {event.get('type')}")
                
                print("Session successfully created!")
                    
            except asyncio.TimeoutError:
                raise Exception("Session initialization timed out - the server took too long to respond")
            except Exception as e:
                raise Exception(f"Session initialization failed: {str(e)}")

            # Run conversation and event handling loops
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(conversation_loop(ws)),
                    asyncio.create_task(handle_server_events(ws))
                ],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
    except Exception as e:
        print(f"\nFatal error: {str(e)}")
    finally:
        # Cleanup
        if STATE.audio.player:
            STATE.audio.player.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("CLI interrupted.")
