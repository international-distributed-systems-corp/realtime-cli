import os
import json
import logging
import asyncio
import httpx
import uuid
from typing import Dict, Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from modal import Image, App, Secret, asgi_app

# Try to import Neo4j
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    print("Warning: Neo4j driver not installed. Some functionality may be limited.")
    NEO4J_AVAILABLE = False
    GraphDatabase = None

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
        "python-dotenv",
        "httpx"
    ])
    .apt_install(["python3-dev", "gcc"])
)

# Create Modal app
app = App(TOOL_MGMT_APP_LABEL)

# Logging setup
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# Create FastAPI app
web_app = FastAPI(title="Tool Management API", version="1.0.0")

# Add CORS middleware
web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class JavaScriptCode(BaseModel):
    code: str
    function_name: str

class PythonCode(BaseModel):
    code: str
    function_name: str

class HTTPAction(BaseModel):
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
    url: str
    headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None

class ToolAction(BaseModel):
    type: Literal["javascript", "http", "python"]
    javascript: Optional[JavaScriptCode] = None
    http: Optional[HTTPAction] = None
    python: Optional[PythonCode] = None

class ToolOutput(BaseModel):
    type: Literal["ai", "markdown", "html"]
    content: str

class UserSetting(BaseModel):
    name: str
    label: str
    type: str = "text"
    description: Optional[str] = None
    required: bool = False
    placeholder: Optional[str] = None
    values: Optional[List[str]] = None

class Tool(BaseModel):
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    code: Optional[str] = None
    action: Optional[ToolAction] = None
    output: Optional[ToolOutput] = None
    user_settings: Optional[List[UserSetting]] = None
    runtime: Optional[Literal["python", "javascript"]] = None
    is_adhoc: Optional[bool] = False
    created_by: Optional[str] = "user"
    agent_id: Optional[str] = None
    validation_status: Optional[Literal["pending", "approved", "rejected"]] = "pending"

