#  """
# FastAPI Backend for No-Code SQL Frontend with MCP Integration
# Architecture:
# 1. React Frontend → /api/copilotkit (CopilotKit SDK)
# 2. FastAPI receives query and sends to Azure OpenAI (GPT-4.5)
# 3. Azure OpenAI responds with tool calls
# 4. FastAPI forwards tool calls to MCP Server via SSE
# 5. MCP Server connects to PostgreSQL and returns data
# 6. FastAPI streams response back to React Frontend

import logging
import json
import os
import re
import httpx
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Local imports
from config import get_settings
from mcp_client import (
    initialize_mcp_client,
    close_mcp_client,
    get_mcp_client,
    get_connection_details,
    set_connection_details,
    _normalize_tool_input,
    _format_result_as_text,
)
from db_utils import DatabaseConnection, DatabaseOperations
from guardrails.policy_engine import check_request


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Settings ---
settings = get_settings()

# --- Pydantic Models ---
class ConnectionDetails(BaseModel):
    host: str
    port: int
    user: str
    password: str
    database: str = "postgres"
    ssl: bool = False


class ToolCall(BaseModel):
    name: str
    input: Dict[str, Any]


class ToolExecutionRequest(BaseModel):
    tools: List[ToolCall]


class DBConnectRequest(BaseModel):
    host: str
    port: int
    user: str
    password: str
    database: str
    ssl: bool = False


class PreviewRequest(BaseModel):
    host: str
    port: int
    user: str
    password: str
    database: str
    ssl: bool = False
    table: str


class CopilotChatRequest(BaseModel):
    messages: Optional[List[Dict[str, str]]] = None
    message: Optional[str] = None
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


def _extract_chat_messages(request: CopilotChatRequest) -> tuple[str, List[Dict[str, str]]]:
    """Return the latest user message and full user/assistant history for the LLM."""
    if request.messages:
        history: List[Dict[str, str]] = []
        for msg in request.messages:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and content:
                history.append({"role": role, "content": content})

        user_messages = [m["content"] for m in history if m["role"] == "user"]
        if user_messages:
            return user_messages[-1], history

        if request.messages:
            fallback = request.messages[-1].get("content", "")
            if fallback:
                return fallback, [{"role": "user", "content": fallback}]

    if request.message:
        return request.message, [{"role": "user", "content": request.message}]

    raise HTTPException(status_code=400, detail="No message provided")


# --- Global State ---
mcp_connected: bool = False


# --- Lifecycle Events ---
async def lifespan(app: FastAPI):
    """
    Manage FastAPI application lifecycle.
    Initialize MCP client on startup, close on shutdown.
    """
    # Startup
    global mcp_connected
    logger.info("Starting FastAPI application...")
    
    try:
        # Initialize MCP client connection
        mcp_server_url = f"http://127.0.0.1:8001"
        mcp_connected = await initialize_mcp_client(mcp_server_url)
        
        if mcp_connected:
            logger.info(f"✓ Connected to MCP server at {mcp_server_url}")
        else:
            logger.warning(f"✗ Could not connect to MCP server at {mcp_server_url}")
            logger.info("Make sure MCP server is running: python mcp_server/run.py")
    
    except Exception as e:
        logger.error(f"Error during startup: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI application...")
    try:
        await close_mcp_client()
        logger.info("Closed MCP client connection")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# --- FastAPI App ---
