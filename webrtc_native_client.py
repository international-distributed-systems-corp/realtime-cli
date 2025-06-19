#!/usr/bin/env python3
"""
Native Python WebRTC client for OpenAI Realtime API
Uses aiortc to connect directly to OpenAI without browser dependency
"""
import asyncio
import json
import logging
import os
import pyaudio
import base64
import requests
from getpass import getpass
from aiortc import RTCPeerConnection, RTCDataChannel, RTCSessionDescription, RTCConfiguration, RTCIceServer, MediaStreamTrack
from aiortc.contrib.media import MediaPlayer
import threading
from queue import Queue, Empty
import signal
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AudioStreamTrack(MediaStreamTrack):
    """Dummy audio track for WebRTC connection"""
    kind = "audio"
    
    def __init__(self):
        super().__init__()
        self.sample_rate = 24000
        self.channels = 1
    
    async def recv(self):
        # This would normally return audio frames
        # For now, return silence
        import numpy as np
        import av
        
        # Create silence samples as numpy array
        # AudioFrame.from_ndarray expects a 2D array with shape (channels, samples)
        samples = np.zeros((1, 480), dtype=np.int16)
        
        # Create audio frame from numpy array
        frame = av.AudioFrame.from_ndarray(samples, format='s16', layout='mono')
        frame.sample_rate = self.sample_rate
        frame.pts = getattr(self, '_pts', 0)
        self._pts = getattr(self, '_pts', 0) + 480
        
        return frame

