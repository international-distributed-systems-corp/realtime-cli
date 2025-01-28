import sqlite3
import json
import datetime
from typing import Optional, Dict, Any
from contextlib import contextmanager

DB_PATH = "realtime.db"

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

def get_user_by_api_key(api_key: str) -> Optional[Dict]:
    """Get user by API key"""
    with get_db() as conn:
        result = conn.execute(
            "SELECT * FROM users WHERE api_key = ?",
            (api_key,)
        ).fetchone()
        if result:
            return dict(result)
    return None

def record_usage(user_id: str, tokens: int, audio_seconds: float, request_type: str):
    """Record API usage"""
    with get_db() as conn:
        now = datetime.datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO usage_records 
               (user_id, tokens, audio_seconds, request_type, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, tokens, audio_seconds, request_type, now)
        )
        conn.commit()