app = FastAPI(
    title="No-Code SQL Backend with MCP",
    description="FastAPI backend for SQL database operations with proper MCP integration",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Log registered routes to help debug missing endpoints
def _log_routes():
    try:
        logger.info("Registered FastAPI routes:")
        for r in app.routes:
            try:
                methods = getattr(r, 'methods', None)
                path = getattr(r, 'path', getattr(r, 'url', ''))
                logger.info(f"  {methods} {path} (name={r.name})")
            except Exception:
                logger.info(f"  {r}")
    except Exception as e:
        logger.warning(f"Could not log routes: {e}")

# Call once at import time to show current route registration
_log_routes()


# --- Connection Management ---
def _connection_from_details() -> DatabaseConnection:
    details = get_connection_details()
    ssl_value = details.get("ssl", False)
    if isinstance(ssl_value, str):
        ssl_value = ssl_value.lower() in ("true", "1", "yes")
    return DatabaseConnection(
        host=details["host"],
        port=int(details["port"]),
        user=details["user"],
        password=details["password"],
        database=details["database"],
        ssl=bool(ssl_value),
    )


async def _load_schema_context() -> str:
    """Load table/column names from the connected database for LLM grounding."""
    try:
        db_conn = _connection_from_details()
        db_ops = DatabaseOperations(db_conn)
        database = db_conn.database
        tables = await db_ops.list_tables(database)
        if not tables:
            return f"Connected database: {database}\nNo public tables found."

        lines = [
            f"Connected database: {database}",
            "Available tables and columns (use these EXACT names in SQL):",
        ]
        for table in tables:
            schema = await db_ops.get_table_schema(database, table)
            cols = ", ".join(schema.keys())
            lines.append(f"  - {table}: {cols}")
        lines.append(
            "Important: Do not invent table names (e.g. departments, employees). "
            "Use only the table and column names listed above."
        )
        return "\n".join(lines)
    except Exception as e:
        logger.warning("Could not load schema context: %s", e)
        details = get_connection_details()
        return f"Connected database: {details['database']} (schema unavailable: {e})"


async def ensure_mcp_connected():
    """Ensure MCP server is connected - check dynamically"""
    try:
        mcp_client = await get_mcp_client()
        if not mcp_client:
            raise HTTPException(
                status_code=503,
                detail="MCP server not connected. Please start MCP server: python mcp_server/run.py"
            )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail="MCP server not connected. Please start MCP server: python mcp_server/run.py"
        )


# --- REST Endpoints ---

@app.post("/api/connect")
async def connect_db(details: ConnectionDetails):
    """
    Configuration endpoint - validates PostgreSQL credentials and stores them in state.
    MCP server uses these environment variables.
    """
    await ensure_mcp_connected()
    
    try:
        logger.info(f"Connection info received for {details.database} at {details.host}:{details.port}")
        db_conn = DatabaseConnection(
            host=details.host,
            port=details.port,
            user=details.user,
            password=details.password,
            database=details.database,
            ssl=details.ssl
        )

        if not await db_conn.test_connection():
            raise HTTPException(
                status_code=400,
                detail="Invalid PostgreSQL credentials or unable to connect to the database"
            )

        set_connection_details(details.dict())
        
        return {
            "status": "configured",
            "message": "PostgreSQL connection configured and verified",
            "host": details.host,
            "database": details.database,
            "note": "Connection successful. You can now load tables."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Connection error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Configuration failed: {str(e)}")


@app.post("/api/db-tables")
async def get_db_tables(request: DBConnectRequest):
    """
    Connects to the given database and returns a list of table names.
    Used by frontend before CopilotKit cycle starts.
    """
    try:
        logger.info(f"Attempting to connect to {request.host}:{request.port}/{request.database} as user {request.user}")
        db_conn = DatabaseConnection(
            host=request.host,
            port=request.port,
            user=request.user,
            password=request.password,
            database=request.database,
            ssl=request.ssl
        )
        db_ops = DatabaseOperations(db_conn)
        tables = await db_ops.list_tables(request.database)
        logger.info(f"Successfully retrieved {len(tables)} tables from {request.database}")
        return {"status": "success", "tables": tables}
    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}"
        full_traceback = traceback.format_exc()
        logger.error(f"Database connection error: {error_msg}\n{full_traceback}")
        raise HTTPException(status_code=400, detail=f"DB connection failed: {error_msg}")


