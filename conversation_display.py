import sys
from typing import Optional
from dataclasses import dataclass
from enum import Enum

class SpeakerType(Enum):
    USER = "User"
    AGENT = "Agent"

@dataclass
class TranscriptLine:
    speaker: SpeakerType
    text: str
    is_complete: bool = True

class ConversationDisplay:
    """Handles real-time display of conversation with audio levels"""
    
    def __init__(self):
        self.current_line: Optional[TranscriptLine] = None
        self.input_level: float = 0
        self.output_level: float = 0
        self.status_message: str = ""
        
    def _get_level_bar(self, level: float, width: int = 20) -> str:
        """Generate a visual level meter"""
        filled = int(level * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"
        
    def update_input_level(self, level: float) -> None:
        """Update the input audio level"""
        self.input_level = min(1.0, max(0.0, level))
        
    def update_output_level(self, level: float) -> None:
        """Update the output audio level"""
        self.output_level = min(1.0, max(0.0, level))
        
    def set_status(self, message: str) -> None:
        """Update the status message"""
        self.status_message = message
        
    def start_user_speech(self) -> None:
        """Start a new user speech line"""
        self.current_line = TranscriptLine(SpeakerType.USER, "", False)
        
    def start_agent_speech(self) -> None:
        """Start a new agent speech line"""
        self.current_line = TranscriptLine(SpeakerType.AGENT, "", False)
        
    def update_current_text(self, text: str) -> None:
        """Update the current speech text"""
        if self.current_line:
            self.current_line.text = text
            
    def complete_current_line(self) -> None:
        """Mark the current line as complete"""
        if self.current_line:
            self.current_line.is_complete = True
            
    def get_display(self) -> str:
        """Generate the current display state"""
        # Clear screen and move to top
        display = "\033[2J\033[H"
        
        # Audio levels
        display += f"User Audio:  {self._get_level_bar(self.input_level)}\n"
        display += f"Agent Audio: {self._get_level_bar(self.output_level)}\n"
        display += "\n"
        
        # Current speech (if any)
        if self.current_line:
            prefix = f"{self.current_line.speaker.value}: "
            text = self.current_line.text
            if not self.current_line.is_complete:
                text += "▋"  # Add cursor for incomplete line
            display += f"{prefix}{text}\n"
            
        # Status message
        if self.status_message:
            display += f"\nStatus: {self.status_message}\n"
            
        return display
        
    def render(self) -> None:
        """Render the current display state"""
        sys.stdout.write(self.get_display())
        sys.stdout.flush()
