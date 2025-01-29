import asyncio
import json
import os
from dotenv import load_dotenv
import logging
import uuid
import os
import sqlite3
import websockets
import requests
from datetime import datetime, timedelta
from typing import List, Optional, Union, Dict, Any, Annotated
from contextlib import contextmanager
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str
from modal import Image, App, asgi_app
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = os.getenv("APP_SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Database configuration
DATABASE_URL = "realtime.db"

@contextmanager
def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()

# Create FastAPI app with WebSocket support
web_app = FastAPI(
    title="Realtime Relay",
    description="WebSocket relay for realtime communication", 
    version="1.0.0",
    root_path="",
    root_path_in_servers=False
)

# Set up templates and static files
import os
from pathlib import Path

# Get current directory
current_dir = Path(__file__).parent

# Set up templates and static directories
templates_dir = current_dir / "templates"
static_dir = current_dir / "static"

# Configure templates with absolute path
templates = Jinja2Templates(directory=str(templates_dir))

# Mount static files with absolute path and name
web_app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@web_app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main chat interface"""
    return templates.TemplateResponse(
        "chat.html",
        {"request": request}
    )

# User models and database
class UserInDB(BaseModel):
    email: str
    hashed_password: str
    is_superuser: bool = False

class UserCreate(BaseModel):
    email: str
    password: str

def get_user(email: str) -> Optional[UserInDB]:
    """Get user from database by email"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        if user:
            return UserInDB(**user)
    return None

def create_user(user: UserCreate) -> UserInDB:
    """Create new user in database"""
    hashed_password = pwd_context.hash(user.password)
    is_superuser = user.email.endswith("@brainchain.ai")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (email, hashed_password, is_superuser) VALUES (?, ?, ?)",
            (user.email, hashed_password, is_superuser)
        )
        conn.commit()
        
    return UserInDB(
        email=user.email,
        hashed_password=hashed_password,
        is_superuser=is_superuser
    )

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

def authenticate_user(email: str, password: str) -> Optional[UserInDB]:
    """Authenticate user by email and password"""
    user = get_user(email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserInDB:
    """Get current user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = get_user(email)
    if user is None:
        raise credentials_exception
    return user

async def get_current_superuser(
    current_user: Annotated[UserInDB, Depends(get_current_user)]
) -> UserInDB:
    """Check if current user is superuser"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough privileges"
        )
    return current_user

from pathlib import Path

# Get current directory for mounting
CURRENT_DIR = Path(__file__).parent
import dotenv

# Create Modal app and image
# Load environment variables
load_dotenv()

app = App("realtime-relay")
image = (
    Image.debian_slim()
    .pip_install(["fastapi", "uvicorn", "python-dotenv", "websockets>=12.0", "requests", "python-multipart", "python-jose[cryptography]", "passlib", "jinja2"])
    # Mount the templates directory
    .add_local_dir(
        "templates",
        remote_path="/root/templates"
    )
    # Mount the static directory  
    .add_local_dir(
        "static", 
        remote_path="/root/static"
    )
)

class RealtimeRelay:
    """
    Manages a single upstream connection to the OpenAI Realtime API.
    """
    def __init__(self, ephemeral_token: str, session_config: dict):
        self.ephemeral_token = ephemeral_token
        self.session_config = session_config
        self.upstream_ws = None

    async def connect_upstream(self):
        """Connect to the Realtime API over WebSocket using ephemeral token."""
        base_url = "wss://api.openai.com/v1/realtime"
        model = self.session_config.get("model", None)
        if model:
            base_url += f"?model={model}"

        headers = {
            "Authorization": f"Bearer {self.ephemeral_token}",
            "OpenAI-Beta": "realtime=v1"
        }

        logger.info(f"Connecting upstream to {base_url} ...")
        self.upstream_ws = await websockets.connect(base_url, additional_headers=headers)
        logger.info("Upstream connected.")

    async def close(self):
        if self.upstream_ws:
            await self.upstream_ws.close()

from modal import Secret, Mount

@app.function(
    secrets=[Secret.from_name("distributed-systems")]
)
def create_ephemeral_token(session_config: dict) -> str:
    """Create ephemeral token for Realtime API access."""
    payload = {
        k: session_config[k]
        for k in [
            "model", "modalities", "instructions", "voice",
            "input_audio_format", "output_audio_format",
            "input_audio_transcription", "turn_detection",
            "tools", "tool_choice", "temperature",
            "max_response_output_tokens"
        ]
        if k in session_config
    }
    openai_api_key = os.getenv('OPENAI_API_KEY')
    print(openai_api_key)
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    url = "https://api.openai.com/v1/realtime/sessions"
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "realtime=v1"
    }

    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed ephemeral token: {resp.text}")
    data = resp.json()
    return data["client_secret"]["value"]

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

