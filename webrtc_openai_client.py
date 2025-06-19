#!/usr/bin/env python3
"""
OpenAI Realtime API WebRTC Client
Based on the webrtcHacks guide: https://webrtchacks.com/openai-webrtc-guide/
Native Python implementation with proper audio handling and event processing
"""
import asyncio
import json
import logging
import os
import pyaudio
import numpy as np
import base64
from getpass import getpass
from aiortc import RTCPeerConnection, RTCDataChannel, RTCSessionDescription, RTCConfiguration, RTCIceServer, MediaStreamTrack
import av
import threading
from queue import Queue, Empty
import signal
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_SESSION_INSTRUCTIONS = """You are a friendly assistant. 
Speak in a natural, conversational tone. 
Your knowledge cut-off is October 2023."""

DEFAULT_START_INSTRUCTIONS = "Greet the user and ask how you can help them today."

class AudioPlaybackHandler:
    """Handles audio playback using PyAudio"""
    
    def __init__(self, sample_rate=24000, channels=1, chunk_size=1024):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.audio_queue = Queue()
        self.playing = False
        self.thread = None
        
    def start(self):
        """Start audio playback"""
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=self.chunk_size
            )
            self.playing = True
            self.thread = threading.Thread(target=self._playback_thread)
            self.thread.start()
            logger.info("Audio playback started")
        except Exception as e:
            logger.error(f"Failed to start audio playback: {e}")
            
    def _playback_thread(self):
        """Thread that plays audio from queue"""
        while self.playing:
            try:
                audio_data = self.audio_queue.get(timeout=0.1)
                if self.stream and self.playing:
                    self.stream.write(audio_data)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Audio playback error: {e}")
                
    def add_audio(self, audio_data):
        """Add audio data to playback queue"""
        if self.playing:
            self.audio_queue.put(audio_data)
            
    def stop(self):
        """Stop audio playback"""
        self.playing = False
        if self.thread:
            self.thread.join()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()
        logger.info("Audio playback stopped")

