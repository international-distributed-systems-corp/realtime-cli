"""
State management for the Realtime API client
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from queue import Queue
from enum import Enum

class ResponseState(Enum):
    """Possible states for the response system"""
    IDLE = "idle"
    PROCESSING = "processing"
    RESPONDING = "responding"
    ERROR = "error"

@dataclass
class AudioState:
    """Global audio state management"""
    is_recording: bool = False
    is_playing: bool = False
    input_queue: Queue = field(default_factory=Queue)
    output_queue: Queue = field(default_factory=Queue)
    current_input_buffer: List[bytes] = field(default_factory=list)
    current_output_buffer: List[bytes] = field(default_factory=list)
    sample_rate: int = 24000
    channels: int = 1
    chunk_size: int = 1024
    storage: Any = None  # Will hold AudioStorage instance

@dataclass
class ConversationState:
    """Tracks the current conversation state"""
    conversation_id: Optional[str] = None
    current_item_id: Optional[str] = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    context: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class SessionState:
    """Global session state"""
    session_id: Optional[str] = None
    audio: AudioState = field(default_factory=AudioState)
    conversation: ConversationState = field(default_factory=ConversationState)
    response_state: ResponseState = ResponseState.IDLE
    current_response_id: Optional[str] = None
    rate_limits: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # Track all events
    events_received: List[Dict[str, Any]] = field(default_factory=list)
    events_sent: List[Dict[str, Any]] = field(default_factory=list)
    
    # Track specific event counts
    event_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Track timing information
    last_event_time: Optional[float] = None
    session_start_time: Optional[float] = None
    
    # Track rate limits
    token_usage: Dict[str, int] = field(default_factory=lambda: {"total": 0, "input": 0, "output": 0})
    request_count: int = 0
    
    def reset(self) -> None:
        """Reset the session state"""
        self.audio = AudioState()
        self.conversation = ConversationState()
        self.response_state = ResponseState.IDLE
        self.current_response_id = None
