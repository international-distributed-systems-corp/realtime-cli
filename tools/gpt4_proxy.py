"""
Proxy tool that allows GPT-4 to delegate tasks to Claude
"""
from typing import ClassVar, Literal
from anthropic.types.beta import BetaToolUnionParam

from .base import BaseAnthropicTool, ToolResult
from .collection import ToolCollection

class GPT4ProxyTool(BaseAnthropicTool):
    """
    A tool that allows GPT-4 to delegate tasks to Claude.
    """
    name: ClassVar[Literal["delegate_to_claude"]] = "delegate_to_claude"
    
    def __init__(self, tool_collection: ToolCollection):
        self.tool_collection = tool_collection
        super().__init__()

    async def __call__(self, *, instruction: str, **kwargs) -> ToolResult:
        """
        Relay instructions from GPT-4 to Claude and return results
        """
        print(f"\nGPT-4 delegating to Claude: {instruction}")
        
        # Claude will parse this instruction and use the appropriate tools
        # The results will be returned through the normal tool result channels
        return ToolResult(
            output=f"Instruction received: {instruction}\nClaude will execute this and report back."
        )

    def to_params(self) -> BetaToolUnionParam:
        return {
            "name": self.name,
            "description": "Delegate computer control tasks to Claude, who has direct access to the computer tools",
            "parameters": {
                "type": "object",
                "properties": {
                    "instruction": {
                        "type": "string",
                        "description": "The instruction to send to Claude"
                    }
                },
                "required": ["instruction"]
            }
        }
