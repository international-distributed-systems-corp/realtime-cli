import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from modal import Image, App, Secret, asgi_app
from modal import App, Image, Secret, asgi_app

# Try to import Neo4j
try:
    from neo4j import AsyncGraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    print("Warning: Neo4j driver not installed. Some functionality may be limited.")
    NEO4J_AVAILABLE = False
    AsyncGraphDatabase = None

# Configuration
TOOL_MGMT_APP_LABEL = "tool_management_api"
NEO4J_SECRET_NAME = "distributed-systems"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Modal configuration
image = (
    Image.debian_slim()
    .pip_install([
        "fastapi",
        "uvicorn", 
        "pydantic",
        "neo4j",
        "python-dotenv"
    ])
)

# Create Modal app
stub = App(TOOL_MGMT_APP_LABEL)

# Logging setup
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# Modal configuration
image = (
    Image.debian_slim()
    .pip_install([
        "fastapi",
        "uvicorn",
        "pydantic",
        "neo4j",
        "python-dotenv",
    ])
    .apt_install(["python3-dev", "gcc"])
)

# Create the Modal stub
stub = App(TOOL_MGMT_APP_LABEL)

# Pydantic models
class Tool(BaseModel):
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    code: str

class ToolResponse(BaseModel):
    id: str
    name: str
    description: str
    input_schema: dict
    output_schema: dict

class ToolExecutionRequest(BaseModel):
    tool_id: str
    input_data: Dict[str, Any]

class ToolExecutionResponse(BaseModel):
    tool_id: str
    output_data: Dict[str, Any]

class SequentialToolExecutionRequest(BaseModel):
    tool_ids: List[str]
    initial_input: Dict[str, Any]

class ParallelToolExecutionRequest(BaseModel):
    tool_ids: List[str]
    input_data: Dict[str, Dict[str, Any]]

# Neo4j connection management
class Neo4jConnection:
    """Manages the Neo4j database connection."""

    def __init__(self):
        """Initialize the Neo4j connection using environment variables from secrets."""
        if not NEO4J_AVAILABLE:
            logger.warning("Neo4j driver not installed. Some functionalities are disabled.")
            return

        uri = os.getenv("NEO4J_URI", "neo4j://bolt.n4j.distributed.systems")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "Backstab2025!")
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self):
        """Close the Neo4j connection."""
        if NEO4J_AVAILABLE and self.driver is not None:
            await self.driver.close()

    async def get_session(self):
        """Get a new Neo4j session."""
        if NEO4J_AVAILABLE and self.driver is not None:
            return self.driver.session()
        return None

async def get_db():
    """Dependency to get database session."""
    db = Neo4jConnection()
    try:
        yield db
    finally:
        await db.close()

async def get_session(db: Neo4jConnection = Depends(get_db)):
    """Get a new Neo4j session."""
    session = await db.get_session()
    if session is None:
        raise HTTPException(status_code=500, detail="Neo4j session unavailable.")
    async with session as s:
        yield s