class ToolResponse(BaseModel):
    id: str
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    action: Optional[ToolAction] = None
    output: Optional[ToolOutput] = None
    version: Optional[str] = None

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
        self.driver = None
        if not NEO4J_AVAILABLE:
            logger.warning("Neo4j driver not installed; functionalities are disabled.")
            return

        uri = "neo4j://bolt.n4j.distributed.systems"
        print(uri)
        user_ = os.getenv("NEO4J_USERNAME")

        pass_ = os.getenv("NEO4J_PASSWORD")
        print(user_)
        print(pass_)

        try:
            self.driver = GraphDatabase.driver(uri, auth=(user_, pass_))
            self.driver.verify_connectivity()
            logger.info("Neo4j connection established successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise

    async def close(self):
        if NEO4J_AVAILABLE and self.driver is not None:
            self.driver.close()

    async def get_session(self):
        if NEO4J_AVAILABLE and self.driver is not None:
            return self.driver.session()
        return None

async def get_db():
    """Yields a new Neo4j connection; auto-closed after request."""
    db = Neo4jConnection()
    try:
        yield db
    finally:
        await db.close()

async def get_session(db: Neo4jConnection = Depends(get_db)):
    """Yields a Neo4j session; closed after request."""
    session = await db.get_session()
    if session is None:
        raise HTTPException(status_code=500, detail="Neo4j session unavailable.")
    try:
        yield session
    finally:
        session.close()

# Root and health endpoints
@web_app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to the Tool Management API"}

@web_app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
# Utility functions
async def safe_exec_python(python_code: str, input_data: dict, libraries: List[str] = None) -> Dict[str, Any]:
    """Safely executes Python code in a Modal container."""
    logger.info("Creating Modal container for Python code execution")
    
    # Create stub function to run code
    @modal.function(
        image=image.pip_install(*libraries) if libraries else image,
        secret=Secret.from_name(NEO4J_SECRET_NAME)
    )
    def run_code(code: str, data: dict) -> dict:
        # Set up environment
        globals_dict = {
            'input_data': data,
            'output_data': {}
        }
        
        # Execute code with input data
        exec(code, globals_dict)
        
        return globals_dict['output_data']

    try:
        # Execute code in Modal container
        result = await run_code.aio(python_code, input_data)
        return result
        
    except Exception as e:
        raise RuntimeError(f"Error executing Python code in Modal container: {str(e)}")

async def execute_tool_in_neo4j(tool_id: str, input_data: Dict[str, Any], session) -> Dict[str, Any]:
    """Execute tool by looking up details in Neo4j."""
    logger.info(f"Executing tool with id: {tool_id}")
    result = session.run(
        """
        MATCH (t:Tool {id: $tool_id})
        OPTIONAL MATCH (t)-[:HAS_SCHEMA]->(s:ToolSchema)
        OPTIONAL MATCH (t)-[:HAS_ACTION]->(a:ToolAction)
        OPTIONAL MATCH (t)-[:HAS_OUTPUT]->(o:ToolOutput)
        OPTIONAL MATCH (t)-[:HAS_CODE]->(c:ToolCode)
        RETURN t, s, a, o, c
        """,
        tool_id=tool_id
    )
    record = result.single()
    if not record:
        logger.warning(f"Tool not found in Neo4j for id: {tool_id}")
        raise HTTPException(status_code=404, detail="Tool not found")

    tool_node = record["t"]
    action_node = record["a"]
    code_node = record["c"]

    if not action_node:
        if not code_node:
            raise HTTPException(status_code=400, detail="No code/action found for this tool.")
        code_text = code_node["code"]
        try:
            out = safe_exec_python(code_text, input_data)
            return out
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

    action_type = action_node["type"]
    logger.info(f"Tool action type: {action_type}")

    if action_type == "python":
        if code_node and "code" in code_node:
            code_text = code_node["code"]
            try:
                return safe_exec_python(code_text, input_data)
            except RuntimeError as e:
                raise HTTPException(status_code=500, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail="Missing Python code for this tool.")

    elif action_type == "http":
        http_data = action_node.get("http", None)
        if not http_data:
            raise HTTPException(status_code=400, detail="No HTTP config found for this tool.")
        http_json = json.loads(http_data)
        method = http_json["method"].lower()
        url = _replace_params(http_json["url"], input_data)
        headers = {
            k: _replace_params(v, input_data)
            for k, v in http_json.get("headers", {}).items()
        }
        body = input_data

        logger.info(f"Performing HTTP request: {method.upper()} {url}")
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                r = await client.request(method, url, headers=headers, json=body)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError as e:
                logger.error(f"HTTP error during tool execution: {str(e)}")
                raise HTTPException(status_code=500, detail=f"HTTP Error: {str(e)}")

    elif action_type == "javascript":
        raise HTTPException(status_code=501, detail="JavaScript execution not implemented.")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action type: {action_type}")

def _replace_params(template: str, params: Dict[str, Any]) -> str:
    """Replace {key} placeholders in template string."""
    for k, v in params.items():
        template = template.replace(f"{{{k}}}", str(v))
    return template

# CRUD endpoints
@web_app.post("/tools", response_model=ToolResponse)
async def create_tool(tool: Tool, session=Depends(get_session)):
    """Create a new tool."""
    logger.info(f"Creating new tool: {tool.name}")
    tool_id = str(uuid.uuid4())

    if tool.created_by == "agent":
        tool.validation_status = "pending"
    else:
        tool.validation_status = "approved"

    # Create Tool node
    result = session.run(
        """
        CREATE (t:Tool {
            id: $id,
            name: $name,
            description: $desc,
            created_by: $created_by,
            agent_id: $agent_id,
            validation_status: $vstatus,
            is_adhoc: $is_adhoc,
            runtime: $runtime
        })
        RETURN t
        """,
        id=tool_id,
        name=tool.name,
        desc=tool.description,
        created_by=tool.created_by,
        agent_id=tool.agent_id,
        vstatus=tool.validation_status,
        is_adhoc=tool.is_adhoc,
        runtime=tool.runtime
    )
    record = result.single()
    if not record:
        logger.error(f"Failed to create tool node for {tool.name}")
        raise HTTPException(status_code=500, detail="Failed to create tool")

    # Create ToolSchema node
    schema_id = str(uuid.uuid4())
    session.run(
        """
        MATCH (t:Tool {id: $tid})
        CREATE (s:ToolSchema {
            id: $sid,
            input_schema: $ischema,
            output_schema: $oschema
        })
        CREATE (t)-[:HAS_SCHEMA]->(s)
        """,
        tid=tool_id,
        sid=schema_id,
        ischema=json.dumps(tool.input_schema),
        oschema=json.dumps(tool.output_schema)
    )

    # Create ToolAction node if provided
    if tool.action:
        action_id = str(uuid.uuid4())
        action_json = {
            "type": tool.action.type,
            "javascript": json.dumps(tool.action.javascript.dict())
                          if tool.action.javascript else None,
            "http": json.dumps(tool.action.http.dict())
                          if tool.action.http else None,
            "python": json.dumps(tool.action.python.dict())
                          if tool.action.python else None,
        }
        session.run(
            """
            MATCH (t:Tool {id: $tid})
            CREATE (a:ToolAction {
                id: $aid,
                type: $type,
                javascript: $js,
                http: $http,
                python: $py
            })
            CREATE (t)-[:HAS_ACTION]->(a)
            """,
            tid=tool_id,
            aid=action_id,
            type=action_json["type"],
            js=action_json["javascript"],
            http=action_json["http"],
            py=action_json["python"]
        )

    # Create ToolOutput node if provided
    if tool.output:
        output_id = str(uuid.uuid4())
        session.run(
            """
            MATCH (t:Tool {id: $tid})
            CREATE (o:ToolOutput {
                id: $oid,
                type: $otype,
                content: $ocontent
            })
            CREATE (t)-[:HAS_OUTPUT]->(o)
            """,
            tid=tool_id,
            oid=output_id,
            otype=tool.output.type,
            ocontent=tool.output.content
        )

    # Create ToolCode node if code provided
    if tool.code:
        code_id = str(uuid.uuid4())
        session.run(
            """
            MATCH (t:Tool {id: $tid})
            CREATE (c:ToolCode {id: $cid, code: $code})
            CREATE (t)-[:HAS_CODE]->(c)
            """,
            tid=tool_id,
            cid=code_id,
            code=tool.code
        )

    response = ToolResponse(
        id=tool_id,
        name=tool.name,
        description=tool.description,
        input_schema=tool.input_schema,
        output_schema=tool.output_schema,
        action=tool.action,
        output=tool.output,
        version="1.0.0"
    )
    logger.info(f"Tool created successfully: {tool.name} (id={tool_id})")
    return response

@web_app.get("/tools", response_model=List[ToolResponse])
async def get_tools(session=Depends(get_session)):
    """Get all tools."""
    logger.info("Fetching all tools")
    result = session.run(
        """
        MATCH (t:Tool)
        OPTIONAL MATCH (t)-[:HAS_SCHEMA]->(s:ToolSchema)
        OPTIONAL MATCH (t)-[:HAS_ACTION]->(a:ToolAction)
        OPTIONAL MATCH (t)-[:HAS_OUTPUT]->(o:ToolOutput)
        RETURN t, s, a, o
        """
    )
    records = result.data()
    tools = []

    for record in records:
        t = record["t"]
        s = record.get("s")
        a = record.get("a")
        o = record.get("o")

        action_model = None
        if a:
            action_model = ToolAction(
                type=a["type"],
                javascript=(JavaScriptCode(**json.loads(a["javascript"]))
                            if a.get("javascript") else None),
                http=(HTTPAction(**json.loads(a["http"]))
                      if a.get("http") else None),
                python=(PythonCode(**json.loads(a["python"]))
                        if a.get("python") else None),
            )

        output_model = None
        if o:
            output_model = ToolOutput(
                type=o.get("type", "markdown"),
                content=o.get("content", "")
            )

        in_sch = {}
        out_sch = {}
        if s:
            in_sch = json.loads(s.get("input_schema", "{}"))
            out_sch = json.loads(s.get("output_schema", "{}"))

        tr = ToolResponse(
            id=t["id"],
            name=t["name"],
            description=t["description"],
            input_schema=in_sch,
            output_schema=out_sch,
            action=action_model,
            output=output_model,
            version=t.get("version", "1.0.0")
        )
        tools.append(tr)

    logger.info(f"Fetched {len(tools)} tools")
    return tools

@web_app.get("/tools/{tool_identifier}", response_model=ToolResponse)
async def get_tool(tool_identifier: str, session=Depends(get_session)):
    """Get a tool by ID or name."""
    logger.info(f"Fetching tool with identifier: {tool_identifier}")
    result = session.run(
        """
        MATCH (t:Tool)
        WHERE t.id = $identifier OR t.name = $identifier
        OPTIONAL MATCH (t)-[:HAS_SCHEMA]->(s:ToolSchema)
        OPTIONAL MATCH (t)-[:HAS_ACTION]->(a:ToolAction)
        OPTIONAL MATCH (t)-[:HAS_OUTPUT]->(o:ToolOutput)
        RETURN t, s, a, o
        """,
        identifier=tool_identifier
    )
    record = result.single()
    if not record:
        logger.warning(f"Tool not found with identifier: {tool_identifier}")
        raise HTTPException(status_code=404, detail="Tool not found")

    t = record["t"]
    s = record["s"]
    a = record["a"]
    o = record["o"]

    action_model = None
    if a:
        action_model = ToolAction(
            type=a["type"],
            javascript=(JavaScriptCode(**json.loads(a["javascript"]))
                        if a.get("javascript") else None),
            http=(HTTPAction(**json.loads(a["http"]))
                  if a.get("http") else None),
            python=(PythonCode(**json.loads(a["python"]))
                    if a.get("python") else None),
        )

    output_model = None
    if o:
        output_model = ToolOutput(
            type=o["type"],
            content=o["content"]
        )

    in_sch = {}
    out_sch = {}
    if s:
        in_sch = json.loads(s["input_schema"])
        out_sch = json.loads(s["output_schema"])

    return ToolResponse(
        id=t["id"],
        name=t["name"],
        description=t["description"],
        input_schema=in_sch,
        output_schema=out_sch,
        action=action_model,
        output=output_model,
        version=t.get("version", "1.0.0")
    )

@web_app.put("/tools/{tool_id}", response_model=ToolResponse)
async def update_tool(tool_id: str, tool: Tool, session=Depends(get_session)):
    """Update a tool."""
    logger.info(f"Updating tool with id: {tool_id}")

    check = session.run(
        "MATCH (t:Tool {id: $tid}) RETURN t",
        tid=tool_id
    ).single()
    if not check:
        logger.warning(f"Tool not found for update with id: {tool_id}")
        raise HTTPException(status_code=404, detail="Tool not found")

    # Update Tool node
    session.run(
        """
        MATCH (t:Tool {id: $tid})
        SET t.name = $name,
            t.description = $desc,
            t.is_adhoc = $is_adhoc,
            t.runtime = $runtime,
            t.validation_status = $vstatus
        """,
        tid=tool_id,
        name=tool.name,
        desc=tool.description,
        is_adhoc=tool.is_adhoc,
        runtime=tool.runtime,
        vstatus=tool.validation_status
    )

    # Update schema
    session.run(
        """
        MATCH (t:Tool {id: $tid})-[:HAS_SCHEMA]->(s:ToolSchema)
        SET s.input_schema = $ischema, s.output_schema = $oschema
        """,
        tid=tool_id,
        ischema=json.dumps(tool.input_schema),
        oschema=json.dumps(tool.output_schema)
    )

    # Update action if provided
    if tool.action:
        action_check = session.run(
            """
            MATCH (t:Tool {id: $tid})-[:HAS_ACTION]->(a:ToolAction)
            RETURN a
            """, tid=tool_id
        ).single()
        if action_check:
            session.run(
                """
                MATCH (t:Tool {id: $tid})-[:HAS_ACTION]->(a:ToolAction)
                SET a.type = $type,
                    a.javascript = $js,
                    a.http = $http,
                    a.python = $py
                """,
                tid=tool_id,
                type=tool.action.type,
                js=(json.dumps(tool.action.javascript.dict())
                    if tool.action.javascript else None),
                http=(json.dumps(tool.action.http.dict())
                      if tool.action.http else None),
                py=(json.dumps(tool.action.python.dict())
                    if tool.action.python else None),
            )
        else:
            session.run(
                """
                MATCH (t:Tool {id: $tid})
                CREATE (a:ToolAction {
                    id: $aid,
                    type: $type,
                    javascript: $js,
                    http: $http,
                    python: $py
                })
                CREATE (t)-[:HAS_ACTION]->(a)
                """,
                tid=tool_id,
                aid=str(uuid.uuid4()),
                type=tool.action.type,
                js=(json.dumps(tool.action.javascript.dict())
                    if tool.action.javascript else None),
                http=(json.dumps(tool.action.http.dict())
                      if tool.action.http else None),
                py=(json.dumps(tool.action.python.dict())
                    if tool.action.python else None),
            )

    # Update output if provided
    if tool.output:
        out_check = session.run(
            """
            MATCH (t:Tool {id: $tid})-[:HAS_OUTPUT]->(o:ToolOutput)
            RETURN o
            """, tid=tool_id
        ).single()
        if out_check:
            session.run(
                """
                MATCH (t:Tool {id: $tid})-[:HAS_OUTPUT]->(o:ToolOutput)
                SET o.type = $otype,
                    o.content = $ocontent
                """,
                tid=tool_id,
                otype=tool.output.type,
                ocontent=tool.output.content
            )
        else:
            session.run(
                """
                MATCH (t:Tool {id: $tid})
                CREATE (o:ToolOutput {
                    id: $oid,
                    type: $otype,
                    content: $ocontent
                })
                CREATE (t)-[:HAS_OUTPUT]->(o)
                """,
                tid=tool_id,
                oid=str(uuid.uuid4()),
                otype=tool.output.type,
                ocontent=tool.output.content
            )

    # Update code if provided
    if tool.code:
        code_check = session.run(
            """
            MATCH (t:Tool {id: $tid})-[:HAS_CODE]->(c:ToolCode)
            RETURN c
            """, tid=tool_id
        ).single()
        if code_check:
            session.run(
                """
                MATCH (t:Tool {id: $tid})-[:HAS_CODE]->(c:ToolCode)
                SET c.code = $code
                """,
                tid=tool_id,
                code=tool.code
            )
        else:
            session.run(
                """
                MATCH (t:Tool {id: $tid})
                CREATE (c:ToolCode {id: $cid, code: $code})
                CREATE (t)-[:HAS_CODE]->(c)
                """,
                tid=tool_id,
                cid=str(uuid.uuid4()),
                code=tool.code
            )

    return await get_tool(tool_id, session)

@web_app.delete("/tools/{tool_id}")
async def delete_tool(tool_id: str, session=Depends(get_session)):
    """Delete a tool."""
    logger.info(f"Deleting tool with id: {tool_id}")
    result = session.run(
        """
        MATCH (t:Tool {id: $tid})
        OPTIONAL MATCH (t)-[:HAS_SCHEMA]->(s:ToolSchema)
        OPTIONAL MATCH (t)-[:HAS_ACTION]->(a:ToolAction)
        OPTIONAL MATCH (t)-[:HAS_OUTPUT]->(o:ToolOutput)
        OPTIONAL MATCH (t)-[:HAS_CODE]->(c:ToolCode)
        DETACH DELETE t, s, a, o, c
        RETURN count(*) AS deleted_count
        """,
        tid=tool_id
    ).single()
    count = result["deleted_count"] if result else 0
    if count > 0:
        logger.info(f"Tool deleted successfully: {tool_id}")
        return {"message": "Tool deleted successfully"}
    else:
        logger.warning(f"Tool not found for deletion with id: {tool_id}")
        raise HTTPException(status_code=404, detail="Tool not found")

# Execution endpoints
@web_app.post("/execute_tool", response_model=ToolExecutionResponse)
async def execute_single_tool(request: ToolExecutionRequest, session=Depends(get_session)):
    """Execute a single tool."""
    logger.info(f"Received request to execute tool: {request.tool_id}")
    logger.debug(f"Input data: {request.input_data}")

    try:
        output_data = await execute_tool_in_neo4j(
            tool_id=request.tool_id,
            input_data=request.input_data,
            session=session
        )
        return ToolExecutionResponse(
            tool_id=request.tool_id,
            output_data=output_data
        )
    except HTTPException as he:
        logger.error(f"HTTP error while executing tool {request.tool_id}: {str(he)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error while executing tool {request.tool_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

@web_app.post("/execute_tools_sequential", response_model=List[ToolExecutionResponse])
async def execute_tools_sequential(request: SequentialToolExecutionRequest, session=Depends(get_session)):
    """Execute tools sequentially."""
    logger.info(f"Executing tools sequentially: {request.tool_ids}")
    current_input = request.initial_input
    results = []

    for idx, tool_id in enumerate(request.tool_ids, start=1):
        logger.info(f"[{idx}/{len(request.tool_ids)}] Executing tool {tool_id}")
        try:
            output_data = await execute_tool_in_neo4j(tool_id, current_input, session)
            results.append(ToolExecutionResponse(tool_id=tool_id, output_data=output_data))
            current_input = output_data
        except HTTPException as e:
            logger.error(f"Error executing tool {tool_id} in sequence: {str(e)}")
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Error at tool {tool_id}: {e.detail}"
            )
        except Exception as e:
            logger.error(f"Unexpected error executing tool {tool_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected error at tool {tool_id}: {str(e)}"
            )

    return results

@web_app.post("/execute_tools_parallel", response_model=List[ToolExecutionResponse])
async def execute_tools_parallel(request: ParallelToolExecutionRequest, session=Depends(get_session)):
    """Execute tools in parallel."""
    logger.info(f"Executing tools in parallel: {request.tool_ids}")
    tasks = []

    for tool_id in request.tool_ids:
        in_data = request.input_data.get(tool_id, {})
        tasks.append(execute_tool_in_neo4j(tool_id, in_data, session))

    try:
        results = await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"Error during parallel execution: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error during parallel execution: {str(e)}")

    responses = []
    for tid, output_data in zip(request.tool_ids, results):
        responses.append(ToolExecutionResponse(tool_id=tid, output_data=output_data))
    return responses

# Exception handler
@web_app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP exception: {exc.detail}")
    return {"detail": exc.detail}, exc.status_code
