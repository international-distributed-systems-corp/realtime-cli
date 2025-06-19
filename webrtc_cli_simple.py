#!/usr/bin/env python3
"""
Simple WebRTC CLI with real-time audio streaming and visualization
"""
import asyncio
import json
import os
import sys
import numpy as np
import pyaudio
import threading
import queue
import time
from datetime import datetime
import struct
import audioop

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
from aiortc.mediastreams import AudioStreamTrack
import av
import logging
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleAudioTrack(AudioStreamTrack):
    """Simple audio track for microphone input"""
    
    def __init__(self):
        super().__init__()
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=24000,
            input=True,
            frames_per_buffer=960
        )
        self._start = None
        self._timestamp = 0
        self._stopped = False
        self.frame_count = 0
        self.error_count = 0
        self.last_audio_level = 0
    
    async def recv(self):
        """Receive audio frame"""
        if self._stopped:
            raise Exception("Audio track stopped")
            
        if self._start is None:
            self._start = time.time()
        
        try:
            # Read audio from microphone with error handling
            if not self.stream or not self.stream.is_active():
                raise Exception("Stream is not active")
                
            audio_data = await asyncio.get_event_loop().run_in_executor(
                None, self.stream.read, 960, False
            )
            
            # Convert to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Calculate audio analytics
            self.frame_count += 1
            self.last_audio_level = np.abs(audio_array).mean() / 32768.0
            
            # Check for unusual audio characteristics
            if self.frame_count % 100 == 0:  # Log every 100 frames
                rms = audioop.rms(audio_data, 2)
                logger.info(f"Audio Analytics - Frame {self.frame_count}: Level={self.last_audio_level:.4f}, RMS={rms}")
            
            # Create audio frame
            frame = av.AudioFrame.from_ndarray(
                audio_array.reshape(1, -1),
                format='s16',
                layout='mono'
            )
            frame.sample_rate = 24000
            frame.pts = self._timestamp
            self._timestamp += len(audio_array)
            
            return frame
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Audio recv error #{self.error_count}: {e}")
            self._stopped = True
            raise
    
    def stop(self):
        """Stop audio capture"""
        self._stopped = True
        logger.info(f"Stopping audio track - Total frames: {self.frame_count}, Errors: {self.error_count}")
        
        if hasattr(self, 'stream') and self.stream:
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error stopping stream: {e}")
        if hasattr(self, 'p') and self.p:
            try:
                self.p.terminate()
            except Exception as e:
                logger.error(f"Error terminating PyAudio: {e}")