@app.get("/api/tools")
async def get_available_tools():
    """
    Get list of available tools from MCP server.
    These tools are discovered via MCP protocol.
    """
    await ensure_mcp_connected()
    
    try:
        mcp_client = await get_mcp_client()
        tools = await mcp_client.get_tools()
        
        if not tools:
            raise HTTPException(
                status_code=503,
                detail="Could not retrieve tools from MCP server"
            )
        
        return {
            "status": "success",
            "tools": tools,
            "count": len(tools),
            "source": "MCP Server"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tools: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/execute-tool")
async def execute_tool_sse(request: ToolCall):
    """
    Execute a single tool via MCP Server using SSE.
    Streams execution progress back to client.
    """
    await ensure_mcp_connected()
    
    tool_name = request.name
    tool_input = request.input
    
    logger.info(f"Executing tool: {tool_name} with input: {tool_input}")
    
    mcp_client = await get_mcp_client()
    
    # Stream tool execution
    async def generate():
        async for event in mcp_client.call_tool_streaming(tool_name, tool_input):
            yield f"data: {event}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/execute-tools")
async def execute_tools_batch(request: ToolExecutionRequest):
    """
    Execute multiple tools via MCP Server in sequence.
    """
    await ensure_mcp_connected()
    
    mcp_client = await get_mcp_client()
    
    # Stream batch execution
    async def generate():
        for tool_call in request.tools:
            async for event in mcp_client.call_tool_streaming(tool_call.name, tool_call.input):
                yield f"data: {event}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/structure")
