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
from scipy import signal
import base64
import signal
import select
import sys
from typing import Optional, Dict, Any
from pathlib import Path
from queue import Queue, Empty
from datetime import datetime

from conversation_display import ConversationDisplay
from conversation import ConversationManager
from audio_training.storage import AudioStorage
from services.thought_analyzer import ThoughtAnalyzer

from utils import (
    console,
    print_event,
    StreamingTextAccumulator,
    ProgressSpinner,
    handle_interrupt
)
from services.thought_analyzer import ThoughtAnalyzer
from visualizer import AudioVisualizer
from events import EventHandler, EventType
from state import SessionState, ResponseState, AudioState

# Configure minimal logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
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
STATE.audio.visualizer = AudioVisualizer()  # Initialize visualizer
STATE.conversation = ConversationManager()  # Add conversation manager

from session_manager import SessionManager

# Initialize session manager
session_manager = SessionManager()

# Enhanced session config
DEFAULT_SESSION_CONFIG = {
    "model": "gpt-4o-realtime",
    "modalities": ["text", "audio"],
    "instructions": "You are a friendly assistant.",
    "voice": "alloy", 
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
    }
}

# Audio recording settings
CHUNK = 2048  # Optimized chunk size
FORMAT = pyaudio.paFloat32  # High quality format
CHANNELS = 1
RATE = 24000  # Native rate for OpenAI
TARGET_RATE = 24000  # OpenAI requires 24kHz

# Advanced audio processing settings
NOISE_REDUCTION_STRENGTH = 0.15  # Noise reduction factor
AUDIO_GAIN = 1.2  # Input gain adjustment
SILENCE_THRESHOLD = 0.01  # Silence detection threshold
MAX_RETRY_ATTEMPTS = 3  # Max retries for failed operations
BACKOFF_FACTOR = 1.5  # Exponential backoff factor

# Voice Activity Detection settings
VAD_THRESHOLD = 0.02  # Initial VAD threshold
VAD_ADJUSTMENT = 0.8  # Scale factor for input sensitivity
BACKGROUND_LEARNING_RATE = 0.01  # Rate to learn background noise level

def process_audio(audio_data: bytes, from_rate: int, to_rate: int) -> bytes:
    """
    Process audio data with advanced noise reduction and resampling
    """
    # Convert to numpy array and make a copy
    audio_array = numpy.frombuffer(audio_data, dtype=numpy.float32).copy()
    
    # Apply noise reduction
    if len(audio_array) > 0:
        # Calculate noise profile from silent portions
        noise_profile = numpy.mean(numpy.abs(audio_array[audio_array < SILENCE_THRESHOLD]))
        # Apply spectral subtraction
        audio_array -= noise_profile * NOISE_REDUCTION_STRENGTH
        
    # Apply gain
    audio_array *= AUDIO_GAIN
    
    # Clip to prevent distortion
    audio_array = numpy.clip(audio_array, -1.0, 1.0)
    
    # Resample if needed
    if from_rate != to_rate:
        audio_array = signal.resample(audio_array, int(len(audio_array) * to_rate / from_rate))
    
    return audio_array.astype(numpy.float32).tobytes()

def audio_callback(in_data, frame_count, time_info, status):
    """Callback for audio recording"""
    if STATE.audio.is_recording:
        # Convert input to numpy array for processing
        audio_data = numpy.frombuffer(in_data, dtype=numpy.float32)
        
        # Calculate audio level
        audio_level = numpy.abs(audio_data).mean()
        
        # Update background noise level
        if not hasattr(STATE.audio, 'background_level'):
            STATE.audio.background_level = audio_level
        else:
            STATE.audio.background_level = (
                (1 - BACKGROUND_LEARNING_RATE) * STATE.audio.background_level +
                BACKGROUND_LEARNING_RATE * audio_level
            )
        
        # Detect voice activity
        is_voice = audio_level > (STATE.audio.background_level * VAD_THRESHOLD)
        
        # If playing audio, mute the input
        if getattr(STATE.audio, 'is_playing', False):
            # Generate silence instead of recording
            audio_data = numpy.zeros_like(audio_data)
            is_voice = False
        else:
            # Apply input sensitivity adjustment
            audio_data = audio_data * VAD_ADJUSTMENT
        
        # Update VAD indicator
        STATE.audio.display.update_vad_indicator(is_voice)
        
        # Queue the processed audio
        if not hasattr(STATE.audio, 'queue'):
            STATE.audio.queue = Queue()
        STATE.audio.queue.put(audio_data.tobytes())
        
        # Update visualization
        if frame_count % 2 == 0:
            STATE.audio.display.update_input_level(audio_level)
            STATE.audio.display.render()
            
    return (in_data, pyaudio.paContinue)