class MicrophoneStreamTrack(MediaStreamTrack):
    """Audio track that captures from microphone"""
    kind = "audio"
    
    def __init__(self, sample_rate=24000, channels=1):
        super().__init__()
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.running = False
        self.audio_queue = Queue()
        self._start_capture()
        
    def _start_capture(self):
        """Start capturing audio from microphone"""
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=480,  # 20ms at 24kHz
                stream_callback=self._audio_callback
            )
            self.stream.start_stream()
            self.running = True
            logger.info("Microphone capture started")
        except Exception as e:
            logger.error(f"Failed to start microphone capture: {e}")
            raise
            
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for captured audio"""
        if self.running:
            self.audio_queue.put(in_data)
        return (in_data, pyaudio.paContinue)
        
    async def recv(self):
        """Return an audio frame for WebRTC"""
        try:
            # Get audio data from queue
            audio_data = await asyncio.get_event_loop().run_in_executor(
                None, self.audio_queue.get, True, 0.1
            )
            
            # Convert bytes to numpy array
            samples = np.frombuffer(audio_data, dtype=np.int16)
            
            # Reshape for av.AudioFrame (needs shape: [channels, samples])
            samples = samples.reshape(1, -1)
            
            # Create audio frame
            frame = av.AudioFrame.from_ndarray(samples, format='s16', layout='mono')
            frame.sample_rate = self.sample_rate
            frame.pts = getattr(self, '_pts', 0)
            self._pts = getattr(self, '_pts', 0) + len(samples[0])
            
            return frame
        except Empty:
            # Return silence if no audio available
            samples = np.zeros((1, 480), dtype=np.int16)
            frame = av.AudioFrame.from_ndarray(samples, format='s16', layout='mono')
            frame.sample_rate = self.sample_rate
            frame.pts = getattr(self, '_pts', 0)
            self._pts = getattr(self, '_pts', 0) + 480
            return frame
            
    def stop(self):
        """Stop audio capture"""
        self.running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()

class OpenAIWebRTCClient:
    """WebRTC client for OpenAI Realtime API following webrtcHacks guide"""
    
    def __init__(self, api_key, model="gpt-4o-realtime-preview-2025-06-03"):
        self.api_key = api_key
        self.model = model
        self.pc = None
        self.data_channel = None
        self.microphone_track = None
        self.audio_playback = None
        self.session_active = False
        self.running = True
        self.current_assistant_message = ""
        self.audio_buffer = bytearray()
        
        # Session configuration
        self.session_config = {
            "instructions": DEFAULT_SESSION_INSTRUCTIONS,
            "voice": "alloy",
            "temperature": 0.8,
            "input_audio_transcription": {"model": "whisper-1"},
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 200,
                "create_response": True,
                "interrupt_response": True
            }
        }
        
        # Function definitions
        self.gpt_functions = [
            {
                "type": "function",
                "name": "end_session",
                "description": "the user would like to stop interacting with the Agent",
                "parameters": {}
            }
        ]
        
    async def connect(self):
        """Connect to OpenAI Realtime API via WebRTC"""
        try:
            logger.info("Connecting to OpenAI Realtime API via WebRTC...")
            
            # Create RTCPeerConnection
            self.pc = RTCPeerConnection()
            
            # Set up connection state monitoring
            @self.pc.on("connectionstatechange")
            async def on_connection_state_change():
                logger.info(f"Connection state: {self.pc.connectionState}")
                if self.pc.connectionState == "connected":
                    logger.info("WebRTC connection established!")
                    self.session_active = True
                elif self.pc.connectionState in ["closed", "failed"]:
                    logger.info("WebRTC connection lost")
                    self.session_active = False
                    self.running = False
            
            # Handle incoming audio track
            @self.pc.on("track")
            def on_track(track):
                logger.info(f"Received {track.kind} track")
                if track.kind == "audio":
                    # Start audio playback handler
                    self.audio_playback = AudioPlaybackHandler()
                    self.audio_playback.start()
                    
                    @track.on("ended")
                    def on_ended():
                        logger.info("Remote audio track ended")
            
            # Set up microphone capture and add track
            logger.info("Setting up audio stream...")
            self.microphone_track = MicrophoneStreamTrack()
            self.pc.addTrack(self.microphone_track)
            
            # Create data channel
            self.data_channel = self.pc.createDataChannel("oai-events")
            
            @self.data_channel.on("open")
            def on_open():
                logger.info("Data channel opened")
                asyncio.create_task(self.session_start_messages())
            
            @self.data_channel.on("message")
            def on_message(message):
                try:
                    event = json.loads(message)
                    asyncio.create_task(self.handle_event(event))
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
            
            @self.data_channel.on("close")
            def on_close():
                logger.info("Data channel closed")
                self.session_active = False
            
            # Create offer and set local description
            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)
            
            # Send offer to OpenAI and get answer
            base_url = "https://api.openai.com/v1/realtime"
            response = await self.fetch_openai_answer(base_url, self.pc.localDescription.sdp)
            
            # Set remote description
            answer = RTCSessionDescription(sdp=response, type="answer")
            await self.pc.setRemoteDescription(answer)
            
            # Wait for connection to be established
            await self.wait_for_connection()
            
            logger.info("Successfully connected to OpenAI Realtime API!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    async def fetch_openai_answer(self, base_url, offer_sdp):
        """Fetch SDP answer from OpenAI API"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}?model={self.model}",
                data=offer_sdp,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/sdp"
                }
            ) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    raise Exception(f"OpenAI API error: {response.status} - {error_text}")
                return await response.text()
    
    async def wait_for_connection(self, timeout=10):
        """Wait for WebRTC connection to be established"""
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            if self.pc.connectionState == "connected":
                return
            await asyncio.sleep(0.1)
        raise Exception(f"Connection timeout. Current state: {self.pc.connectionState}")
    
    async def session_start_messages(self):
        """Send initial session configuration and greeting"""
        try:
            # Send session update with configuration
            session_update = {
                "type": "session.update",
                "session": {
                    "instructions": self.session_config["instructions"],
                    "voice": self.session_config["voice"],
                    "tools": self.gpt_functions,
                    "tool_choice": "auto",
                    "input_audio_transcription": self.session_config["input_audio_transcription"],
                    "temperature": self.session_config["temperature"],
                    "turn_detection": self.session_config["turn_detection"]
                }
            }
            await self.send_message(session_update)
            
            # Send initial greeting
            start_message = {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "instructions": DEFAULT_START_INSTRUCTIONS,
                    "max_output_tokens": 100
                }
            }
            await self.send_message(start_message)
            
            logger.info("Session initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize session: {e}")
    
    async def send_message(self, message):
        """Send message via data channel"""
        if self.data_channel and self.data_channel.readyState == "open":
            self.data_channel.send(json.dumps(message))
        else:
            logger.warning("Data channel not ready for sending")
    
    async def handle_event(self, event):
        """Handle incoming events from OpenAI"""
        event_type = event.get("type", "")
        
        if event_type == "session.created":
            logger.info("Session created successfully")
            session = event.get("session", {})
            logger.debug(f"Session defaults: {json.dumps(session, indent=2)}")
            
        elif event_type == "input_audio_buffer.speech_started":
            print("\n🎙️  User speaking...")
            
        elif event_type == "conversation.item.input_audio_transcription.completed":
            transcript = event.get("transcript", "")
            print(f"\nYou: {transcript}")
            
        elif event_type == "response.audio_transcript.delta":
            delta = event.get("delta", "")
            self.current_assistant_message += delta
            print(delta, end="", flush=True)
            
        elif event_type == "response.audio_transcript.done":
            print()  # New line after complete transcript
            self.current_assistant_message = ""
            
        elif event_type == "response.function_call_arguments.done":
            name = event.get("name", "")
            if name == "end_session":
                logger.info("Ending session based on user request")
                await self.end_session("Thank you for chatting with me. Have a great day!")
                
        elif event_type == "response.audio.delta":
            # Handle audio playback
            if self.audio_playback and "delta" in event:
                audio_base64 = event["delta"]
                audio_data = base64.b64decode(audio_base64)
                self.audio_playback.add_audio(audio_data)
                
        elif event_type == "response.audio.done":
            logger.debug("Audio response complete")
            
        elif event_type == "response.done":
            print("\n💬 Response complete. You can speak or type your message.")
            
        elif event_type == "error":
            error = event.get("error", {})
            logger.error(f"Error from OpenAI: {error}")
            
        else:
            logger.debug(f"Unhandled event type: {event_type}")
    
    async def send_text_message(self, text):
        """Send a text message to OpenAI"""
        try:
            # Create conversation item
            await self.send_message({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{
                        "type": "input_text",
                        "text": text
                    }]
                }
            })
            
            # Trigger response
            await self.send_message({
                "type": "response.create"
            })
            
        except Exception as e:
            logger.error(f"Error sending text message: {e}")
    
    async def end_session(self, goodbye_message=None):
        """End the session gracefully"""
        if goodbye_message and self.data_channel and self.data_channel.readyState == "open":
            # Send goodbye message
            await self.send_message({
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "instructions": goodbye_message,
                    "max_output_tokens": 200
                }
            })
            
            # Wait a bit for the response to complete
            await asyncio.sleep(3)
        
        self.running = False
        self.session_active = False
    
    async def run_interactive_session(self):
        """Run interactive session with user input"""
        print("\n" + "="*60)
        print("🎤 OpenAI Realtime WebRTC Client")
        print("="*60)
        print("Commands:")
        print("  - Type your message and press Enter")
        print("  - Type 'quit' or 'exit' to end session")
        print("  - Just speak naturally for voice interaction")
        print("="*60)
        
        # Start a separate thread for user input
        main_loop = asyncio.get_event_loop()
        
        def input_handler():
            """Handle user input in separate thread"""
            while self.running and self.session_active:
                try:
                    user_input = input("\n> ").strip()
                    if user_input.lower() in ['quit', 'exit']:
                        asyncio.run_coroutine_threadsafe(
                            self.end_session("Goodbye! It was nice talking with you."),
                            main_loop
                        )
                        break
                    elif user_input:
                        print(f"\nYou: {user_input}")
                        asyncio.run_coroutine_threadsafe(
                            self.send_text_message(user_input),
                            main_loop
                        )
                except EOFError:
                    break
                except Exception as e:
                    logger.error(f"Input error: {e}")
        
        input_thread = threading.Thread(target=input_handler, daemon=True)
        input_thread.start()
        
        # Main event loop
        try:
            while self.running and self.session_active:
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        
        logger.info("Interactive session ended")
    
    async def cleanup(self):
        """Clean up resources"""
        self.running = False
        self.session_active = False
        
        if self.microphone_track:
            self.microphone_track.stop()
            
        if self.audio_playback:
            self.audio_playback.stop()
            
        if self.data_channel:
            self.data_channel.close()
            
        if self.pc:
            await self.pc.close()
            
        logger.info("Cleanup completed")

