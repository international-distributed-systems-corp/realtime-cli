import sqlite3
import json
import datetime
import base64
from typing import Optional, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager

DB_PATH = "realtime.db"

@dataclass
class Conversation:
    id: str
    created_at: str
    config: Dict[str, Any]

@contextmanager
def get_db():
    """Database connection context manager"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Create database tables if they don't exist"""
    with get_db() as conn:
        c = conn.cursor()
        
        # Conversations table
        c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            config TEXT
        )
        """)
        
        # Events table - stores all WebSocket messages
        c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            direction TEXT,  -- 'client->server' or 'server->client'
            event_type TEXT,
            event_data TEXT, -- Full JSON event
            created_at TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
        """)
        
        # Audio data table
        c.execute("""
        CREATE TABLE IF NOT EXISTS audio_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            event_id INTEGER,
            audio_type TEXT,  -- 'input' or 'output'
            audio_data BLOB,  -- Raw audio bytes
            created_at TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id),
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
        """)
        
        # Function calls table
        c.execute("""
        CREATE TABLE IF NOT EXISTS function_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            event_id INTEGER,
            function_name TEXT,
            arguments TEXT,  -- JSON string
            result TEXT,     -- JSON string
            created_at TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id),
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
        """)
        
        conn.commit()

def create_conversation(conv_id: str, config: Dict[str, Any]) -> None:
    """Create a new conversation record"""
    with get_db() as conn:
        now = datetime.datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO conversations (id, created_at, config) VALUES (?, ?, ?)",
            (conv_id, now, json.dumps(config))
        )
        conn.commit()

def record_event(conversation_id: str, direction: str, event_data: str) -> int:
    """
    Record a WebSocket event, returns the event ID.
    Validates event structure and handles special event types.
    """
    with get_db() as conn:
        now = datetime.datetime.utcnow().isoformat()
        
        try:
            event = json.loads(event_data)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in event_data")
            
        # Validate required event fields
        if 'type' not in event:
            raise ValueError("Event missing required 'type' field")
            
        event_type = event.get('type', 'unknown')
        
        # Record the main event
        c = conn.execute(
            """INSERT INTO events 
               (conversation_id, direction, event_type, event_data, created_at)
               VALUES (?, ?, ?, ?, ?)
            """,
            (conversation_id, direction, event_type, event_data, now)
        )
        event_id = c.lastrowid
        
        # Handle special event types
        if event_type in ('input_audio_buffer.append', 'response.audio.delta'):
            audio_type = 'input' if direction == 'client->server' else 'output'
            audio_data = event.get('audio') or event.get('delta')
            
            if audio_data:
                try:
                    # Validate base64 data
                    audio_bytes = base64.b64decode(audio_data)
                    conn.execute(
                        """INSERT INTO audio_data
                           (conversation_id, event_id, audio_type, audio_data, created_at)
                           VALUES (?, ?, ?, ?, ?)
                        """,
                        (conversation_id, event_id, audio_type, audio_bytes, now)
                    )
                except Exception as e:
                    print(f"Warning: Failed to decode audio data: {e}")
        
        # Handle function calls with validation
        if event_type == 'response.function_call_arguments.done':
            function_name = event.get('name')
            arguments = event.get('arguments')
            
            if not function_name:
                print("Warning: Function call event missing 'name'")
                function_name = 'unknown'
                
            if not isinstance(arguments, (str, dict)):
                print("Warning: Invalid function arguments format")
                arguments = '{}'
            elif isinstance(arguments, dict):
                arguments = json.dumps(arguments)
                
            conn.execute(
                """INSERT INTO function_calls
                   (conversation_id, event_id, function_name, arguments, created_at)
                   VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, event_id, function_name, arguments, now)
            )
        
        conn.commit()
        return event_id

def get_conversation(conv_id: str) -> Optional[Conversation]:
    """Retrieve a conversation by ID"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conv_id,)
        ).fetchone()
        
        if row:
            return Conversation(
                id=row['id'],
                created_at=row['created_at'],
                config=json.loads(row['config'])
            )
        return None

def get_conversation_events(conv_id: str, direction: str = None):
    """
    Get all events for a conversation in chronological order.
    Optionally filter by direction ('client->server' or 'server->client')
    """
    with get_db() as conn:
        query = """SELECT * FROM events 
                  WHERE conversation_id = ?
                  {}
                  ORDER BY created_at ASC"""
                  
        if direction:
            query = query.format("AND direction = ?")
            return conn.execute(query, (conv_id, direction)).fetchall()
        else:
            query = query.format("")
            return conn.execute(query, (conv_id,)).fetchall()

def get_conversation_audio(conv_id: str, audio_type: str):
    """Get all audio data for a conversation"""
    with get_db() as conn:
        return conn.execute(
            """SELECT * FROM audio_data
               WHERE conversation_id = ? AND audio_type = ?
               ORDER BY created_at ASC""",
            (conv_id, audio_type)
        ).fetchall()

def get_conversation_function_calls(conv_id: str):
    """Get all function calls for a conversation"""
    with get_db() as conn:
        return conn.execute(
            """SELECT * FROM function_calls
               WHERE conversation_id = ?
               ORDER BY created_at ASC""",
            (conv_id,)
        ).fetchall()