class RealtimeWebRTCCLI:
    """Simple WebRTC client for OpenAI Realtime API"""
    
    def __init__(self):
        self.pc = None
        self.data_channel = None
        self.audio_track = None
        self.output_stream = None
        self.p_out = pyaudio.PyAudio()
        self.connected = False
        self.messages = []
        self.output_frame_count = 0
        self.output_error_count = 0
        self.connection_start_time = None
        self.audio_pitch_samples = []
        
    def print_header(self):
        """Print header"""
        print("\n" + "="*60)
        print("🎙️  OpenAI Realtime WebRTC CLI")
        print("="*60)
        print("Status: Connecting...")
        print("")
    
    def print_status(self, message):
        """Print status update"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def visualize_audio_level(self, level):
        """Simple audio level visualization"""
        bar_length = int(level * 50)
        bar = "█" * bar_length + "░" * (50 - bar_length)
        return bar
    
    async def connect(self):
        """Connect to OpenAI Realtime API"""
        self.print_status("Connecting to OpenAI Realtime API...")
        
        # Get API key
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        self.model = 'gpt-4o-realtime-preview-2025-06-03'
        
        # Setup WebRTC
        self.print_status("Setting up WebRTC connection...")
        self.pc = RTCPeerConnection(
            configuration=RTCConfiguration(
                iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
            )
        )
        
        # Connection state monitoring
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            self.print_status(f"Connection state: {self.pc.connectionState}")
            if self.pc.connectionState == "connected" and not self.connection_start_time:
                self.connection_start_time = time.time()
            elif self.pc.connectionState == "failed":
                logger.error("WebRTC connection failed")
                if self.connection_start_time:
                    duration = time.time() - self.connection_start_time
                    logger.info(f"Connection lasted {duration:.1f} seconds")
        
        # Add audio track
        self.audio_track = SimpleAudioTrack()
        self.pc.addTrack(self.audio_track)
        self.print_status("Microphone initialized")
        
        # Handle incoming audio
        @self.pc.on("track")
        def on_track(track):
            if track.kind == "audio":
                self.print_status("Receiving audio from AI")
                asyncio.create_task(self.handle_audio_output(track))
        
        # Create data channel BEFORE creating offer
        self.data_channel = self.pc.createDataChannel("oai-events")
        
        @self.data_channel.on("open")
        def on_open():
            self.connected = True
            self.print_status("✅ Data channel opened! Initializing session...")
            
            # Initialize session
            asyncio.create_task(self.initialize_session())
        
        @self.data_channel.on("message")
        def on_message(message):
            try:
                msg = json.loads(message)
                self.handle_message(msg)
            except Exception as e:
                self.print_status(f"Message error: {e}")
        
        @self.data_channel.on("close")
        def on_close():
            self.print_status("Data channel closed")
            self.connected = False
        
        # Create offer AFTER setting up data channel
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        
        # Get answer
        answer_response = requests.post(
            f'https://api.openai.com/v1/realtime?model={self.model}',
            data=offer.sdp,
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/sdp'
            }
        )
        
        if answer_response.status_code not in [200, 201]:
            raise Exception(f"Failed to get answer: {answer_response.text}")
        
        answer_sdp = answer_response.content.decode()
        answer = RTCSessionDescription(sdp=answer_sdp, type="answer")
        await self.pc.setRemoteDescription(answer)
        
        # Wait for connection
        await self.wait_for_connection()
        
        self.print_status("WebRTC connection established!")
    
    async def wait_for_connection(self, timeout=10):
        """Wait for WebRTC connection to be established"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.pc.connectionState == "connected":
                return
            await asyncio.sleep(0.1)
        raise Exception("Connection timeout")
    
    async def initialize_session(self):
        """Initialize the session with OpenAI"""
        try:
            # Send session update
            self.data_channel.send(json.dumps({
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "voice": "alloy",
                    "turn_detection": {"type": "server_vad"},
                    "instructions": "You are a helpful AI assistant. Keep responses concise."
                }
            }))
            self.print_status("Session initialized")
        except Exception as e:
            self.print_status(f"Failed to initialize session: {e}")
    
    async def handle_audio_output(self, track):
        """Handle incoming audio from AI"""
        if not self.output_stream:
            self.output_stream = self.p_out.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True,
                frames_per_buffer=960
            )
        
        logger.info("Starting audio output handler")
        
        while True:
            try:
                # Get next frame with timeout
                frame = await asyncio.wait_for(track.recv(), timeout=5.0)
                
                # Convert to audio data
                audio_data = frame.to_ndarray().flatten()
                audio_bytes = audio_data.astype(np.int16).tobytes()
                
                # Analyze audio for pitch detection
                self.output_frame_count += 1
                
                # Calculate and display level
                level = np.abs(audio_data).mean() / 32768.0
                rms = audioop.rms(audio_bytes, 2)
                
                # Simple pitch detection using zero-crossing rate (only for non-silent audio)
                if level > 0.001 and rms > 100:  # Only detect pitch for audible audio
                    zero_crossings = np.where(np.diff(np.sign(audio_data)))[0]
                    if len(zero_crossings) > 0:
                        zcr = len(zero_crossings) / len(audio_data)
                        estimated_freq = zcr * 24000 / 2  # Rough frequency estimate
                        
                        # Only track reasonable frequency values
                        if 50 <= estimated_freq <= 8000:
                            if len(self.audio_pitch_samples) < 100:
                                self.audio_pitch_samples.append(estimated_freq)
                            else:
                                self.audio_pitch_samples.pop(0)
                                self.audio_pitch_samples.append(estimated_freq)
                
                # Log analytics every 50 frames
                if self.output_frame_count % 50 == 0 and self.audio_pitch_samples:
                    avg_pitch = np.mean(self.audio_pitch_samples)
                    logger.info(f"Output Audio Analytics - Frame {self.output_frame_count}: Level={level:.4f}, RMS={rms}, Avg Freq={avg_pitch:.1f}Hz")
                
                if level > 0.01:
                    print(f"\r🔊 AI Speaking: {self.visualize_audio_level(level)}", end="", flush=True)
                
                # Play audio
                self.output_stream.write(audio_bytes)
                
            except asyncio.TimeoutError:
                await asyncio.sleep(0.1)
            except Exception as e:
                self.output_error_count += 1
                logger.error(f"Audio output error #{self.output_error_count}: {e}")
                logger.info(f"Output stats - Frames: {self.output_frame_count}, Errors: {self.output_error_count}")
                break
    
    def handle_message(self, message):
        """Handle incoming messages"""
        msg_type = message.get('type', '')
        
        if msg_type == 'response.audio_transcript.delta':
            # AI is speaking - show transcript
            transcript = message.get('delta', '')
            print(f"\n🤖 AI: {transcript}", end="", flush=True)
            
        elif msg_type == 'input_audio_buffer.speech_started':
            print("\n🎤 Listening...", end="", flush=True)
            
        elif msg_type == 'conversation.item.input_audio_transcription.completed':
            transcript = message.get('transcript', '')
            print(f"\n👤 You: {transcript}")
            
        elif msg_type == 'response.done':
            print("\n")  # New line after AI response
            
        elif msg_type == 'error':
            error = message.get('error', {})
            print(f"\n❌ Error: {error.get('message', 'Unknown error')}")
    
    async def send_text(self, text):
        """Send text message"""
        if self.data_channel and self.data_channel.readyState == 'open':
            self.data_channel.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}]
                }
            }))
            self.data_channel.send(json.dumps({"type": "response.create"}))
            print(f"👤 You: {text}")
    
    async def run_input_loop(self):
        """Handle user text input"""
        # Check if we're running with piped input
        is_piped = not sys.stdin.isatty()
        
        while True:
            try:
                # Get input in executor to not block
                if is_piped:
                    # For piped input, read without prompt
                    text = await asyncio.get_event_loop().run_in_executor(
                        None, sys.stdin.readline
                    )
                    if not text:  # EOF reached
                        break
                    text = text.strip()
                else:
                    # For interactive mode, show prompt
                    text = await asyncio.get_event_loop().run_in_executor(
                        None, input, "\n💬 Type message (or 'quit' to exit): "
                    )
                
                if text.lower() in ['quit', 'exit']:
                    break
                    
                if text.strip():
                    await self.send_text(text)
                    # For piped input, wait longer for audio response
                    if is_piped:
                        await asyncio.sleep(10)  # Wait 10 seconds for full audio response
                    
            except EOFError:
                break
            except Exception as e:
                if is_piped:
                    break
                await asyncio.sleep(0.1)
    
    async def run(self):
        """Run the client"""
        try:
            self.print_header()
            
            # Connect to API
            await self.connect()
            
            # Run input loop
            await self.run_input_loop()
            
        except KeyboardInterrupt:
            print("\n\nShutting down...")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        finally:
            # Print final analytics
            print("\n\n" + "="*60)
            print("📊 Session Analytics:")
            print("="*60)
            
            if self.connection_start_time:
                duration = time.time() - self.connection_start_time
                print(f"Connection Duration: {duration:.1f} seconds")
            
            if self.audio_track:
                print(f"Input Audio - Frames: {self.audio_track.frame_count}, Errors: {self.audio_track.error_count}")
                
            print(f"Output Audio - Frames: {self.output_frame_count}, Errors: {self.output_error_count}")
            
            if self.audio_pitch_samples:
                avg_pitch = np.mean(self.audio_pitch_samples)
                min_pitch = np.min(self.audio_pitch_samples)
                max_pitch = np.max(self.audio_pitch_samples)
                print(f"Output Pitch Analysis - Avg: {avg_pitch:.1f}Hz, Min: {min_pitch:.1f}Hz, Max: {max_pitch:.1f}Hz")
            
            print("="*60)
            
            # Cleanup
            if self.audio_track:
                try:
                    self.audio_track.stop()
                except:
                    pass
            if self.output_stream:
                try:
                    if self.output_stream.is_active():
                        self.output_stream.stop_stream()
                    self.output_stream.close()
                except:
                    pass
            if self.p_out:
                try:
                    self.p_out.terminate()
                except:
                    pass
            if self.pc:
                try:
                    await self.pc.close()
                except:
                    pass

async def main():
    """Main entry point"""
    client = RealtimeWebRTCCLI()
    await client.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")