async def get_database_structure():
    """
    Get database structure (databases and tables).
    Calls MCP server's list_databases and list_tables tools.
    """
    await ensure_mcp_connected()
    
    try:
        mcp_client = await get_mcp_client()
        
        # Get list of databases
        databases_result = await mcp_client.call_tool("list_databases", {})
        databases = [db.strip() for db in databases_result.split("\n") if db.strip()]
        
        structure = []
        
        # For each database, get its tables
        for db_name in databases:
            try:
                tables_result = await mcp_client.call_tool("list_tables", {"database": db_name})
                tables = [table.strip() for table in tables_result.split("\n") if table.strip()]
                
                structure.append({
                    "name": db_name,
                    "type": "database",
                    "children": [{"name": table, "type": "table"} for table in tables]
                })
            except Exception as e:
                logger.warning(f"Could not list tables in {db_name}: {e}")
                structure.append({
                    "name": db_name,
                    "type": "database",
                    "children": []
                })
        
        return {
            "status": "success",
            "structure": structure
        }
    
    except Exception as e:
        logger.error(f"Error getting structure: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class PreviewRequest(BaseModel):
    host: str
    port: int
    user: str
    password: str
    database: str
    ssl: bool = False
    table: str


@app.post("/api/preview")
async def preview_table(request: PreviewRequest):
    """
    Preview table data directly from PostgreSQL.
    """
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", request.table):
        raise HTTPException(status_code=400, detail="Invalid table name")

    try:
        db_conn = DatabaseConnection(
            host=request.host,
            port=request.port,
            user=request.user,
            password=request.password,
            database=request.database,
            ssl=request.ssl
        )
        db_ops = DatabaseOperations(db_conn)
        rows = await db_ops.execute_query(request.database, f'SELECT * FROM "{request.table}" LIMIT 10')

        return {
            "status": "success",
            "data": rows,
            "count": len(rows)
        }
    except Exception as e:
        logger.error(f"Error previewing table: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/schema/{database}/{table}")
async def get_table_schema_endpoint(database: str, table: str):
    """
    Get schema for a specific table using MCP server.
    """
    await ensure_mcp_connected()
    
    try:
        mcp_client = await get_mcp_client()
        schema_result = await mcp_client.call_tool(
            "get_table_schema",
            {"database": database, "table_name": table}
        )
        
        # Parse schema result
        schema = {}
        for line in schema_result.split("\n"):
            if ": " in line:
                col_name, col_type = line.split(": ", 1)
                schema[col_name.strip()] = col_type.strip()
        
        return {
            "status": "success",
            "database": database,
            "table": table,
            "schema": schema
        }
    
    except Exception as e:
        logger.error(f"Error getting schema: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/copilotkit")
async def copilotkit_chat(request: CopilotChatRequest):
    """
    Main chat endpoint for CopilotKit frontend. Supports Azure OpenAI, OpenAI, and Groq APIs.
    Streams LLM output and routes tool calls to the MCP engine.
    """
    # Use the latest user message (not the first) and pass full chat history to Groq
    user_message, chat_history = _extract_chat_messages(request)
    logger.info("Processing latest user message: %s", user_message)

    # Guardrails: block before any tool execution / LLM processing
    decision = check_request(user_prompt=user_message)
    if not decision.allowed:
        # Do not leak internal details; still required by spec
        raise HTTPException(
            status_code=403,
            detail={"status": "blocked", "reason": "Violates organizational security policy."},
        )

    session_id = request.session_id or "default"
    context = request.context or {}


    connected_db = get_connection_details()["database"]
    schema_context = await _load_schema_context()

    system_message = {
        "role": "system",
        "content": (
            "You are a helpful SQL assistant for PostgreSQL. "
            "Use tool calls for all database reads. "
            "Answer each new user question independently using a fresh SQL query.\n\n"
            f"{schema_context}\n\n"
            f"Always pass database='{connected_db}' in execute_query calls. "
            "Write SQL using only the exact table and column names listed above."
        ),
    }

    # Build messages for LLM: system prompt + full conversation history
    messages = [system_message, *chat_history]

    # Base payload
    payload = {
        "messages": messages,
        "stream": True,
    }

    # Tools configuration (for OpenAI/Azure)
    # NOTE: MCP server tool name is `execute_query`, not `execute_sql_query`.
    # Keep LLM tool interface compatible with existing logic by exposing the MCP name.
    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_tables",
                "description": "List all tables in the connected PostgreSQL database.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string", "description": "Database name"}
                    },
                    "required": ["database"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_table_schema",
                "description": "Get column names and types for a table.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string", "description": "Database name"},
                        "table_name": {"type": "string", "description": "Table name"}
                    },
                    "required": ["database", "table_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "execute_query",
                "description": (
                    "Execute a SQL SELECT query. Use EXACT table and column names "
                    "from the schema in the system message (e.g. department.DEPT_ID, employee.EMAIL)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string", "description": "Database name"},
                        "query": {"type": "string", "description": "SQL SELECT query"}
                    },
                    "required": ["database", "query"]
                }
            }
        }
    ]

    # Force Groq usage everywhere
    if not getattr(settings, "groq_api_key", ""):
        raise HTTPException(status_code=500, detail="No GROQ_API_KEY configured")

    llm_url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"}

    # Groq follows OpenAI-compatible schema; keep tools enabled.
    send_payload = {**payload, "model": settings.groq_model, "tools": tools}

    def _openai_sse_chunk(content: str = "", finish_reason: Optional[str] = None) -> str:
        """Emit a CopilotKit-compatible OpenAI chat completion chunk."""
        choice: Dict[str, Any] = {"index": 0, "delta": {}}
        if content:
            choice["delta"]["content"] = content
        if finish_reason:
            choice["finish_reason"] = finish_reason
        return f"data: {json.dumps({'choices': [choice]})}\n\n"

    async def chat_stream():
        pending_tool_calls: Dict[int, Dict[str, Any]] = {}
        tools_executed = False

        async def execute_pending_tool_calls():
            nonlocal tools_executed
            if tools_executed or not pending_tool_calls:
                return
            tools_executed = True
            for idx in sorted(pending_tool_calls.keys()):
                tool_call = pending_tool_calls[idx]
                function = tool_call.get("function") or {}
                if isinstance(function, str):
                    try:
                        function = json.loads(function)
                    except Exception:
                        function = {"name": function, "arguments": ""}
                if not isinstance(function, dict):
                    continue

                tool_name = function.get("name")
                if not tool_name:
                    continue

                raw_args = function.get("arguments", "")
                if isinstance(raw_args, dict):
                    tool_args = raw_args
                else:
                    tool_args = _normalize_tool_input(raw_args or {})

                mcp_client = await get_mcp_client()
                result = await mcp_client.call_tool(tool_name, tool_args)
                if isinstance(result, str):
                    text = result
                else:
                    text = _format_result_as_text(result)
                yield _openai_sse_chunk(text)
            pending_tool_calls.clear()
            yield _openai_sse_chunk(finish_reason="stop")
            yield "data: [DONE]\n\n"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", llm_url, headers=headers, json=send_payload) as resp:
                    if resp.status_code != 200:
                        error_text = await resp.aread()
                        logger.error(f"LLM API Error {resp.status_code}: {error_text}")
                        yield _openai_sse_chunk(f"API Error: {resp.status_code}", finish_reason="stop")
                        yield "data: [DONE]\n\n"
                        return

                    async for line in resp.aiter_lines():
                        if not line:
                            continue

                        if line.startswith("data: "):
                            data = line[6:]
                        else:
                            data = line

                        if data.strip() == "[DONE]":
                            async for event in execute_pending_tool_calls():
                                yield event
                            if not tools_executed:
                                yield "data: [DONE]\n\n"
                            break

                        try:
                            chunk = json.loads(data)
                        except Exception as e:
                            logger.debug(f"Failed to parse JSON: {e}")
                            continue

                        choices = chunk.get("choices", [])
                        if not choices:
                            continue

                        for choice in choices:
                            delta = choice.get("delta", {}) or {}
                            finish_reason = choice.get("finish_reason")

                            if delta.get("tool_calls"):
                                for tool_call in delta["tool_calls"]:
                                    idx = tool_call.get("index", 0)
                                    if idx not in pending_tool_calls:
                                        pending_tool_calls[idx] = {
                                            "id": tool_call.get("id"),
                                            "function": {"name": "", "arguments": ""},
                                        }

                                    if tool_call.get("id"):
                                        pending_tool_calls[idx]["id"] = tool_call["id"]

                                    function = tool_call.get("function") or {}
                                    if isinstance(function, str):
                                        try:
                                            function = json.loads(function)
                                        except Exception:
                                            function = {"name": function, "arguments": ""}
                                    if not isinstance(function, dict):
                                        function = {}

                                    if function.get("name"):
                                        pending_tool_calls[idx]["function"]["name"] = function["name"]
                                    if function.get("arguments") is not None:
                                        pending_tool_calls[idx]["function"]["arguments"] += function["arguments"]
                                continue

                            if finish_reason == "tool_calls":
                                async for event in execute_pending_tool_calls():
                                    yield event
                                return

                            if delta.get("content"):
                                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield _openai_sse_chunk(f"Stream error: {e}", finish_reason="stop")
            yield "data: [DONE]\n\n"

    return StreamingResponse(chat_stream(), media_type="text/event-stream")