class AudioCapture:
    """Audio capture using PyAudio for WebRTC"""
    
    def __init__(self, sample_rate=24000, chunk_size=512, channels=1):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.running = False
        self.audio_queue = Queue()
        
    def start_capture(self):
        """Start audio capture"""
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )
            self.stream.start_stream()
            self.running = True
            logger.info("Audio capture started")
        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            raise
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for captured audio"""
        if self.running:
            self.audio_queue.put(in_data)
        return (in_data, pyaudio.paContinue)
    
    def get_audio_data(self, timeout=0.1):
        """Get captured audio data"""
        try:
            return self.audio_queue.get(timeout=timeout)
        except Empty:
            return None
    
    def stop_capture(self):
        """Stop audio capture"""
        self.running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()
        logger.info("Audio capture stopped")

class NativeWebRTCClient:
    """Native Python WebRTC client for OpenAI Realtime API"""
    
    def __init__(self, openai_api_key, model="gpt-4o-realtime-preview-2025-06-03"):
        self.openai_api_key = openai_api_key
        self.model = model
        self.pc = None
        self.data_channel = None
        self.audio_capture = None
        self.session_active = False
        self.running = True
        
        # Session configuration following webrtcHacks guide
        self.session_config = {
            "model": model,
            "voice": "verse",
            "modalities": ["text", "audio"],
            "instructions": """You are a helpful AI assistant with computer control capabilities.
            You can control the computer using mouse, keyboard and run commands.
            Use the computer tools naturally as part of our conversation.""",
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500,
                "create_response": True,
                "interrupt_response": True
            },
            "input_audio_transcription": {"model": "whisper-1"},
            "temperature": 0.8
        }
    
    async def connect_to_openai(self):
        """Connect directly to OpenAI Realtime API via WebRTC"""
        try:
            logger.info("Connecting to OpenAI Realtime API via WebRTC...")
            
            # Create peer connection
            configuration = RTCConfiguration(
                iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
            )
            self.pc = RTCPeerConnection(configuration=configuration)
            
            # Set up audio capture
            self.audio_capture = AudioCapture()
            
            # Add audio track
            logger.info("Setting up audio stream...")
            audio_track = AudioStreamTrack()
            self.pc.addTrack(audio_track)
            
            # Create data channel for messaging
            self.data_channel = self.pc.createDataChannel("oai-events")
            
            @self.data_channel.on("open")
            def on_open():
                logger.info("Data channel opened")
                asyncio.create_task(self.initialize_session())
            
            @self.data_channel.on("message")
            def on_message(message):
                try:
                    event = json.loads(message)
                    asyncio.create_task(self.handle_server_event(event))
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
            
            @self.data_channel.on("close")
            def on_close():
                logger.info("Data channel closed")
                self.session_active = False
            
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
            
            # Create offer
            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)
            
            # Send offer to OpenAI
            base_url = "https://api.openai.com/v1/realtime"
            response = await self.fetch_openai_answer(base_url, self.pc.localDescription.sdp)
            
            # Set remote description
            answer = RTCSessionDescription(sdp=response, type="answer")
            await self.pc.setRemoteDescription(answer)
            
            # Wait for connection
            await self.wait_for_connection()
            
            logger.info("Successfully connected to OpenAI Realtime API!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to OpenAI: {e}")
            return False
    
    async def fetch_openai_answer(self, base_url, offer_sdp):
        """Fetch SDP answer from OpenAI API"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}?model={self.model}",
                data=offer_sdp,
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/sdp"
                }
            ) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    logger.error(f"OpenAI API error response: {error_text}")
                    raise Exception(f"OpenAI API request failed: {response.status} - {error_text}")
                return await response.text()
    
    async def wait_for_connection(self, timeout=10):
        """Wait for WebRTC connection to be established"""
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            if self.pc.connectionState == "connected":
                return
            await asyncio.sleep(0.1)
        raise Exception("Connection timeout")
    
    async def initialize_session(self):
        """Initialize the session with OpenAI"""
        try:
            # Send session update
            await self.send_message({
                "type": "session.update",
                "session": self.session_config
            })
            
            # Send greeting request
            await self.send_message({
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "instructions": "Greet the user and let them know you're ready to help with computer tasks.",
                    "max_output_tokens": 100
                }
            })
            
            logger.info("Session initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize session: {e}")
    
    async def send_message(self, message):
        """Send message to OpenAI via data channel"""
        try:
            if self.data_channel and self.data_channel.readyState == "open":
                message_str = json.dumps(message)
                self.data_channel.send(message_str)
            else:
                logger.warning("Data channel not ready for sending")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    async def handle_server_event(self, event):
        """Handle events from OpenAI"""
        event_type = event.get("type", "")
        
        if event_type == "session.created":
            logger.info("Session created successfully")
            
        elif event_type == "response.text.delta":
            # Print response text as it streams
            delta = event.get("delta", "")
            print(delta, end="", flush=True)
            
        elif event_type == "response.text.done":
            print()  # New line after response
            
        elif event_type == "response.audio.delta":
            # Handle audio response (would need audio playback implementation)
            logger.debug("Received audio delta")
            
        elif event_type == "input_audio_buffer.speech_started":
            print("🎙️ Speech detected...")
            
        elif event_type == "input_audio_buffer.speech_stopped":
            print("⏸️ Speech stopped, processing...")
            
        elif event_type == "conversation.item.input_audio_transcription.completed":
            transcript = event.get("transcript", "")
            print(f"You: {transcript}")
            
        elif event_type == "response.done":
            print("\\n🤖 Response complete. You can speak or type your next message.")
            
        elif event_type == "error":
            error_msg = event.get("error", {}).get("message", "Unknown error")
            logger.error(f"OpenAI error: {error_msg}")
            
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
            
            # Request response
            await self.send_message({
                "type": "response.create"
            })
            
        except Exception as e:
            logger.error(f"Error sending text message: {e}")
    
    async def start_audio_streaming(self):
        """Start streaming audio to OpenAI"""
        try:
            if not self.audio_capture:
                return
                
            self.audio_capture.start_capture()
            
            while self.session_active and self.running:
                audio_data = self.audio_capture.get_audio_data()
                if audio_data:
                    # Encode audio as base64
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    
                    # Send to OpenAI
                    await self.send_message({
                        "type": "input_audio_buffer.append",
                        "audio": audio_base64
                    })
                
                await asyncio.sleep(0.01)  # Small delay to prevent overwhelming
                
        except Exception as e:
            logger.error(f"Error in audio streaming: {e}")
        finally:
            if self.audio_capture:
                self.audio_capture.stop_capture()
    
    async def run_interactive_session(self):
        """Run interactive session with text input"""
        print("\\n" + "="*60)
        print("🎙️ OpenAI Realtime WebRTC CLI (Native Python)")
        print("="*60)
        print("Commands:")
        print("  Type your message and press Enter")
        print("  Type 'quit' or 'exit' to end session")
        print("  Type 'audio' to start audio streaming")
        print("="*60)
        
        # Store the main loop reference
        main_loop = asyncio.get_event_loop()
        
        def input_handler():
            """Handle user input in separate thread"""
            while self.running and self.session_active:
                try:
                    user_input = input("\\n> ").strip()
                    if user_input.lower() in ['quit', 'exit']:
                        self.running = False
                        break
                    elif user_input.lower() == 'audio':
                        print("Starting audio capture... (this is a demo)")
                        asyncio.run_coroutine_threadsafe(
                            self.start_audio_streaming(), 
                            main_loop
                        )
                    elif user_input:
                        asyncio.run_coroutine_threadsafe(
                            self.send_text_message(user_input),
                            main_loop
                        )
                except EOFError:
                    self.running = False
                    break
                except Exception as e:
                    logger.error(f"Input error: {e}")
        
        # Start input handler in separate thread
        input_thread = threading.Thread(target=input_handler, daemon=False)
        input_thread.start()
        
        # Main loop
        try:
            while self.running and self.session_active:
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        
        # Wait for input thread to finish
        input_thread.join(timeout=1.0)
        
        logger.info("Interactive session ended")
    
    async def cleanup(self):
        """Clean up resources"""
        self.running = False
        self.session_active = False
        
        if self.audio_capture:
            self.audio_capture.stop_capture()
            
        if self.data_channel:
            self.data_channel.close()
            
        if self.pc:
            await self.pc.close()
            
        logger.info("Cleanup completed")

async def main():
    """Main function"""
    print("🚀 OpenAI Realtime API - Native WebRTC Client")
    print("=" * 50)
    
    # Get OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        api_key = getpass("OpenAI API Key: ")
    
    if not api_key:
        print("❌ OpenAI API key is required")
        return 1
    
    client = None
    try:
        # Create client
        client = NativeWebRTCClient(api_key)
        
        # Set up signal handlers
        def signal_handler(signum, frame):
            print("\\n🛑 Shutting down...")
            client.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Connect to OpenAI
        if await client.connect_to_openai():
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
        try:
            import aiohttp
        except ImportError:
            print("❌ Missing dependency: pip install aiohttp")
            sys.exit(1)
            
        # Run client
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\\n👋 Interrupted")
        sys.exit(0)