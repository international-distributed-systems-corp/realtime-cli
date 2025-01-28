import httpx
import functools
import logging
from typing import Optional, Dict, Any, Callable, TypeVar, ParamSpec, List
from pydantic import BaseModel

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

class ToolRegistryClient:
    """Client for interacting with the Tool Registry service"""
    
    def __init__(self, base_url: str = "http://localhost:2016"):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        
    async def register_endpoint(self, 
                              name: str,
                              description: str,
                              method: str,
                              path: str,
                              input_schema: Dict[str, Any],
                              output_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Register an HTTP endpoint as a tool"""
        try:
            response = await self.client.post("/tools/endpoint", json={
                "name": name,
                "description": description,
                "method": method,
                "path": path,
                "input_schema": input_schema,
                "output_schema": output_schema
            })
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to register endpoint tool: {str(e)}")
            raise

    async def register_function(self,
                              name: str, 
                              description: str,
                              func: Callable,
                              input_schema: Dict[str, Any],
                              output_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Register a Python function as a tool"""
        try:
            response = await self.client.post("/tools/function", json={
                "name": name,
                "description": description,
                "code": func.__code__.co_code.hex(),
                "input_schema": input_schema,
                "output_schema": output_schema
            })
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to register function tool: {str(e)}")
            raise

class tools:
    """Decorators for registering tools"""
    
    @staticmethod
    def endpoint(name: str,
                description: str,
                method: str = "POST",
                path: Optional[str] = None,
                input_schema: Optional[Dict[str, Any]] = None,
                output_schema: Optional[Dict[str, Any]] = None):
        """Decorator to register an endpoint as a tool"""
        def decorator(func: Callable[P, T]) -> Callable[P, T]:
            @functools.wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                # Register the endpoint
                client = ToolRegistryClient()
                await client.register_endpoint(
                    name=name,
                    description=description,
                    method=method,
                    path=path or f"/tools/{name}",
                    input_schema=input_schema or {},
                    output_schema=output_schema or {}
                )
                return await func(*args, **kwargs)
            return wrapper
        return decorator

    @staticmethod
    def function(name: str,
                description: str,
                input_schema: Optional[Dict[str, Any]] = None,
                output_schema: Optional[Dict[str, Any]] = None):
        """Decorator to register a function as a tool"""
        def decorator(func: Callable[P, T]) -> Callable[P, T]:
            @functools.wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                # Register the function
                client = ToolRegistryClient()
                await client.register_function(
                    name=name,
                    description=description,
                    func=func,
                    input_schema=input_schema or {},
                    output_schema=output_schema or {}
                )
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools"""
        try:
            response = await self.client.get("/tools")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list tools: {str(e)}")
            return []

    async def call_function(self, name: str, parameters: Dict[str, Any]) -> Any:
        """Calls the specified tool with given parameters"""
        try:
            response = await self.client.post("/execute_tool", json={
                "tool_id": name,
                "input_data": parameters
            })
            response.raise_for_status()
            result = response.json()
            return result.get('output_data')
        except Exception as e:
            logger.error(f"Failed to call function {name}: {str(e)}")
            raise
