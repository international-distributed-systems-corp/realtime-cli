from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Deque
from collections import deque
import numpy as np
import time

class SpeakerState(Enum):
    IDLE = "idle"
    SPEAKING = "speaking"
    PROCESSING = "processing"
    LISTENING = "listening"

@dataclass
class ConversationMetrics:
    """Tracks conversation flow metrics"""
    last_human_speech_end: float = 0.0
    last_ai_speech_end: float = 0.0
    speech_gaps: Deque[float] = deque(maxlen=10)
    turn_durations: Deque[float] = deque(maxlen=10)
    interruption_count: int = 0

class ConversationManager:
    """Manages conversation turn-taking and flow"""
    def __init__(self):
        self.human_state = SpeakerState.IDLE
        self.ai_state = SpeakerState.IDLE
        self.metrics = ConversationMetrics()
        self.speech_threshold = 0.1
        self.min_speech_duration = 0.2
        self.speech_start_time = 0.0
        self.last_active_time = time.time()
        
    def update_human_audio(self, level: float) -> None:
        """Update human speech state based on audio level"""
        now = time.time()
        
        if self.human_state == SpeakerState.IDLE:
            if level > self.speech_threshold:
                self.human_state = SpeakerState.SPEAKING
                self.speech_start_time = now
                self.last_active_time = now
                
        elif self.human_state == SpeakerState.SPEAKING:
            if level < self.speech_threshold:
                # Only count as speech if duration exceeds minimum
                if now - self.speech_start_time > self.min_speech_duration:
                    self.human_state = SpeakerState.PROCESSING
                    self.metrics.last_human_speech_end = now
                    # Track turn duration
                    self.metrics.turn_durations.append(now - self.speech_start_time)
                else:
                    self.human_state = SpeakerState.IDLE
            else:
                self.last_active_time = now

    def update_ai_audio(self, level: float) -> None:
        """Update AI speech state based on audio level"""
        now = time.time()
        
        if self.ai_state == SpeakerState.IDLE:
            if level > self.speech_threshold:
                # Check for interruption
                if self.human_state in (SpeakerState.SPEAKING, SpeakerState.PROCESSING):
                    self.metrics.interruption_count += 1
                self.ai_state = SpeakerState.SPEAKING
                
        elif self.ai_state == SpeakerState.SPEAKING:
            if level < self.speech_threshold:
                self.ai_state = SpeakerState.LISTENING
                self.metrics.last_ai_speech_end = now
                # Track gap after AI speech
                if self.metrics.last_human_speech_end:
                    self.metrics.speech_gaps.append(
                        self.metrics.last_ai_speech_end - self.metrics.last_human_speech_end
                    )

    def should_process_audio(self) -> bool:
        """Determine if we should process incoming audio"""
        # Don't process while AI is speaking
        if self.ai_state == SpeakerState.SPEAKING:
            return False
            
        # Check if we're in an active turn
        if self.human_state == SpeakerState.SPEAKING:
            return True
            
        # Allow brief pauses during processing
        if (self.human_state == SpeakerState.PROCESSING and 
            time.time() - self.last_active_time < self.get_dynamic_pause()):
            return True
            
        return False

    def get_dynamic_pause(self) -> float:
        """Calculate dynamic pause threshold based on conversation metrics"""
        if not self.metrics.turn_durations:
            return 0.5  # Default pause
            
        # Use recent turn durations to estimate natural pause length
        avg_turn = np.mean(self.metrics.turn_durations)
        if avg_turn < 1.0:
            return 0.3  # Short turns = shorter pauses
        elif avg_turn < 2.0:
            return 0.5  # Medium turns = medium pauses
        else:
            return 0.8  # Long turns = longer pauses

    def get_conversation_status(self) -> str:
        """Get formatted conversation status for display"""
        status = (
            f"Human: {self.human_state.value:10} "
            f"AI: {self.ai_state.value:10} "
            f"Interrupts: {self.metrics.interruption_count}"
        )
        if self.metrics.speech_gaps:
            status += f" Avg Gap: {np.mean(self.metrics.speech_gaps):.2f}s"
        return status
