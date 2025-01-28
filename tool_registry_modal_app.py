from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from modal import Image, Secret, App, asgi_app

# Configuration
TOOL_MGMT_APP_LABEL = "tool_management_api"
NEO4J_SECRET_NAME = "distributed-systems"

# Modal configuration
image = (
    Image.debian_slim()
    .pip_install([
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0", 
        "pydantic>=1.8.0",
        "neo4j>=5.0.0",
        "python-dotenv>=0.19.0"
    ])
    .env({
        "NEO4J_URI": "neo4j://bolt.n4j.distributed.systems",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "Backstab2025!"
    })
)

# Create Modal app
app = App(TOOL_MGMT_APP_LABEL)

# Import web_app from tool_registry.py
from tool_registry import web_app

# Wrap the FastAPI app with Modal
@app.function(
    image=image,
    secrets=[Secret.from_name(NEO4J_SECRET_NAME)],
)
@asgi_app(label="tools")
def fastapi_app():
    return web_app
