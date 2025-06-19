"""End session tool for gracefully terminating conversations."""

from .base import BaseAnthropicTool, ToolResult
from typing import Optional

class EndSessionTool(BaseAnthropicTool):
    """A tool for ending the current session gracefully."""
    
    name = "end_session"
    api_type = "function"
    description = "End the current conversation session gracefully"
    
    def to_params(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "Optional reason for ending the session"
                        }
                    },
                    "additionalProperties": False
                }
            }
        }
    
    async def __call__(self, reason: Optional[str] = None) -> ToolResult:
        """End the session."""
        if reason:
            return ToolResult(output=f"Session ended: {reason}")
        else:
            return ToolResult(output="Session ended gracefully")