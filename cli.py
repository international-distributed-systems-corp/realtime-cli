#!/usr/bin/env python3
"""
Command-line interface for the OpenAI Realtime API
"""
import os
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
from typing import Optional, Dict, Any
from pathlib import Path
from queue import Queue, Empty

from conversation_display import ConversationDisplay
from conversation import ConversationManager
from audio_training.storage import AudioStorage

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
        # Don't play if speech is detected
        if self.state.response_state == ResponseState.PROCESSING:
            return
            
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

# Configuration
################################################################################

# Required environment variables
REQUIRED_ENV_VARS = {
    "OPENAI_API_KEY": "OpenAI API key for creating ephemeral tokens",
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
TOOL_REGISTRY_URL = os.environ.get("TOOL_REGISTRY_URL", "http://localhost:2016")
RELAY_SERVER_URL = "ws://localhost:9000"
AUDIO_CHUNK = 1024
FORMAT = pyaudio.paFloat32
CHANNELS = 1
RATE = 24000  # OpenAI requires 24kHz sample rate for PCM16

# Initialize global state
STATE = SessionState()
STATE.audio.queue = Queue()  # Initialize audio queue
STATE.audio.player = None  # Initialize player attribute
STATE.audio.display = ConversationDisplay()  # Add display
STATE.audio.storage = AudioStorage()  # Initialize audio storage
STATE.conversation = ConversationManager()  # Add conversation manager

from session_manager import SessionManager

# Initialize session manager
session_manager = SessionManager()

# Audio recording settings
CHUNK = 1024
FORMAT = pyaudio.paInt16  # Changed to paInt16 for PCM16
CHANNELS = 1
RATE = 24000  # OpenAI requires 24kHz sample rate for PCM16

def audio_callback(in_data, frame_count, time_info, status):
    """Callback for audio recording"""
    if STATE.audio.is_recording and hasattr(STATE.audio, 'queue'):
        # Calculate audio level and update display
        audio_data = numpy.frombuffer(in_data, dtype=numpy.int16)
        audio_level = numpy.abs(audio_data).mean() / 32768.0  # Normalize to 0-1
        STATE.audio.display.update_input_level(audio_level)
        
        # Update conversation state
        STATE.conversation.update_human_audio(audio_level)
        
        # Always process audio when recording is active and not in RESPONDING state
        if STATE.response_state != ResponseState.RESPONDING:
            # Store audio sample
            STATE.audio.storage.save_sample(
                speaker='user',
                audio_data=in_data,
                sample_rate=RATE
            )
            STATE.audio.queue.put(in_data)
        
        # Update display
        if frame_count % 2 == 0:  # Reduce update frequency
            status = STATE.conversation.get_conversation_status()
            STATE.audio.display.set_status(status)
            STATE.audio.display.render()
        
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
                        
                elif event_type == "response.audio.delta":
                    if (STATE.response_state == ResponseState.RESPONDING and 
                        event["response_id"] == STATE.current_response_id):
                        # Decode and play audio
                        audio_data = base64.b64decode(event["delta"])
                        if STATE.audio.player is None:
                            STATE.audio.player = AudioPlayer()
                            STATE.audio.player.start()
                        # Update display with output audio level
                        audio_data_np = numpy.frombuffer(audio_data, dtype=numpy.int16)
                        output_level = numpy.abs(audio_data_np).mean() / 32768.0
                        STATE.audio.display.update_output_level(output_level)
                        STATE.audio.player.play(audio_data)
                        
                elif event_type == "response.done":
                    if STATE.response_state == ResponseState.RESPONDING:
                        text_accumulator.stop()
                        STATE.current_response_id = None
                        STATE.response_state = ResponseState.IDLE
                        print("\nReady for input...")  # Visual indicator
                        # Wait for audio playback to finish and levels to drop
                        if STATE.audio.player:
                            while STATE.audio.visualizer.output_level > 0.05:
                                await asyncio.sleep(0.1)
                            await asyncio.sleep(0.3)  # Additional cooldown
                            STATE.audio.player.stop()
                            STATE.audio.player = None
                        # Only resume recording after output level drops
                        STATE.audio.is_recording = True
                        
                elif event_type == "input_audio_buffer.speech_started":
                    # Stop current response and playback when speech detected
                    if STATE.response_state == ResponseState.RESPONDING:
                        # Clear audio queue and stop playback
                        while not STATE.audio.output_queue.empty():
                            STATE.audio.output_queue.get()
                        if STATE.audio.player:
                            STATE.audio.player.stop()
                            STATE.audio.player = None
                            
                        # Cancel current response
                        cancel_event = {
                            "event_id": f"evt_{uuid.uuid4().hex[:6]}",
                            "type": "response.cancel",
                            "response_id": STATE.current_response_id
                        }
                        await ws.send(json.dumps(cancel_event))
                        
                        # Reset state
                        STATE.current_response_id = None
                        STATE.response_state = ResponseState.IDLE
                        
                    STATE.response_state = ResponseState.PROCESSING
                    STATE.audio.display.start_user_speech()
                    
                elif event_type == "input_audio_buffer.speech_stopped":
                    if STATE.audio.display.current_line:
                        STATE.audio.display.complete_current_line()
                    
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = event['transcript']
                    STATE.audio.display.update_current_text(transcript)
                    STATE.audio.display.complete_current_line()
                    
                    # Update last user sample with transcription
                    if STATE.audio.storage:
                        samples = STATE.audio.storage.get_samples_by_speaker('user')
                        if samples:
                            last_sample = samples[-1]
                            STATE.audio.storage.update_transcription(last_sample.id, transcript)
                
            except json.JSONDecodeError:
                print(f"\nInvalid JSON: {msg_str}")
            except Exception as e:
                print(f"\nError handling event: {str(e)}")
                
    except websockets.ConnectionClosed:
        print("\nConnection to relay closed")

async def main():
    """Main entry point"""
    try:
        print(f"Connecting to relay at {RELAY_SERVER_URL} ...")
        
        async with websockets.connect(RELAY_SERVER_URL) as ws:
            # Set up signal handler
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(handle_interrupt(ws)))
            
            # Initialize session with dynamic config
            init_msg = {
                "type": "init_session",
                "session_config": session_manager.get_config()
            }
            await ws.send(json.dumps(init_msg))
            
            # Wait for session.created event
            async for msg_str in ws:
                event = json.loads(msg_str)
                if event.get("type") == "session.created":
                    break
                elif event.get("type") == "error":
                    raise Exception(f"Session initialization failed: {event.get('error', {}).get('message')}")
            
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
