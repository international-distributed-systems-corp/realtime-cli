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
        "fastapi",
        "uvicorn", 
        "pydantic",
        "neo4j",
        "python-dotenv"
    ])
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
@asgi_app()
def app():
    return app
