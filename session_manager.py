from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
import logging
from system_tools import SystemTools
from token_processor import TokenProcessor

logger = logging.getLogger(__name__)

@dataclass
class SessionConfig:
    """Configuration for a Realtime API session"""
    model: str = "gpt-4o-realtime-preview-2024-12-17"
    modalities: List[str] = field(default_factory=lambda: ["text", "audio"])
    instructions: str = """You are a highly capable AI assistant with access to both voice and text interaction, as well as various system tools and functions. You can:

1. Process and respond to both voice and text input naturally
2. Execute system commands and file operations safely when requested
3. Maintain context across a conversation
4. Handle interruptions and turn-taking gracefully
5. Provide real-time audio feedback and visual indicators
6. Access and manipulate files and directories when needed
7. Perform various string and data manipulations
8. Make API calls and integrate with external services

Always aim to be helpful, clear, and efficient in your responses. If you need to perform system operations, ensure they are safe and clearly explain what you're doing. Feel free to use any available tools to best assist the user."""
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
        self._tool_handlers: Dict[str, callable] = {}
        self.system = SystemTools()  # Initialize system tools
        self.token_processor = TokenProcessor()  # Initialize token processor
        
        # Register built-in tools
        self._register_builtin_tools()
        
        # Register some example token triggers
        self._register_builtin_triggers()
        
    def _register_builtin_tools(self):
        """Register built-in system tools"""
        self.register_tool(
            "file_read",
            "Read contents of a file",
            lambda args: self.system.read_file(args["path"])
        )
        
        self.register_tool(
            "file_write", 
            "Write content to a file",
            lambda args: self.system.write_file(args["path"], args["content"])
        )
        
        self.register_tool(
            "list_directory",
            "List contents of a directory",
            lambda args: self.system.list_directory(args.get("path"))
        )
        
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
                
    def execute_system_command(self, command: str) -> str:
        """Execute a system command and return the result"""
        try:
            # Validate command for safety
            if any(unsafe in command.lower() for unsafe in ['rm -rf', 'mkfs', '> /dev']):
                raise ValueError("Unsafe command detected")
                
            result = self.system.run_command(command)
            output = result.stdout if result.stdout else "Command executed successfully"
            logger.info(f"Executed command: {command}")
            return output
        except Exception as e:
            logger.error(f"Failed to execute command {command}: {e}")
            return f"Error executing command: {str(e)}"
            
    def register_tool(self, name: str, description: str, handler: callable) -> None:
        """Register a new tool with custom handler"""
        tool = {
            "type": "function",
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "args": {
                        "type": "object",
                        "description": "Arguments for the tool"
                    }
                }
            }
        }
        self._tool_handlers[name] = handler
        self.add_tool(tool)
        logger.info(f"Registered tool: {name}")
        
    def execute_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """Execute a registered tool"""
        if name not in self._tool_handlers:
            raise ValueError(f"Tool {name} not registered")
            
        handler = self._tool_handlers[name]
        try:
            result = handler(args)
            logger.info(f"Tool {name} executed successfully")
            return result
        except Exception as e:
            logger.error(f"Tool {name} failed: {str(e)}")
            raise
            
    def _register_builtin_triggers(self):
        """Register built-in token triggers"""
        # Example: Trigger on "execute {tool_name}"
        self.token_processor.register_trigger(
            pattern=r"execute (\w+)",
            handler=lambda match: self.execute_tool(match.group(1), {}),
            description="Execute tool by name",
            priority=1
        )
        
        # Example: Trigger on "list tools"
        self.token_processor.register_trigger(
            pattern=r"list tools",
            handler=lambda _: print("\n".join(self._active_tools.keys())),
            description="List available tools",
            priority=1
        )
        
    def register_token_trigger(self,
                             pattern: str,
                             handler: Callable,
                             description: str,
                             priority: int = 0) -> None:
        """Register a new token trigger"""
        self.token_processor.register_trigger(
            pattern=pattern,
            handler=handler,
            description=description,
            priority=priority
        )
        
    def process_tokens(self, tokens: List[str]) -> None:
        """Process tokens through registered triggers"""
        self.token_processor.process_tokens(tokens)
