#!/usr/bin/env python3
"""
WebRTC CLI client for OpenAI Realtime API
Uses browser-based WebRTC for optimal audio quality and low latency
"""
import asyncio
import json
import logging
import webbrowser
import requests
from getpass import getpass
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import os
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment URLs
PROD_URL = "https://arthurcolle--realtime-relay.modal.run"
DEV_URL = "https://arthurcolle--realtime-relay-dev.modal.run"

class WebRTCCLI:
    """WebRTC CLI client that launches browser-based interface"""
    
    def __init__(self, env='prod'):
        self.env = env
        self.base_url = PROD_URL if env == 'prod' else DEV_URL
        self.token = None
        self.server = None
        self.server_thread = None
        
    async def login(self) -> str:
        """Login and get access token"""
        email = input("Email: ")
        password = getpass("Password: ")
        
        response = requests.post(
            f"{self.base_url}/token",
            data={"username": email, "password": password}
        )
        
        if response.status_code != 200:
            raise Exception(f"Login failed: {response.text}")
            
        self.token = response.json()["access_token"]
        return self.token
    
    def create_webrtc_client_html(self) -> str:
        """Create optimized WebRTC client HTML for CLI usage"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Realtime CLI - WebRTC Client</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .container {{
            max-width: 800px;
            width: 100%;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(20px);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}
        .status {{
            padding: 15px;
            border-radius: 10px;
            margin: 10px 0;
            font-weight: 500;
        }}
        .status.connected {{ background: rgba(16, 185, 129, 0.3); }}
        .status.connecting {{ background: rgba(245, 158, 11, 0.3); }}
        .status.disconnected {{ background: rgba(239, 68, 68, 0.3); }}
        .controls {{
            display: flex;
            gap: 15px;
            margin: 20px 0;
            flex-wrap: wrap;
        }}
        button {{
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
        }}
        button:hover {{ transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3); }}
        button:disabled {{ opacity: 0.5; cursor: not-allowed; transform: none; }}
        button.primary {{ background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }}
        button.danger {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
        .messages {{
            height: 400px;
            overflow-y: auto;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 10px;
            padding: 15px;
            margin: 20px 0;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 14px;
            line-height: 1.5;
        }}
        .message {{
            margin: 8px 0;
            padding: 8px 12px;
            border-radius: 6px;
            background: rgba(255, 255, 255, 0.1);
        }}
        .message.user {{ background: rgba(79, 172, 254, 0.3); }}
        .message.assistant {{ background: rgba(16, 185, 129, 0.3); }}
        .message.system {{ background: rgba(156, 163, 175, 0.3); }}
        .input-group {{
            display: flex;
            gap: 10px;
            margin: 20px 0;
        }}
        input[type="text"] {{
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.1);
            color: white;
            font-size: 16px;
            backdrop-filter: blur(10px);
        }}
        input[type="text"]::placeholder {{ color: rgba(255, 255, 255, 0.6); }}
        .visualizer {{
            display: flex;
            justify-content: center;
            align-items: end;
            height: 60px;
            gap: 3px;
            margin: 20px 0;
        }}
        .bar {{
            width: 4px;
            background: linear-gradient(to top, #4facfe, #00f2fe);
            border-radius: 2px;
            min-height: 4px;
            transition: height 0.15s ease;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎙️ Realtime CLI - WebRTC Client</h1>
        <p>Optimized for low-latency voice conversations with AI</p>
        
        <div id="status" class="status disconnected">
            Status: Disconnected
        </div>
        
        <div class="controls">
            <button id="connect-btn" class="primary">Connect Voice</button>
            <button id="disconnect-btn" class="danger" disabled>Disconnect</button>
            <button id="mute-btn" disabled>Toggle Mute</button>
        </div>
        
        <div class="visualizer" id="visualizer">
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        </div>
        
        <div id="messages" class="messages">
            <div class="message system">WebRTC CLI Client Ready - Click "Connect Voice" to start</div>
        </div>
        
        <div class="input-group">
            <input type="text" id="text-input" placeholder="Type a message or use voice...">
            <button id="send-btn">Send</button>
        </div>
    </div>
    
    <audio id="remote-audio" autoplay></audio>
    
    <script>
        const TOKEN = '{self.token}';
        const BASE_URL = '{self.base_url}';
        
        let pc = null;
        let dataChannel = null;
        let localStream = null;
        let isMuted = false;
        let isConnected = false;
        let currentAssistantMessage = null;
        
        // DOM elements
        const statusEl = document.getElementById('status');
        const connectBtn = document.getElementById('connect-btn');
        const disconnectBtn = document.getElementById('disconnect-btn');
        const muteBtn = document.getElementById('mute-btn');
        const messagesEl = document.getElementById('messages');
        const textInput = document.getElementById('text-input');
        const sendBtn = document.getElementById('send-btn');
        const visualizerBars = document.querySelectorAll('.bar');
        
        // Audio visualizer
        function startVisualization() {{
            const animate = () => {{
                visualizerBars.forEach(bar => {{
                    const height = Math.random() * 50 + 10;
                    bar.style.height = height + 'px';
                }});
            }};
            setInterval(animate, 150);
        }}
        
        function stopVisualization() {{
            visualizerBars.forEach(bar => {{
                bar.style.height = '4px';
            }});
        }}
        
        // Status management
        function updateStatus(message, className) {{
            statusEl.textContent = `Status: ${{message}}`;
            statusEl.className = `status ${{className}}`;
        }}
        
        // Message management
        function addMessage(type, content) {{
            const messageEl = document.createElement('div');
            messageEl.className = `message ${{type}}`;
            messageEl.textContent = `[${{new Date().toLocaleTimeString()}}] ${{content}}`;
            messagesEl.appendChild(messageEl);
            messagesEl.scrollTop = messagesEl.scrollHeight;
            return messageEl;
        }}
        
        function appendToMessage(messageEl, text) {{
            messageEl.textContent += text;
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }}
        
        // WebRTC connection
        async function connectWebRTC() {{
            try {{
                updateStatus('Connecting...', 'connecting');
                
                // Get ephemeral token
                const tokenResponse = await fetch(`${{BASE_URL}}/session`, {{
                    headers: {{ 'Authorization': `Bearer ${{TOKEN}}` }}
                }});
                const data = await tokenResponse.json();
                const ephemeralToken = data.client_secret.value;
                
                // Create peer connection
                pc = new RTCPeerConnection();
                
                // Set up remote audio
                const audioEl = document.getElementById('remote-audio');
                pc.ontrack = e => {{
                    audioEl.srcObject = e.streams[0];
                    updateStatus('Speaking', 'connected');
                    startVisualization();
                }};
                
                // Add local audio track
                localStream = await navigator.mediaDevices.getUserMedia({{
                    audio: {{
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                        sampleRate: 24000,
                        channelCount: 1
                    }}
                }});
                pc.addTrack(localStream.getTracks()[0]);
                
                // Set up data channel
                dataChannel = pc.createDataChannel("oai-events");
                dataChannel.addEventListener("open", () => {{
                    updateStatus('Connected', 'connected');
                    isConnected = true;
                    connectBtn.disabled = true;
                    disconnectBtn.disabled = false;
                    muteBtn.disabled = false;
                    addMessage('system', 'Voice connection established - Start speaking!');
                }});
                
                dataChannel.addEventListener("message", (e) => {{
                    try {{
                        const event = JSON.parse(e.data);
                        handleRealtimeEvent(event);
                    }} catch (err) {{
                        console.error('Error parsing data channel message:', err);
                    }}
                }});
                
                // Create offer and get answer
                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);
                
                const sdpResponse = await fetch(`${{BASE_URL}}/webrtc/offer`, {{
                    method: "POST",
                    body: offer.sdp,
                    headers: {{
                        'Authorization': `Bearer ${{TOKEN}}`,
                        "Content-Type": "application/sdp"
                    }},
                }});
                
                if (!sdpResponse.ok) {{
                    throw new Error(`HTTP ${{sdpResponse.status}}: ${{sdpResponse.statusText}}`);
                }}
                
                const answerSdp = await sdpResponse.text();
                const answer = {{
                    type: "answer",
                    sdp: answerSdp,
                }};
                await pc.setRemoteDescription(answer);
                
            }} catch (error) {{
                console.error('WebRTC connection failed:', error);
                updateStatus('Connection Failed', 'disconnected');
                addMessage('system', `Connection failed: ${{error.message}}`);
            }}
        }}
        
        function disconnectWebRTC() {{
            if (pc) pc.close();
            if (localStream) localStream.getTracks().forEach(track => track.stop());
            if (dataChannel) dataChannel.close();
            
            pc = null;
            localStream = null;
            dataChannel = null;
            isConnected = false;
            
            updateStatus('Disconnected', 'disconnected');
            stopVisualization();
            connectBtn.disabled = false;
            disconnectBtn.disabled = true;
            muteBtn.disabled = true;
            addMessage('system', 'Voice connection closed');
        }}
        
        function toggleMute() {{
            if (localStream) {{
                const audioTrack = localStream.getAudioTracks()[0];
                if (audioTrack) {{
                    audioTrack.enabled = !audioTrack.enabled;
                    isMuted = !audioTrack.enabled;
                    muteBtn.textContent = isMuted ? 'Unmute' : 'Toggle Mute';
                    muteBtn.style.background = isMuted ? 'var(--gradient-secondary)' : '';
                    addMessage('system', isMuted ? 'Microphone muted' : 'Microphone unmuted');
                }}
            }}
        }}
        
        function sendTextMessage(message) {{
            if (dataChannel && dataChannel.readyState === 'open') {{
                const event = {{
                    type: 'conversation.item.create',
                    item: {{
                        type: 'message',
                        role: 'user',
                        content: [{{ type: 'input_text', text: message }}]
                    }}
                }};
                dataChannel.send(JSON.stringify(event));
                addMessage('user', message);
                
                // Trigger response
                dataChannel.send(JSON.stringify({{ type: 'response.create' }}));
            }} else {{
                addMessage('system', 'Please connect voice first');
            }}
        }}
        
        function handleRealtimeEvent(event) {{
            console.log('Received realtime event:', event);
            
            switch(event.type) {{
                case 'response.text.delta':
                    if (!currentAssistantMessage) {{
                        currentAssistantMessage = addMessage('assistant', '');
                    }}
                    appendToMessage(currentAssistantMessage, event.delta);
                    break;
                case 'response.audio.delta':
                    updateStatus('AI Speaking', 'connected');
                    startVisualization();
                    break;
                case 'response.done':
                    currentAssistantMessage = null;
                    updateStatus('Listening', 'connected');
                    stopVisualization();
                    break;
                case 'input_audio_buffer.speech_started':
                    updateStatus('You Speaking', 'connected');
                    addMessage('system', 'Speech detected...');
                    break;
                case 'input_audio_buffer.speech_stopped':
                    updateStatus('Processing', 'connected');
                    break;
                case 'conversation.item.input_audio_transcription.completed':
                    addMessage('user', `[Transcribed] ${{event.transcript}}`);
                    break;
                default:
                    console.log('Unhandled event type:', event.type);
            }}
        }}
        
        // Event listeners
        connectBtn.addEventListener('click', connectWebRTC);
        disconnectBtn.addEventListener('click', disconnectWebRTC);
        muteBtn.addEventListener('click', toggleMute);
        
        sendBtn.addEventListener('click', () => {{
            const message = textInput.value.trim();
            if (message) {{
                sendTextMessage(message);
                textInput.value = '';
            }}
        }});
        
        textInput.addEventListener('keypress', (e) => {{
            if (e.key === 'Enter') {{
                sendBtn.click();
            }}
        }});
        
        // Cleanup on page unload
        window.addEventListener('beforeunload', disconnectWebRTC);
        
        // Auto-focus text input
        textInput.focus();
        
        console.log('WebRTC CLI Client Ready');
    </script>
</body>
</html>"""

    def start_local_server(self, port=8080):
        """Start local HTTP server to serve WebRTC client"""
        class CustomHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                self.html_content = None
                super().__init__(*args, **kwargs)
            
            def do_GET(self):
                if self.path == '/' or self.path == '/index.html':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(self.server.webrtc_cli.create_webrtc_client_html().encode())
                else:
                    super().do_GET()
        
        self.server = HTTPServer(('localhost', port), CustomHandler)
        self.server.webrtc_cli = self
        
        def run_server():
            logger.info(f"Starting local server on http://localhost:{port}")
            self.server.serve_forever()
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        return f"http://localhost:{port}"
    
    def stop_server(self):
        """Stop the local server"""
        if self.server:
            self.server.shutdown()
            self.server = None
        if self.server_thread:
            self.server_thread.join(timeout=1)
            self.server_thread = None
    
    async def run(self):
        """Run the WebRTC CLI client"""
        try:
            # Login
            print("🔐 Authenticating with Realtime API...")
            await self.login()
            print("✅ Authentication successful!")
            
            # Start local server
            print("🚀 Starting WebRTC client...")
            client_url = self.start_local_server()
            
            # Open browser
            print(f"🌐 Opening WebRTC client at {client_url}")
            webbrowser.open(client_url)
            
            print("\n" + "="*60)
            print("🎙️  WebRTC CLI Client Started!")
            print("="*60)
            print(f"• Environment: {self.env}")
            print(f"• Server: {self.base_url}")
            print(f"• Client URL: {client_url}")
            print("\n📋 Instructions:")
            print("1. Click 'Connect Voice' in the browser")
            print("2. Allow microphone access when prompted")
            print("3. Start speaking - AI will respond with voice")
            print("4. Use text input for typed messages")
            print("5. Press Ctrl+C to exit")
            print("="*60)
            
            # Keep running until interrupted
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n🔌 Shutting down...")
                
        except Exception as e:
            logger.error(f"Failed to start WebRTC CLI: {e}")
        finally:
            self.stop_server()

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
    print("✅ Registration successful! Please login.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='WebRTC CLI for OpenAI Realtime API')
    parser.add_argument('--env', choices=['prod', 'dev'], default='prod',
                      help='Environment to connect to')
    parser.add_argument('--register', action='store_true',
                      help='Register a new user')
    parser.add_argument('--port', type=int, default=8080,
                      help='Local server port (default: 8080)')
    
    args = parser.parse_args()
    
    try:
        if args.register:
            base_url = PROD_URL if args.env == 'prod' else DEV_URL
            asyncio.run(register(base_url))
        else:
            cli = WebRTCCLI(args.env)
            asyncio.run(cli.run())
    except KeyboardInterrupt:
        print("\n👋 Session ended.")
    except Exception as e:
        logger.error(f"CLI error: {e}")