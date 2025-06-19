#!/usr/bin/env python3
"""
Enhanced WebRTC CLI with real-time audio visualization and streaming
"""
import asyncio
import json
import os
import sys
import numpy as np
from datetime import datetime
import pyaudio
import threading
import queue
from collections import deque
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaPlayer, MediaRelay
from aiortc.mediastreams import AudioStreamTrack
import av
import logging
import requests
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

console = Console()

class AudioLevelTrack(AudioStreamTrack):
    """Custom audio track that provides level monitoring"""
    
    def __init__(self, device_index=None):
        super().__init__()
        self.device_index = device_index
        self._start = None
        self._timestamp = 0
        
        # PyAudio setup
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=24000,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=960,
            stream_callback=self._audio_callback
        )
        
        self.audio_queue = queue.Queue()
        self.current_level = 0.0
        
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback to capture audio"""
        self.audio_queue.put(in_data)
        
        # Calculate audio level
        audio_data = np.frombuffer(in_data, dtype=np.int16)
        if len(audio_data) > 0:
            self.current_level = np.abs(audio_data).mean() / 32768.0
        
        return (None, pyaudio.paContinue)
    
    async def recv(self):
        """Receive audio frame"""
        if self._start is None:
            self._start = time.time()
        
        # Get audio data
        try:
            audio_data = await asyncio.get_event_loop().run_in_executor(
                None, self.audio_queue.get, True, 0.1
            )
        except queue.Empty:
            # Generate silence if no audio
            audio_data = b'\x00' * 1920
        
        # Convert to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
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
    
    def stop(self):
        """Stop audio capture"""
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
        if hasattr(self, 'p'):
            self.p.terminate()

class RealtimeWebRTCClient:
    """Enhanced WebRTC client with real-time visualization"""
    
    def __init__(self):
        self.pc = None
        self.data_channel = None
        self.audio_track = None
        self.audio_player = None
        
        # Audio levels
        self.input_level = 0.0
        self.output_level = 0.0
        self.level_history = deque(maxlen=50)
        
        # Message queues
        self.send_queue = asyncio.Queue()
        self.receive_queue = asyncio.Queue()
        
        # State
        self.connected = False
        self.speaking = False
        self.ai_speaking = False
        self.last_activity = time.time()
        
        # UI elements
        self.layout = Layout()
        self.setup_ui()
        
        # PyAudio for output
        self.p_out = pyaudio.PyAudio()
        self.output_stream = None
        
    def setup_ui(self):
        """Setup the terminal UI layout"""
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="audio_viz", size=8),
            Layout(name="messages", size=15),
            Layout(name="input", size=3)
        )
    
    def create_header(self):
        """Create header panel"""
        status = "🟢 Connected" if self.connected else "🔴 Disconnected"
        header_text = Text.from_markup(
            f"[bold cyan]🎙️ OpenAI Realtime WebRTC CLI[/bold cyan] | {status} | [dim]{datetime.now().strftime('%H:%M:%S')}[/dim]"
        )
        return Panel(header_text, style="bold white on blue")
    
    def create_audio_viz(self):
        """Create audio visualization panel"""
        table = Table(show_header=False, box=None, padding=0)
        
        # Input level
        input_bar = "█" * int(self.input_level * 50)
        input_bar = input_bar.ljust(50, "░")
        
        # Output level  
        output_bar = "█" * int(self.output_level * 50)
        output_bar = output_bar.ljust(50, "░")
        
        # Level history graph
        history_graph = ""
        for level in self.level_history:
            height = int(level * 5)
            history_graph += "▁▂▃▄▅▆▇█"[min(height, 7)]
        
        table.add_row(
            Text("🎤 Input  ", style="cyan"),
            Text(input_bar, style="green" if self.speaking else "dim green")
        )
        table.add_row(
            Text("🔊 Output ", style="cyan"),
            Text(output_bar, style="yellow" if self.ai_speaking else "dim yellow")
        )
        table.add_row(
            Text("📊 History", style="cyan"),
            Text(history_graph, style="blue")
        )
        
        return Panel(table, title="Audio Levels", border_style="cyan")
    
    def create_messages(self):
        """Create messages panel"""
        messages = []
        
        # Add recent messages (this would be populated from actual messages)
        if hasattr(self, 'recent_messages'):
            for msg in self.recent_messages[-10:]:
                messages.append(msg)
        
        content = "\n".join(messages) if messages else "[dim]Waiting for conversation...[/dim]"
        return Panel(content, title="Conversation", border_style="green")
    
    def create_input(self):
        """Create input panel"""
        mode = "🎤 Voice Active" if self.speaking else "⌨️  Type Message"
        help_text = "[dim]Press Ctrl+C to exit | Audio streaming active[/dim]"
        
        return Panel(
            f"{mode}\n{help_text}",
            border_style="blue"
        )
    
    async def update_ui(self):
        """Update the UI"""
        self.layout["header"].update(self.create_header())
        self.layout["audio_viz"].update(self.create_audio_viz())
        self.layout["messages"].update(self.create_messages())
        self.layout["input"].update(self.create_input())
    
    async def connect(self):
        """Connect to OpenAI Realtime API"""
        console.print("[yellow]Connecting to OpenAI Realtime API...[/yellow]")
        
        # Get ephemeral token
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        response = requests.post(
            'https://api.openai.com/v1/realtime/sessions',
            headers={'Authorization': f'Bearer {api_key}'},
            json={
                'model': 'gpt-4o-realtime-preview-2025-06-03',
                'voice': 'alloy'
            }
        )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create session: {response.text}")
        
        data = response.json()
        
        # Setup WebRTC
        self.pc = RTCPeerConnection(
            configuration=RTCConfiguration(
                iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
            )
        )
        
        # Add audio track
        self.audio_track = AudioLevelTrack()
        self.pc.addTrack(self.audio_track)
        
        # Handle incoming audio
        @self.pc.on("track")
        async def on_track(track):
            if track.kind == "audio":
                console.print("[green]Receiving audio track[/green]")
                asyncio.create_task(self.handle_audio_output(track))
        
        # Create data channel
        self.data_channel = self.pc.createDataChannel("oai-events")
        
        @self.data_channel.on("open")
        async def on_open():
            self.connected = True
            console.print("[green]Data channel opened![/green]")
            
            # Initialize session
            await self.data_channel.send(json.dumps({
                "type": "session.update",
                "session": {
                    "turn_detection": {"type": "server_vad"},
                    "instructions": "You are a helpful AI assistant. Please respond naturally and conversationally."
                }
            }))
        
        @self.data_channel.on("message")
        async def on_message(message):
            await self.handle_message(json.loads(message))
        
        # Create offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        
        # Get answer
        answer_response = requests.post(
            'https://api.openai.com/v1/realtime',
            data=offer.sdp,
            headers={
                'Authorization': f'Bearer {data["client_secret"]["value"]}',
                'Content-Type': 'application/sdp'
            }
        )
        
        if answer_response.status_code not in [200, 201]:
            raise Exception(f"Failed to get answer: {answer_response.text}")
        
        answer_sdp = answer_response.content.decode()
        answer = RTCSessionDescription(sdp=answer_sdp, type="answer")
        await self.pc.setRemoteDescription(answer)
        
        console.print("[green]WebRTC connection established![/green]")
    
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
        
        async for frame in track:
            # Play audio
            audio_data = frame.to_ndarray().flatten()
            audio_bytes = audio_data.astype(np.int16).tobytes()
            
            # Calculate output level
            if len(audio_data) > 0:
                self.output_level = np.abs(audio_data).mean()
                self.ai_speaking = self.output_level > 0.01
            
            # Play audio
            self.output_stream.write(audio_bytes)
    
    async def handle_message(self, message):
        """Handle incoming messages"""
        msg_type = message.get('type', '')
        
        if msg_type == 'response.audio_transcript.delta':
            # AI is speaking
            self.ai_speaking = True
            transcript = message.get('delta', '')
            if not hasattr(self, 'recent_messages'):
                self.recent_messages = []
            if self.recent_messages and self.recent_messages[-1].startswith("🤖"):
                self.recent_messages[-1] += transcript
            else:
                self.recent_messages.append(f"🤖 {transcript}")
        
        elif msg_type == 'input_audio_buffer.speech_started':
            self.speaking = True
            
        elif msg_type == 'input_audio_buffer.speech_stopped':
            self.speaking = False
            
        elif msg_type == 'conversation.item.input_audio_transcription.completed':
            transcript = message.get('transcript', '')
            if not hasattr(self, 'recent_messages'):
                self.recent_messages = []
            self.recent_messages.append(f"👤 {transcript}")
        
        elif msg_type == 'response.done':
            self.ai_speaking = False
    
    async def monitor_audio_levels(self):
        """Monitor and update audio levels"""
        while True:
            if self.audio_track:
                self.input_level = self.audio_track.current_level
                
            # Update level history
            current_level = max(self.input_level, self.output_level)
            self.level_history.append(current_level)
            
            await asyncio.sleep(0.1)
    
    async def run_ui(self):
        """Run the UI update loop"""
        with Live(self.layout, console=console, refresh_per_second=10) as live:
            while True:
                await self.update_ui()
                await asyncio.sleep(0.1)
    
    async def run(self):
        """Run the client"""
        try:
            # Connect to API
            await self.connect()
            
            # Start monitoring tasks
            monitor_task = asyncio.create_task(self.monitor_audio_levels())
            ui_task = asyncio.create_task(self.run_ui())
            
            # Keep running
            await asyncio.gather(monitor_task, ui_task)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
        finally:
            # Cleanup
            if self.audio_track:
                self.audio_track.stop()
            if self.output_stream:
                self.output_stream.stop_stream()
                self.output_stream.close()
            if hasattr(self, 'p_out'):
                self.p_out.terminate()
            if self.pc:
                await self.pc.close()

async def main():
    """Main entry point"""
    console.print(Panel.fit(
        "[bold cyan]🎙️ OpenAI Realtime WebRTC CLI[/bold cyan]\n"
        "[dim]Real-time audio streaming with visualization[/dim]",
        border_style="cyan"
    ))
    
    client = RealtimeWebRTCClient()
    await client.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")