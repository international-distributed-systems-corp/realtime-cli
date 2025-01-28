import os
import json
import logging
import uvicorn
from enum import Enum
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class ToolType(str, Enum):
    ENDPOINT = "endpoint"
    FUNCTION = "function"
    SCRIPT = "script"

class Tool(BaseModel):
    """Model representing a tool definition"""
    name: str
    description: str
    type: ToolType
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    code: Optional[str] = None
    endpoint: Optional[Dict[str, str]] = None
    version: str = "1.0.0"
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

# Initialize FastAPI app
app = FastAPI(
    title="Tool Registry API",
    version="1.0.0",
    docs_url="/docs"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ToolRegistry:
    """Manages registration and access to tools"""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.tool_versions: Dict[str, List[Tool]] = {}
        self.tags: Dict[str, List[str]] = {}
        self.search_index: Dict[str, List[float]] = {}  # For vector search
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

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools in OpenAI format"""
        try:
            tools = []
            for name in self.tool_versions:
                tool = self.tool_versions[name][-1]
                tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema
                })
            return tools
            
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

@app.post("/tools/endpoint")
async def register_endpoint_tool(tool: Tool):
    """Register an HTTP endpoint as a tool"""
    if tool.type != ToolType.ENDPOINT:
        raise HTTPException(status_code=400, detail="Tool type must be 'endpoint'")
    return registry.register_tool(tool)

@app.post("/tools/function") 
async def register_function_tool(tool: Tool):
    """Register a Python function as a tool"""
    if tool.type != ToolType.FUNCTION:
        raise HTTPException(status_code=400, detail="Tool type must be 'function'")
    return registry.register_tool(tool)

@app.get("/tools/search")
async def search_tools(query: str, limit: int = 10):
    """Search tools by name, description, or tags"""
    return registry.search_tools(query, limit)

@app.get("/tools/tags/{tag}")
async def get_tools_by_tag(tag: str):
    """Get all tools with a specific tag"""
    return registry.get_tools_by_tag(tag)

@app.get("/tools/{tool_id}/versions")
async def get_tool_versions(tool_id: str):
    """Get all versions of a specific tool"""
    return registry.get_tool_versions(tool_id)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=2016)
