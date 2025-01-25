"""
Event handling system for OpenAI Realtime API
"""
from enum import Enum
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
import logging
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EventType(Enum):
    """All supported event types from the Realtime API"""
    ERROR = "error"
    SESSION_CREATED = "session.created"
    SESSION_UPDATED = "session.updated"
    CONVERSATION_CREATED = "conversation.created"
    CONVERSATION_ITEM_CREATED = "conversation.item.created"
    AUDIO_TRANSCRIPTION_COMPLETED = "conversation.item.input_audio_transcription.completed"
    AUDIO_TRANSCRIPTION_FAILED = "conversation.item.input_audio_transcription.failed"
    ITEM_TRUNCATED = "conversation.item.truncated"
    ITEM_DELETED = "conversation.item.deleted"
    AUDIO_BUFFER_COMMITTED = "input_audio_buffer.committed"
    AUDIO_BUFFER_CLEARED = "input_audio_buffer.cleared"
    SPEECH_STARTED = "input_audio_buffer.speech_started"
    SPEECH_STOPPED = "input_audio_buffer.speech_stopped"
    RESPONSE_CREATED = "response.created"
    RESPONSE_DONE = "response.done"
    OUTPUT_ITEM_ADDED = "response.output_item.added"
    OUTPUT_ITEM_DONE = "response.output_item.done"
    CONTENT_PART_ADDED = "response.content_part.added"
    CONTENT_PART_DONE = "response.content_part.done"
    TEXT_DELTA = "response.text.delta"
    TEXT_DONE = "response.text.done"
    AUDIO_TRANSCRIPT_DELTA = "response.audio_transcript.delta"
    AUDIO_TRANSCRIPT_DONE = "response.audio_transcript.done"
    AUDIO_DELTA = "response.audio.delta"
    AUDIO_DONE = "response.audio.done"
    FUNCTION_CALL_DELTA = "response.function_call_arguments.delta"
    FUNCTION_CALL_DONE = "response.function_call_arguments.done"
    RATE_LIMITS_UPDATED = "rate_limits.updated"

@dataclass
class RateLimit:
    """Rate limit information"""
    name: str
    limit: int
    remaining: int
    reset_seconds: int

class EventHandler:
    """Handles all incoming events from the Realtime API"""
    
    def __init__(self):
        self._handlers: Dict[EventType, List[Callable]] = {event_type: [] for event_type in EventType}
        self.rate_limits: Dict[str, RateLimit] = {}
    
    def register(self, event_type: EventType, handler: Callable) -> None:
        """Register a handler for an event type"""
        self._handlers[event_type].append(handler)
        
    def handle_event(self, event: Dict[str, Any]) -> None:
        """Process an incoming event"""
        try:
            event_type = EventType(event.get("type"))
            
            # Log all events at debug level
            logger.debug(f"Received event: {event_type.value}")
            
            # Special handling for rate limits
            if event_type == EventType.RATE_LIMITS_UPDATED:
                self._update_rate_limits(event.get("rate_limits", []))
            
            # Special handling for errors
            if event_type == EventType.ERROR:
                self._handle_error(event.get("error", {}))
                
            # Call all registered handlers
            for handler in self._handlers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Handler error for {event_type.value}: {str(e)}")
                    
        except ValueError:
            logger.warning(f"Unknown event type: {event.get('type')}")
        except Exception as e:
            logger.error(f"Error handling event: {str(e)}")
            
    def _update_rate_limits(self, limits: List[Dict[str, Any]]) -> None:
        """Update stored rate limits"""
        for limit in limits:
            self.rate_limits[limit["name"]] = RateLimit(
                name=limit["name"],
                limit=limit["limit"],
                remaining=limit["remaining"],
                reset_seconds=limit["reset_seconds"]
            )
            
    def _handle_error(self, error: Dict[str, Any]) -> None:
        """Handle error events"""
        error_type = error.get("type", "unknown")
        message = error.get("message", "No message")
        code = error.get("code", "no_code")
        
        logger.error(f"API Error: {error_type} - {code} - {message}")
        
    def get_rate_limit(self, name: str) -> Optional[RateLimit]:
        """Get current rate limit info"""
        return self.rate_limits.get(name)
