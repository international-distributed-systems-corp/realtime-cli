import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import numpy as np

@dataclass
class AudioSample:
    """Represents a single audio sample with metadata"""
    id: int
    speaker: str  # 'user' or 'agent' 
    audio_data: bytes
    sample_rate: int
    timestamp: datetime
    transcription: str = None
    
class AudioStorage:
    """Handles persistent storage of audio samples for training"""
    
    def __init__(self, db_path: str = "audio_samples.db"):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """Initialize SQLite database and tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audio_samples (
                    id INTEGER PRIMARY KEY,
                    speaker TEXT NOT NULL,
                    audio_data BLOB NOT NULL,
                    sample_rate INTEGER NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    transcription TEXT
                )
            """)
            
    def save_sample(self, speaker: str, audio_data: bytes, 
                   sample_rate: int, transcription: str = None) -> int:
        """Save an audio sample to storage"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO audio_samples 
                   (speaker, audio_data, sample_rate, transcription)
                   VALUES (?, ?, ?, ?)""",
                (speaker, audio_data, sample_rate, transcription)
            )
            return cursor.lastrowid
            
    def get_sample(self, sample_id: int) -> AudioSample:
        """Retrieve a specific audio sample"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM audio_samples WHERE id = ?", 
                (sample_id,)
            )
            row = cursor.fetchone()
            if row:
                return AudioSample(*row)
            return None
            
    def get_samples_by_speaker(self, speaker: str) -> list[AudioSample]:
        """Get all samples for a specific speaker"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM audio_samples WHERE speaker = ?",
                (speaker,)
            )
            return [AudioSample(*row) for row in cursor.fetchall()]
