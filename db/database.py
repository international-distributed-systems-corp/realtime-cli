import sqlite3
import os
import hashlib
import secrets
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, Dict, Any, List

DATABASE_PATH = "db/realtime.db"

def init_db():
    """Initialize the database with schema"""
    if not os.path.exists("db"):
        os.makedirs("db")
        
    with open("db/schema.sql") as f:
        schema = f.read()
        
    with get_db() as db:
        db.executescript(schema)
        
        # Insert default subscription tiers
        db.executemany(
            """INSERT OR IGNORE INTO subscription_tiers 
               (name, token_limit, audio_limit, base_price, token_overage_price, audio_overage_price)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                ("free", 100000, 3600, 0.0, 0.002, 0.006),
                ("basic", 500000, 18000, 50.0, 0.0015, 0.004), 
                ("pro", 2000000, 72000, 200.0, 0.001, 0.003)
            ]
        )

@contextmanager
def get_db():
    """Context manager for database connections"""
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()

def create_user(email: str, password: str) -> int:
    """Create a new user account"""
    hashed = hashlib.sha256(password.encode()).hexdigest()
    api_key = secrets.token_urlsafe(32)
    
    with get_db() as db:
        cursor = db.execute(
            """INSERT INTO users (email, hashed_password, api_key)
               VALUES (?, ?, ?)""",
            (email, hashed, api_key)
        )
        return cursor.lastrowid

def get_user_by_api_key(api_key: str) -> Optional[Dict]:
    """Look up a user by API key"""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM users WHERE api_key = ?",
            (api_key,)
        ).fetchone()
        return dict(row) if row else None

def record_usage(user_id: int, tokens: int, audio_seconds: float, 
                request_type: str) -> None:
    """Record API usage for a user"""
    with get_db() as db:
        # Get user's subscription tier
        tier = db.execute(
            """SELECT st.* FROM subscription_tiers st
               JOIN users u ON u.subscription_tier = st.name
               WHERE u.id = ?""",
            (user_id,)
        ).fetchone()
        
        # Calculate cost based on usage and limits
        base_cost = 0.0
        if tokens > tier['token_limit']:
            overage_tokens = tokens - tier['token_limit']
            base_cost += overage_tokens * tier['token_overage_price']
            
        if audio_seconds > tier['audio_limit']:
            overage_audio = audio_seconds - tier['audio_limit']
            base_cost += overage_audio * tier['audio_overage_price']
        
        db.execute(
            """INSERT INTO usage_records 
               (user_id, tokens_used, audio_seconds, request_type, cost)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, tokens, audio_seconds, request_type, base_cost)
        )