# Utility function for tool execution
    async def execute_tool(tool_id: str, input_data: Dict[str, Any], session) -> Dict[str, Any]:
        """Execute a single tool by looking up the Python code in Neo4j."""
        logger.info(f"Executing tool with id: {tool_id}")
        result = await session.run(
            """
            MATCH (t:Tool)-[:HAS_CODE]->(c:ToolCode)
            WHERE ID(t) = $tool_id
            RETURN c.code AS code
            """,
            tool_id=int(tool_id)
        )

        record = await result.single()
        if record:
            code = record["code"]
            try:
                exec_globals = {"input_data": input_data, "output_data": {}}
                exec(code, exec_globals)
                output_data = exec_globals["output_data"]
                logger.info(f"Tool executed successfully: {tool_id}")
                return output_data
            except Exception as e:
                logger.error(f"Error executing tool {tool_id}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error executing tool: {str(e)}")
        else:
            logger.warning(f"Tool not found for execution with id: {tool_id}")
            raise HTTPException(status_code=404, detail="Tool not found")

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {"message": "Welcome to the Tool Management API"}

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    @app.post("/tools", response_model=ToolResponse)
    async def create_tool(tool: Tool, session=Depends(get_session)):
        logger.info(f"Creating new tool: {tool.name}")
        result = await session.run(
            """
            CREATE (t:Tool {name: $name, description: $description})
            CREATE (s:ToolSchema {input_schema: $input_schema, output_schema: $output_schema})
            CREATE (c:ToolCode {code: $code})
            CREATE (t)-[:HAS_SCHEMA]->(s)
            CREATE (t)-[:HAS_CODE]->(c)
            RETURN t, s
            """,
            name=tool.name,
            description=tool.description,
            input_schema=json.dumps(tool.input_schema),
            output_schema=json.dumps(tool.output_schema),
            code=tool.code,
        )

        record = await result.single()
        if record:
            tool_node = record["t"]
            schema_node = record["s"]
            logger.info(f"Tool created successfully: {tool.name}")
            return ToolResponse(
                id=str(tool_node.id),
                name=tool_node["name"],
                description=tool_node["description"],
                input_schema=json.loads(schema_node["input_schema"]),
                output_schema=json.loads(schema_node["output_schema"]),
            )
        else:
            logger.error(f"Failed to create tool: {tool.name}")
            raise HTTPException(status_code=500, detail="Failed to create tool")

    @app.get("/tools", response_model=List[ToolResponse])
    async def get_tools(session=Depends(get_session)):
        logger.info("Fetching all tools")
        result = await session.run(
            """
            MATCH (t:Tool)-[:HAS_SCHEMA]->(s:ToolSchema)
            RETURN t, s
            """
        )
        tools = []
        async for record in result:
            tool = record["t"]
            schema = record["s"]
            tools.append(
                ToolResponse(
                    id=str(tool.id),
                    name=tool["name"],
                    description=tool["description"],
                    input_schema=json.loads(schema["input_schema"]),
                    output_schema=json.loads(schema["output_schema"]),
                )
            )
        logger.info(f"Fetched {len(tools)} tools")
        return tools

    @app.get("/tools/{tool_id}", response_model=ToolResponse)
    async def get_tool(tool_id: str, session=Depends(get_session)):
        logger.info(f"Fetching tool with id: {tool_id}")
        result = await session.run(
            """
            MATCH (t:Tool)-[:HAS_SCHEMA]->(s:ToolSchema)
            WHERE ID(t) = $tool_id
            RETURN t, s
            """,
            tool_id=int(tool_id),
        )
        record = await result.single()
        if record:
            tool = record["t"]
            schema = record["s"]
            logger.info(f"Tool found: {tool['name']}")
            return ToolResponse(
                id=str(tool.id),
                name=tool["name"],
                description=tool["description"],
                input_schema=json.loads(schema["input_schema"]),
                output_schema=json.loads(schema["output_schema"]),
            )
        else:
            logger.warning(f"Tool not found with id: {tool_id}")
            raise HTTPException(status_code=404, detail="Tool not found")

    @app.put("/tools/{tool_id}", response_model=ToolResponse)
    async def update_tool(tool_id: str, tool: Tool, session=Depends(get_session)):
        logger.info(f"Updating tool with id: {tool_id}")
        result = await session.run(
            """
            MATCH (t:Tool)-[:HAS_SCHEMA]->(s:ToolSchema)
            WHERE ID(t) = $tool_id
            SET t.name = $name,
                t.description = $description,
                s.input_schema = $input_schema,
                s.output_schema = $output_schema
            WITH t, s
            MATCH (t)-[:HAS_CODE]->(c:ToolCode)
            SET c.code = $code
            RETURN t, s
            """,
            tool_id=int(tool_id),
            name=tool.name,
            description=tool.description,
            input_schema=json.dumps(tool.input_schema),
            output_schema=json.dumps(tool.output_schema),
            code=tool.code,
        )

        record = await result.single()
        if record:
            tool_node = record["t"]
            schema_node = record["s"]
            logger.info(f"Tool updated successfully: {tool_node['name']}")
            return ToolResponse(
                id=str(tool_node.id),
                name=tool_node["name"],
                description=tool_node["description"],
                input_schema=json.loads(schema_node["input_schema"]),
                output_schema=json.loads(schema_node["output_schema"]),
            )
        else:
            logger.warning(f"Tool not found for update with id: {tool_id}")
            raise HTTPException(status_code=404, detail="Tool not found")

    @app.delete("/tools/{tool_id}")
    async def delete_tool(tool_id: str, session=Depends(get_session)):
        logger.info(f"Deleting tool with id: {tool_id}")
        result = await session.run(
            """
            MATCH (t:Tool)-[:HAS_SCHEMA]->(s:ToolSchema)
            WHERE ID(t) = $tool_id
            OPTIONAL MATCH (t)-[:HAS_CODE]->(c:ToolCode)
            DETACH DELETE t, s, c
            """,
            tool_id=int(tool_id),
        )
        if result.consume().counters.nodes_deleted > 0:
            logger.info(f"Tool deleted successfully: {tool_id}")
            return {"message": "Tool deleted successfully"}
        else:
            logger.warning(f"Tool not found for deletion with id: {tool_id}")
            raise HTTPException(status_code=404, detail="Tool not found")

    @app.post("/execute_tool", response_model=ToolExecutionResponse)
    async def execute_single_tool(request: ToolExecutionRequest, session=Depends(get_session)):
        logger.info(f"Received request to execute tool: {request.tool_id}")
        logger.debug(f"Input data: {request.input_data}")
        try:
            output_data = await execute_tool(request.tool_id, request.input_data, session)
            return ToolExecutionResponse(tool_id=request.tool_id, output_data=output_data)
        except HTTPException as he:
            logger.error(f"HTTP error while executing tool {request.tool_id}: {str(he)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while executing tool {request.tool_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    @app.post("/execute_tools_sequential", response_model=List[ToolExecutionResponse])
    async def execute_tools_sequential(request: SequentialToolExecutionRequest, session=Depends(get_session)):
        logger.info(f"Executing tools sequentially: {request.tool_ids}")
        current_input = request.initial_input
        results = []
        for idx, tool_id in enumerate(request.tool_ids, start=1):
            logger.info(f"[{idx}/{len(request.tool_ids)}] Executing tool {tool_id}")
            try:
                output_data = await execute_tool(tool_id, current_input, session)
                results.append(ToolExecutionResponse(tool_id=tool_id, output_data=output_data))
                current_input = output_data  # Pass output as input to next tool
            except HTTPException as e:
                logger.error(f"Error executing tool {tool_id} in sequence: {str(e)}")
                raise HTTPException(status_code=e.status_code, detail=f"Error at tool {tool_id}: {e.detail}")
            except Exception as e:
                logger.error(f"Unexpected error executing tool {tool_id}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Unexpected error at tool {tool_id}: {str(e)}")

        return results

    @app.post("/execute_tools_parallel", response_model=List[ToolExecutionResponse])
    async def execute_tools_parallel(request: ParallelToolExecutionRequest, session=Depends(get_session)):
        logger.info(f"Executing tools in parallel: {request.tool_ids}")
        tasks = []
        for tool_id in request.tool_ids:
            in_data = request.input_data.get(tool_id, {})
            tasks.append(execute_tool(tool_id, in_data, session))

        try:
            results = await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error during parallel execution: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error during parallel execution: {str(e)}")

        # Bundle results
        responses = []
        for tid, output_data in zip(request.tool_ids, results):
            responses.append(ToolExecutionResponse(tool_id=tid, output_data=output_data))
        return responses

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        logger.error(f"HTTP exception: {exc.detail}")
        return {"detail": exc.detail}, exc.status_code

    return app