manager = ConnectionManager()

async def handle_client(websocket: WebSocket, relay: Optional[RealtimeRelay] = None):
    """Handle bi-directional relay between client and OpenAI."""
    try:
        async def relay_local_to_upstream():
            while True:
                data_str = await websocket.receive_text()
                data = json.loads(data_str)
                if "event_id" not in data:
                    data["event_id"] = f"evt_{uuid.uuid4().hex[:6]}"
                await relay.upstream_ws.send(json.dumps(data))

        async def relay_upstream_to_local():
            try:
                async for data_str in relay.upstream_ws:
                    data = json.loads(data_str)
                    # Handle binary audio data if present
                    if data.get("type") == "audio" and "data" in data:
                        audio_data = data["data"]
                        # Send binary audio data as a binary websocket message
                        await websocket.send_bytes(audio_data.encode('utf-8'))
                    else:
                        # Send other messages as text
                        await websocket.send_text(data_str)
            except websockets.ConnectionClosed:
                pass

        done, pending = await asyncio.wait(
            [asyncio.create_task(relay_local_to_upstream()),
             asyncio.create_task(relay_upstream_to_local())],
            return_when=asyncio.FIRST_EXCEPTION
        )
        for task in pending:
            task.cancel()

    except Exception as e:
        logger.error(f"Relay error: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": {"message": str(e)}
            }))
        except:
            pass

@web_app.post("/register", response_model=dict)
async def register(user: UserCreate):
    """Register new user"""
    db_user = get_user(user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    user = create_user(user)
    return {"message": "User registered successfully"}

@web_app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login user and return access token"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@web_app.get("/users/me", response_model=dict)
async def read_users_me(current_user: Annotated[UserInDB, Depends(get_current_user)]):
    """Get current user info"""
    return {
        "email": current_user.email,
        "is_superuser": current_user.is_superuser
    }

@web_app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections with proper lifecycle management"""
    relay = None
    try:
        await manager.connect(websocket)
        logger.info("New WebSocket connection accepted")

        # Send connection acknowledgment
        await websocket.send_text(json.dumps({
            "type": "connection.established",
            "timestamp": str(datetime.now())
        }))

        while True:
            try:
                # Wait for messages
                data = await websocket.receive_text()
                msg = json.loads(data)

                if msg.get("type") == "init_session":
                    # Handle initialization
                    session_config = msg.get("session_config", {})
                    try:
                        token = create_ephemeral_token.local(session_config)
                        relay = RealtimeRelay(token, session_config)
                        await relay.connect_upstream()
                        await handle_client(websocket, relay)
                    except Exception as e:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "error": {
                                "code": "relay_init_failed",
                                "message": str(e)
                            }
                        }))
                else:
                    # Handle regular messages
                    await websocket.send_text(json.dumps({
                        "type": "message",
                        "sender": "Server",
                        "text": f"Received: {msg.get('text', '')}"
                    }))
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": {"message": "Invalid JSON message"}
                }))

        # Create relay connection
        session_config = init_msg.get("session_config", {})
        try:
            token = create_ephemeral_token.local(session_config)
            relay = RealtimeRelay(token, session_config)
            await relay.connect_upstream()
            
            # Start bi-directional relay
            await handle_client(websocket, relay)

        except Exception as e:
            logger.error(f"Failed to initialize relay: {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": {
                    "code": "relay_init_failed",
                    "message": str(e)
                }
            }))

    except WebSocketDisconnect:
        logger.info("Client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        if relay:
            await relay.close()
        logger.info("Cleaning up WebSocket connection")

# add endpoint 
# Initialize database tables
def init_db():
    """Initialize database tables"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            is_superuser BOOLEAN NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()

@app.function(
    image=image,
    keep_warm=1,
    allow_concurrent_inputs=True,
    timeout=600,
    container_idle_timeout=300,
    secrets=[Secret.from_name("distributed-systems")]
)
@asgi_app(label="realtime-relay")
def fastapi_app():
    """ASGI app for handling WebSocket connections"""
    return web_app

if __name__ == "__main__":
    app.serve()