async def start_recording(ws):
    """Start recording and streaming audio"""
    if not hasattr(STATE.audio, 'queue'):
        STATE.audio.queue = Queue()
    
    STATE.audio.is_recording = True
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                   channels=CHANNELS,
                   rate=RATE,
                   input=True,
                   frames_per_buffer=CHUNK,
                   stream_callback=audio_callback)
    stream.start_stream()
    logger.info("Recording started")
    
    # Stream audio buffers and handle text input
    while STATE.audio.is_recording:
        try:
            # Check for text input
            if select.select([sys.stdin], [], [], 0)[0]:
                line = sys.stdin.readline().strip()
                if line.startswith(':'):
                    text = line[1:].strip()
                    if text:
                        event = {
                            "event_id": f"evt_{uuid.uuid4().hex[:6]}",
                            "type": "text.content",
                            "content": text
                        }
                        await ws.send(json.dumps(event))
                        transcript.append(f"User: {text}")
            
            # Handle audio
            audio_data = STATE.audio.queue.get_nowait()
            resampled_audio = process_audio(audio_data, RATE, TARGET_RATE)
            event = {
                "event_id": f"evt_{uuid.uuid4().hex[:6]}",
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(resampled_audio).decode('utf-8')
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
    print("Just start speaking naturally or type your message.")
    print("To type a message, start with ':' (e.g. :hello)")
    print("Press Ctrl+C to end the conversation.\n")

    # Start continuous recording right away
    STATE.audio.is_recording = True
    STATE.audio.queue = Queue()
    STATE.record_task = asyncio.create_task(start_recording(ws))
    
    try:
        # Keep the conversation going until interrupted
        while True:
            await asyncio.sleep(0.1)
            
            # Check if recording task needs to be restarted
            if STATE.audio.is_recording and (not hasattr(STATE, 'record_task') or STATE.record_task.done()):
                STATE.record_task = asyncio.create_task(start_recording(ws))
            
    except asyncio.CancelledError:
        print("\nEnding conversation...")
        STATE.audio.is_recording = False
        if hasattr(STATE, 'record_task'):
            await STATE.record_task


# Global transcript storage
transcript = []

async def handle_server_events(ws):
    """Handle incoming server events with advanced state management and error recovery"""
    text_accumulator = StreamingTextAccumulator()
    retry_count = 0
    last_event_time = datetime.now()
    global transcript  # Use global transcript
    
    # Initialize state tracking
    conversation_state = {
        'context': [],
        'turn_count': 0,
        'last_speaker': None,
        'current_topic': None,
        'pending_actions': [],
        'error_count': 0
    }
    
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
                        if event.get("finish_reason") == "stop":
                            transcript.append(f"Assistant: {text_accumulator.get_text()}")
                        
                elif event_type == "response.audio.delta":
                    if (STATE.response_state == ResponseState.RESPONDING and 
                        event["response_id"] == STATE.current_response_id):
                        # Decode and play audio
                        # Resample from TARGET_RATE back to RATE for playback
                        audio_data = process_audio(
                            base64.b64decode(event["delta"]),
                            TARGET_RATE,
                            RATE
                        )
                        if STATE.audio.player is None:
                            STATE.audio.player = AudioPlayer()
                            STATE.audio.player.start()
                            # Mark as playing but keep recording (will be muted)
                            STATE.audio.is_playing = True
                        # Update display and visualizer with output audio level
                        STATE.audio.visualizer.update_output_level(audio_data)
                        STATE.audio.display.update_output_level(STATE.audio.visualizer.output_level)
                        STATE.audio.player.play(audio_data)
                        
                elif event_type == "response.done":
                    if STATE.response_state == ResponseState.RESPONDING:
                        text_accumulator.stop()
                        STATE.current_response_id = None
                        STATE.response_state = ResponseState.IDLE
                        print("\nReady for input...")  # Visual indicator
                        
                        # Wait for audio playback to finish and levels to drop
                        if STATE.audio.player:
                            try:
                                while STATE.audio.visualizer.output_level > 0.05:
                                    await asyncio.sleep(0.1)
                                await asyncio.sleep(0.3)  # Additional cooldown
                            finally:
                                STATE.audio.player.stop()
                                STATE.audio.player = None
                                STATE.audio.is_playing = False
                        
                        # Reset recording state
                        STATE.audio.queue = Queue()
                        
                        # Restart recording if needed
                        if not hasattr(STATE, 'record_task') or STATE.record_task.done():
                            STATE.record_task = asyncio.create_task(start_recording(ws))
                        
                elif event_type == "input_audio_buffer.speech_started":
                    STATE.response_state = ResponseState.PROCESSING
                    STATE.audio.display.start_user_speech()
                    
                    # Only attempt cancellation if there's an active response
                    if STATE.current_response_id and STATE.response_state == ResponseState.RESPONDING:
                        cancel_event = {
                            "event_id": f"evt_{uuid.uuid4().hex[:6]}",
                            "type": "response.cancel",
                            "response_id": STATE.current_response_id
                        }
                        await ws.send(json.dumps(cancel_event))
                        STATE.current_response_id = None
                        STATE.response_state = ResponseState.IDLE
                        
                    # Stop any ongoing playback
                    if STATE.audio.player:
                        STATE.audio.player.stop()
                        STATE.audio.player = None
                    
                elif event_type == "input_audio_buffer.speech_stopped":
                    if STATE.audio.display.current_line:
                        STATE.audio.display.complete_current_line()
                    
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript_text = event['transcript']
                    transcript.append(f"User: {transcript_text}")
                    STATE.audio.display.update_current_text(transcript_text)
                    STATE.audio.display.complete_current_line()
                    
                    # Handle system commands and tool execution
                    if transcript.lower().startswith(("can you", "please", "would you")):
                        try:
                            # Extract command/request
                            request = transcript.lower()
                            
                            # Handle file operations
                            if "show" in request and "contents" in request:
                                path = request.split("contents of")[-1].strip()
                                result = session_manager.execute_tool("file_read", {"path": path})
                                STATE.audio.display.update_current_text(f"Contents of {path}:\n{result}")
                            
                            # Handle directory listing
                            elif any(x in request for x in ["list", "show", "what's in"]):
                                path = "." if "this directory" in request else request.split("in")[-1].strip()
                                result = session_manager.execute_tool("list_directory", {"path": path})
                                STATE.audio.display.update_current_text(f"Directory contents:\n{', '.join(result)}")
                            
                            # Handle direct system commands
                            elif "run" in request and "command" in request:
                                cmd = request.split("command")[-1].strip()
                                result = session_manager.execute_system_command(cmd)
                                STATE.audio.display.update_current_text(f"Command output:\n{result}")
                                
                            STATE.audio.display.complete_current_line()
                            
                        except Exception as e:
                            STATE.audio.display.update_current_text(f"Error: {str(e)}")
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
        
        async with websockets.connect(
            RELAY_SERVER_URL,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
            max_size=10 * 1024 * 1024  # 10MB max message size
        ) as ws:
            print("Connected to relay server")
            # Set up signal handler
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(handle_interrupt(ws)))
            
            # Initialize session
            init_msg = {
                "type": "init_session",
                "session_config": session_manager.get_config()
            }
            await ws.send(json.dumps(init_msg))
            
            print("Starting chat session...")
            STATE.audio.is_recording = True
            STATE.response_state = ResponseState.IDLE
            
            # Run conversation and event handling loops with thought analysis
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
        print("\nConversation transcript:")
        for line in transcript:
            print(line)
        print("\nCLI interrupted.")
