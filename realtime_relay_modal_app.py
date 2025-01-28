import modal
import json
import asyncio
import websockets
from typing import Optional, Dict, Any

# Create Modal app and image
stub = modal.Stub("realtime-relay")
image = modal.Image.debian_slim().pip_install("websockets", "requests")

@stub.function(image=image)
@modal.web_server(9000)
def run_relay_server():
    """Run the WebSocket relay server using Modal"""
    import relay_server
    
    # Start the relay server
    asyncio.run(relay_server.main())

if __name__ == "__main__":
    stub.serve()
