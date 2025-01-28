import os
import sqlite3
import logging
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        logger.info(f"Initialized audio storage at {self.db_path}")
            
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
            sample_id = cursor.lastrowid
            logger.debug(f"Saved {speaker} audio sample {sample_id}")
            return sample_id
            
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
    def update_transcription(self, sample_id: int, transcription: str) -> None:
        """Update the transcription for a sample"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE audio_samples SET transcription = ? WHERE id = ?",
                (transcription, sample_id)
            )
            logger.debug(f"Updated transcription for sample {sample_id}")
            
    def prune_old_samples(self, days: int = 30) -> int:
        """Remove samples older than specified days"""
        cutoff = datetime.now() - timedelta(days=days)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM audio_samples WHERE timestamp < ?",
                (cutoff,)
            )
            count = cursor.rowcount
            logger.info(f"Pruned {count} samples older than {days} days")
            return count
            
    def export_samples(self, output_dir: str) -> None:
        """Export all samples to a directory"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM audio_samples")
            for row in cursor:
                sample = AudioSample(*row)
                sample_dir = output_path / sample.speaker
                sample_dir.mkdir(exist_ok=True)
                
                # Save audio data
                audio_path = sample_dir / f"{sample.id}.raw"
                audio_path.write_bytes(sample.audio_data)
                
                # Save metadata
                meta = asdict(sample)
                meta['audio_data'] = str(audio_path)  # Replace bytes with path
                meta_path = sample_dir / f"{sample.id}.json"
                meta_path.write_text(json.dumps(meta, default=str))
                
        logger.info(f"Exported samples to {output_dir}")
        
    def import_samples(self, input_dir: str) -> int:
        """Import samples from a directory"""
        input_path = Path(input_dir)
        count = 0
        
        for speaker_dir in input_path.iterdir():
            if speaker_dir.is_dir():
                for meta_file in speaker_dir.glob("*.json"):
                    meta = json.loads(meta_file.read_text())
                    audio_path = Path(meta['audio_data'])
                    audio_data = audio_path.read_bytes()
                    
                    self.save_sample(
                        speaker=meta['speaker'],
                        audio_data=audio_data,
                        sample_rate=meta['sample_rate'],
                        transcription=meta.get('transcription')
                    )
                    count += 1
                    
        logger.info(f"Imported {count} samples from {input_dir}")
        return count
