import os
import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from fastapi import HTTPException

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class Tool(BaseModel):
    """Model representing a tool definition"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    code: Optional[str] = None
    version: str = "1.0.0"

class ToolRegistry:
    """Manages registration and access to tools"""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.tool_versions: Dict[str, List[Tool]] = {}
        logger.info("Tool registry initialized")

    def register_tool(self, tool: Tool) -> str:
        """Register a new tool or update existing one"""
        try:
            # Store tool by name and version
            tool_key = f"{tool.name}@{tool.version}"
            self.tools[tool_key] = tool
            
            # Track versions
            if tool.name not in self.tool_versions:
                self.tool_versions[tool.name] = []
            self.tool_versions[tool.name].append(tool)
            
            logger.info(f"Registered tool: {tool_key}")
            return tool_key
            
        except Exception as e:
            logger.error(f"Error registering tool {tool.name}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to register tool: {str(e)}"
            )

    def get_tool(self, name: str, version: Optional[str] = None) -> Tool:
        """Get a specific tool by name and optional version"""
        try:
            if version:
                tool_key = f"{name}@{version}"
                if tool_key not in self.tools:
                    raise KeyError(f"Tool {name} version {version} not found")
                return self.tools[tool_key]
            else:
                # Get latest version if no specific version requested
                if name not in self.tool_versions:
                    raise KeyError(f"Tool {name} not found")
                versions = self.tool_versions[name]
                return versions[-1]  # Latest version
                
        except KeyError as e:
            logger.warning(str(e))
            raise HTTPException(
                status_code=404,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error retrieving tool {name}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve tool: {str(e)}"
            )

    def list_tools(self) -> List[Tool]:
        """List all registered tools (latest versions)"""
        try:
            latest_tools = []
            for name in self.tool_versions:
                latest_tools.append(self.tool_versions[name][-1])
            return latest_tools
            
        except Exception as e:
            logger.error(f"Error listing tools: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to list tools: {str(e)}"
            )

    def get_tool_versions(self, name: str) -> List[Tool]:
        """Get all versions of a specific tool"""
        try:
            if name not in self.tool_versions:
                raise KeyError(f"Tool {name} not found")
            return self.tool_versions[name]
            
        except KeyError as e:
            logger.warning(str(e))
            raise HTTPException(
                status_code=404,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error retrieving versions for {name}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve tool versions: {str(e)}"
            )

# Global registry instance
registry = ToolRegistry()
