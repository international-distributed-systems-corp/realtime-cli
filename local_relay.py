import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def echo(websocket):
    try:
        async for message in websocket:
            # Echo back a mock session.created event first
            if '"type": "init_session"' in message:
                response = {
                    "type": "session.created",
                    "session": {"id": "test_session"}
                }
                await websocket.send(json.dumps(response))
            logger.info(f"Received message: {message}")
    except websockets.exceptions.ConnectionClosed:
        logger.info("Client disconnected")

async def main():
    async with websockets.serve(echo, "localhost", 8765):
        logger.info("Relay server running on ws://localhost:8765")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
