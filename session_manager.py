from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import logging
from system_tools import SystemTools

logger = logging.getLogger(__name__)

@dataclass
class SessionConfig:
    """Configuration for a Realtime API session"""
    model: str = "gpt-4o-realtime-preview-2024-12-17"
    modalities: List[str] = field(default_factory=lambda: ["text", "audio"])
    instructions: str = "You are a friendly assistant."
    voice: str = "alloy"
    input_audio_format: str = "pcm16"
    output_audio_format: str = "pcm16"
    input_audio_transcription: Dict[str, Any] = field(default_factory=lambda: {"model": "whisper-1"})
    turn_detection: Dict[str, Any] = field(default_factory=lambda: {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 500,
        "create_response": True
    })
    tools: List[Dict[str, Any]] = field(default_factory=list)
    tool_choice: Optional[str] = None
    temperature: Optional[float] = None
    max_response_output_tokens: Optional[int] = None

class SessionManager:
    """Manages dynamic session configuration for Realtime API"""
    
    def __init__(self):
        self.config = SessionConfig()
        self._active_tools: Dict[str, Dict[str, Any]] = {}
        self.system = SystemTools()  # Initialize system tools
        
    def update_system_prompt(self, prompt: str) -> None:
        """Update the system instructions"""
        self.config.instructions = prompt
        logger.info(f"Updated system prompt: {prompt}")
        
    def add_tool(self, tool: Dict[str, Any]) -> None:
        """Add a tool to the session"""
        tool_name = tool.get("name")
        if not tool_name:
            raise ValueError("Tool must have a name")
            
        self._active_tools[tool_name] = tool
        self.config.tools = list(self._active_tools.values())
        logger.info(f"Added tool: {tool_name}")
        
    def remove_tool(self, tool_name: str) -> None:
        """Remove a tool from the session"""
        if tool_name in self._active_tools:
            del self._active_tools[tool_name]
            self.config.tools = list(self._active_tools.values())
            logger.info(f"Removed tool: {tool_name}")
            
    def clear_tools(self) -> None:
        """Remove all tools from the session"""
        self._active_tools.clear()
        self.config.tools = []
        logger.info("Cleared all tools")
        
    def get_config(self) -> Dict[str, Any]:
        """Get the current session configuration"""
        return {
            k: v for k, v in self.config.__dict__.items() 
            if v is not None and k != "_active_tools"
        }
        
    def update_config(self, **kwargs) -> None:
        """Update session configuration parameters"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"Updated config {key}: {value}")
            else:
                logger.warning(f"Unknown config parameter: {key}")
