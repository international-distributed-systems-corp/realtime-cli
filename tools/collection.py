"""Collection classes for managing multiple tools."""

import logging
from typing import Any

from anthropic.types.beta import BetaToolUnionParam

from .base import (
    BaseAnthropicTool,
    ToolError,
    ToolFailure,
    ToolResult,
)

logger = logging.getLogger(__name__)


class ToolCollection:
    """A collection of anthropic-defined tools."""

    def __init__(self, *tools: BaseAnthropicTool):
        self.tools = tools
        # Build tool map using the correct key based on tool format
        self.tool_map = {}
        for tool in tools:
            tool_param = tool.to_params()
            if tool_param.get("type") == "function" and "function" in tool_param:
                name = tool_param["function"]["name"]
            else:
                name = tool_param.get("name", "unknown")
            self.tool_map[name] = tool

    def to_params(
        self,
    ) -> list[BetaToolUnionParam]:
        return [tool.to_params() for tool in self.tools]
    
    def to_realtime_params(self) -> list[dict]:
        """Convert tools to OpenAI Realtime API format (flattened structure)"""
        params = []
        for tool in self.tools:
            tool_param = tool.to_params()
            tool_name = tool_param.get("name", "unknown_tool")
            
            # Convert Anthropic tools to OpenAI Realtime API format
            if tool_param.get("type") == "bash_20241022":
                realtime_param = {
                    "type": "function",
                    "name": "bash",
                    "description": "Execute bash commands on the system",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The bash command to execute"
                            }
                        },
                        "required": ["command"],
                        "additionalProperties": False
                    }
                }
                params.append(realtime_param)
            elif tool_param.get("type") == "computer_20241022":
                realtime_param = {
                    "type": "function", 
                    "name": "computer",
                    "description": "Take screenshots and control the computer with keyboard and mouse actions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["screenshot", "click", "key", "type", "cursor_position", "left_mouse_click", "left_mouse_drag", "right_mouse_click", "middle_mouse_click", "double_click", "scroll"],
                                "description": "The action to perform"
                            },
                            "coordinate": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "minItems": 2,
                                "maxItems": 2,
                                "description": "The [x, y] coordinate for click/drag actions"
                            },
                            "text": {
                                "type": "string",
                                "description": "Text to type when action is 'type'"
                            }
                        },
                        "required": ["action"],
                        "additionalProperties": False
                    }
                }
                params.append(realtime_param)
            elif tool_param.get("type") == "text_editor_20241022":
                realtime_param = {
                    "type": "function",
                    "name": "str_replace_editor", 
                    "description": "Edit files using string replacement operations",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "enum": ["str_replace", "view", "create", "undo_edit"],
                                "description": "The editing command to execute"
                            },
                            "path": {
                                "type": "string",
                                "description": "Path to the file to edit"
                            },
                            "old_str": {
                                "type": "string", 
                                "description": "String to replace (for str_replace command)"
                            },
                            "new_str": {
                                "type": "string",
                                "description": "Replacement string (for str_replace command)"
                            },
                            "file_text": {
                                "type": "string",
                                "description": "File content (for create command)"
                            }
                        },
                        "required": ["command"],
                        "additionalProperties": False
                    }
                }
                params.append(realtime_param)
            elif tool_param.get("type") == "filesystem_20241022":
                realtime_param = {
                    "type": "function",
                    "name": "filesystem",
                    "description": "Navigate and manage the file system (list directories, create/delete files, etc.)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["list_directory", "get_current_directory", "change_directory", "create_directory", "remove_directory", "copy_file", "move_file", "delete_file", "get_file_info", "find_files"],
                                "description": "The file system operation to perform"
                            },
                            "path": {
                                "type": "string",
                                "description": "Path for the operation"
                            },
                            "destination": {
                                "type": "string",
                                "description": "Destination path for copy/move operations"
                            },
                            "pattern": {
                                "type": "string",
                                "description": "Search pattern for find_files"
                            },
                            "recursive": {
                                "type": "boolean",
                                "description": "Whether to operate recursively"
                            }
                        },
                        "required": ["action"],
                        "additionalProperties": False
                    }
                }
                params.append(realtime_param)
            elif tool_param.get("type") == "web_20241022":
                realtime_param = {
                    "type": "function",
                    "name": "web",
                    "description": "Search the web and fetch web content",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["search", "fetch", "get_headers", "download_file"],
                                "description": "The web operation to perform"
                            },
                            "query": {
                                "type": "string",
                                "description": "Search query for web search"
                            },
                            "url": {
                                "type": "string",
                                "description": "URL to fetch or download"
                            },
                            "file_path": {
                                "type": "string",
                                "description": "Local file path for downloads"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of search results"
                            }
                        },
                        "required": ["action"],
                        "additionalProperties": False
                    }
                }
                params.append(realtime_param)
            elif tool_param.get("type") == "system_monitor_20241022":
                realtime_param = {
                    "type": "function",
                    "name": "system_monitor",
                    "description": "Monitor system resources and manage processes",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["get_system_info", "get_cpu_info", "get_memory_info", "get_disk_info", "get_network_info", "list_processes", "get_process_info", "kill_process", "get_boot_time"],
                                "description": "The system monitoring operation to perform"
                            },
                            "process_id": {
                                "type": "integer",
                                "description": "Process ID for process operations"
                            },
                            "process_name": {
                                "type": "string",
                                "description": "Process name for process operations"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Limit number of results"
                            }
                        },
                        "required": ["action"],
                        "additionalProperties": False
                    }
                }
                params.append(realtime_param)
            elif tool_param.get("type") == "calculator_20241022":
                realtime_param = {
                    "type": "function",
                    "name": "calculator",
                    "description": "Perform mathematical calculations and operations",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["calculate", "statistics", "convert_units", "geometry", "trigonometry"],
                                "description": "The mathematical operation to perform"
                            },
                            "expression": {
                                "type": "string",
                                "description": "Mathematical expression to calculate"
                            },
                            "numbers": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "List of numbers for statistical operations"
                            },
                            "unit_from": {
                                "type": "string",
                                "description": "Source unit for conversion"
                            },
                            "unit_to": {
                                "type": "string",
                                "description": "Target unit for conversion"
                            },
                            "value": {
                                "type": "number",
                                "description": "Numeric value for operations"
                            },
                            "shape": {
                                "type": "string",
                                "description": "Geometric shape for calculations"
                            },
                            "angle_unit": {
                                "type": "string",
                                "enum": ["degrees", "radians"],
                                "description": "Unit for angle measurements"
                            }
                        },
                        "required": ["action"],
                        "additionalProperties": False
                    }
                }
                params.append(realtime_param)
            elif tool_param.get("type") == "reasoning_20241022":
                realtime_param = {
                    "type": "function",
                    "name": "reasoning",
                    "description": "Advanced reasoning capabilities using logical, analytical, and creative thinking",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reasoning_type": {
                                "type": "string",
                                "enum": [
                                    "deductive", "inductive", "abductive", "argument_analysis", "conditional",
                                    "causal_analysis", "risk_assessment", "trend_analysis", 
                                    "brainstorming", "analogy", "reframing", "orchestrate"
                                ],
                                "description": "The type of reasoning to apply"
                            },
                            "premises": {"type": "string", "description": "Premises for deductive reasoning"},
                            "query": {"type": "string", "description": "Query for deductive reasoning"},
                            "observations": {"type": "string", "description": "Observations for inductive/abductive reasoning"},
                            "argument_text": {"type": "string", "description": "Argument text for analysis"},
                            "conditional_statement": {"type": "string", "description": "If-then statement for conditional reasoning"},
                            "situation": {"type": "string", "description": "Situation for causal analysis"},
                            "scenario": {"type": "string", "description": "Scenario for risk assessment"},
                            "data_description": {"type": "string", "description": "Data description for trend analysis"},
                            "problem": {"type": "string", "description": "Problem for brainstorming"},
                            "constraints": {"type": "string", "description": "Constraints for brainstorming"},
                            "source_domain": {"type": "string", "description": "Domain for analogy reasoning"},
                            "original_problem": {"type": "string", "description": "Problem for reframing"},
                            "problem_description": {"type": "string", "description": "Problem for orchestrated reasoning"},
                            "context": {"type": "string", "description": "Additional context"},
                            "mode": {
                                "type": "string", 
                                "enum": ["strategy_only", "full_execution"],
                                "description": "Orchestration mode"
                            }
                        },
                        "required": ["reasoning_type"],
                        "additionalProperties": False
                    }
                }
                params.append(realtime_param)
            elif tool_param.get("type") == "function" and "function" in tool_param:
                # Standard OpenAI format - flatten the structure for Realtime API
                realtime_param = {
                    "type": "function",
                    "name": tool_param["function"]["name"],
                    "parameters": tool_param["function"]["parameters"]
                }
                if "description" in tool_param["function"]:
                    realtime_param["description"] = tool_param["function"]["description"]
                params.append(realtime_param)
            else:
                # Unknown or unsupported format - log warning
                logger.warning(f"Unsupported tool format for realtime API: {tool_param}")
                
        return params

    async def run(self, *, name: str, tool_input: dict[str, Any]) -> ToolResult:
        tool = self.tool_map.get(name)
        if not tool:
            return ToolFailure(error=f"Tool {name} is invalid")
        try:
            return await tool(**tool_input)
        except ToolError as e:
            return ToolFailure(error=e.message)
