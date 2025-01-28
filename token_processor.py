from typing import Callable, Dict, List, Optional, Pattern
import re
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

@dataclass
class TokenTrigger:
    """Represents a token sequence that triggers an action"""
    pattern: Pattern
    handler: Callable
    description: str
    priority: int = 0
    enabled: bool = True

class TokenProcessor:
    """Processes token sequences and triggers registered handlers"""
    
    def __init__(self):
        self.triggers: Dict[str, TokenTrigger] = {}
        self._buffer: List[str] = []
        self.max_buffer_size = 1000
        
    def register_trigger(self, 
                        pattern: str,
                        handler: Callable,
                        description: str,
                        priority: int = 0) -> None:
        """Register a new token trigger"""
        try:
            compiled_pattern = re.compile(pattern)
            trigger_id = f"trigger_{len(self.triggers)}"
            self.triggers[trigger_id] = TokenTrigger(
                pattern=compiled_pattern,
                handler=handler,
                description=description,
                priority=priority
            )
            logger.info(f"Registered token trigger: {description}")
        except re.error as e:
            logger.error(f"Invalid trigger pattern '{pattern}': {e}")
            raise ValueError(f"Invalid trigger pattern: {e}")
            
    def process_tokens(self, tokens: List[str]) -> None:
        """Process a batch of tokens through registered triggers"""
        # Add new tokens to buffer
        self._buffer.extend(tokens)
        
        # Trim buffer if needed
        if len(self._buffer) > self.max_buffer_size:
            self._buffer = self._buffer[-self.max_buffer_size:]
            
        # Get buffer content as string
        buffer_text = " ".join(self._buffer)
        
        # Check triggers in priority order
        sorted_triggers = sorted(
            self.triggers.values(),
            key=lambda t: t.priority,
            reverse=True
        )
        
        for trigger in sorted_triggers:
            if not trigger.enabled:
                continue
                
            try:
                if match := trigger.pattern.search(buffer_text):
                    # Extract matched text
                    matched_text = match.group(0)
                    
                    # Call handler with matched text
                    try:
                        trigger.handler(matched_text)
                        logger.debug(f"Triggered handler for: {matched_text}")
                    except Exception as e:
                        logger.error(f"Error in trigger handler: {e}")
                        
                    # Remove matched text from buffer
                    start_idx = match.start()
                    end_idx = match.end()
                    token_count = len(matched_text.split())
                    self._buffer = self._buffer[token_count:]
                    
            except Exception as e:
                logger.error(f"Error processing trigger: {e}")
                
    def clear_buffer(self) -> None:
        """Clear the token buffer"""
        self._buffer.clear()
        
    def disable_trigger(self, trigger_id: str) -> None:
        """Disable a specific trigger"""
        if trigger_id in self.triggers:
            self.triggers[trigger_id].enabled = False
            
    def enable_trigger(self, trigger_id: str) -> None:
        """Enable a specific trigger"""
        if trigger_id in self.triggers:
            self.triggers[trigger_id].enabled = True
            
    def remove_trigger(self, trigger_id: str) -> None:
        """Remove a registered trigger"""
        if trigger_id in self.triggers:
            del self.triggers[trigger_id]