async def main():
    """Main function"""
    print("🚀 OpenAI Realtime API - WebRTC Client")
    print("="*50)
    
    # Get OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        api_key = getpass("Enter your OpenAI API Key: ")
    
    if not api_key:
        print("❌ OpenAI API key is required")
        return 1
    
    client = None
    try:
        # Create and connect client
        client = OpenAIWebRTCClient(api_key)
        
        # Set up signal handlers
        def signal_handler(signum, frame):
            print("\n🛑 Shutting down...")
            if client:
                client.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Connect to OpenAI
        if await client.connect():
            # Run interactive session
            await client.run_interactive_session()
        else:
            print("❌ Failed to connect to OpenAI")
            return 1
            
    except Exception as e:
        logger.error(f"Client error: {e}")
        return 1
    finally:
        if client:
            await client.cleanup()
    
    print("👋 Session ended")
    return 0

if __name__ == "__main__":
    try:
        # Check dependencies
        required_packages = ['aiohttp', 'aiortc', 'pyaudio', 'av', 'numpy']
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            print(f"❌ Missing dependencies: {', '.join(missing_packages)}")
            print(f"Install with: pip install {' '.join(missing_packages)}")
            sys.exit(1)
        
        # Run the client
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n👋 Interrupted")
        sys.exit(0)