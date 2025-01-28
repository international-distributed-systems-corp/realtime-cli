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
stub = App(TOOL_MGMT_APP_LABEL)

# Create the FastAPI app
app = FastAPI(title="Tool Management API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import app from tool_registry.py
from tool_registry import app

# Wrap the FastAPI app with Modal
@stub.function(
    image=image,
    secrets=[Secret.from_name(NEO4J_SECRET_NAME)],
)
@asgi_app()
def app():
    return app