@app.get("/api/mcp-status")
async def mcp_status():
    """
    Check MCP server status and connection.
    """
    try:
        mcp_client = await get_mcp_client()
        is_connected = await mcp_client.is_connected()
        
        tools = []
        if is_connected:
            tools = await mcp_client.get_tools()
        
        return {
            "status": "connected" if is_connected else "disconnected",
            "mcp_server": "http://localhost:8001",
            "tools_available": len(tools),
            "mcp_enabled": True
        }
    
    except Exception as e:
        logger.error(f"Error checking MCP status: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "mcp_enabled": True
        }


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint.
    """
    try:
        mcp_client = await get_mcp_client()
        is_connected = await mcp_client.is_connected()
        
        return {
            "status": "healthy" if is_connected else "degraded",
            "fastapi_connected": True,
            "mcp_connected": is_connected
        }
    
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.get("/")
async def root():
    """
    Root endpoint with API documentation.
    """
    return {
        "name": "No-Code SQL Backend (MCP v2)",
        "version": "2.0.0",
        "architecture": "FastAPI + MCP Server",
        "mcp_server_running": mcp_connected,
        "endpoints": {
            "health": "GET /api/health",
            "mcp_status": "GET /api/mcp-status",
            "connect": "POST /api/connect",
            "get_tools": "GET /api/tools",
            "execute_tool": "POST /api/execute-tool",
            "execute_tools": "POST /api/execute-tools",
            "get_structure": "GET /api/structure",
            "preview_table": "POST /api/preview",
            "get_schema": "GET /api/schema/{database}/{table}",
            "copilotkit": "POST /api/copilotkit"
        },
        "note": "Ensure MCP server is running: python mcp_server/run.py"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.fastapi_host,
        port=settings.fastapi_port,
        reload=settings.fastapi_reload
    )