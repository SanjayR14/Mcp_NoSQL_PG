"""
MCP Client for FastAPI Backend
Communicates with the MCP Server via SSE (Server-Sent Events)
Handles tool discovery and execution through MCP protocol
"""

import ast
import asyncio
import json
import logging
import os
from typing import Dict, Any, Optional, List, AsyncGenerator
import httpx

from db_utils import DatabaseConnection, DatabaseOperations

logger = logging.getLogger(__name__)

_active_connection_details: Optional[Dict[str, Any]] = None


def _default_connection_details() -> Dict[str, Any]:
    return {
        "host": os.getenv("DATABASE_HOST", "localhost"),
        "port": int(os.getenv("DATABASE_PORT", "5432")),
        "user": os.getenv("DATABASE_USER", "postgres"),
        "password": os.getenv("DATABASE_PASSWORD", ""),
        "database": os.getenv("DATABASE_NAME", "postgres"),
        "ssl": os.getenv("DATABASE_SSL", "false").lower() == "true",
    }


def _coerce_connection_details(details: Any) -> Dict[str, Any]:
    """Always return a dict; parse JSON strings stored by mistake."""
    if isinstance(details, dict):
        return details.copy()

    if isinstance(details, str):
        text = details.strip()
        for _ in range(2):
            try:
                parsed = json.loads(text)
            except Exception:
                break
            if isinstance(parsed, dict):
                return parsed.copy()
            if isinstance(parsed, str):
                text = parsed.strip()
                continue
            break

    logger.warning(
        "Connection details are not a dict (%s); falling back to environment defaults",
        type(details).__name__,
    )
    return _default_connection_details()


def set_connection_details(details: Dict[str, Any]) -> None:
    global _active_connection_details
    _active_connection_details = _coerce_connection_details(details)


def get_connection_details() -> Dict[str, Any]:
    if _active_connection_details is not None:
        return _coerce_connection_details(_active_connection_details)
    return _default_connection_details()


def _normalize_tool_input(tool_input: Any) -> Dict[str, Any]:
    if isinstance(tool_input, dict):
        # OpenAI/Groq function-call shape sometimes leaks through
        function = tool_input.get("function")
        if isinstance(function, dict) and "arguments" in function:
            return _normalize_tool_input(function["arguments"])
        if "arguments" in tool_input and "name" in tool_input:
            return _normalize_tool_input(tool_input["arguments"])

        # Some tool frameworks wrap payloads as {"input": {...}}
        if "input" in tool_input and len(tool_input) == 1:
            return _normalize_tool_input(tool_input["input"])
        return tool_input

    if isinstance(tool_input, str):
        original = tool_input
        text = tool_input.strip()

        # Unwrap quoted JSON string values
        if len(text) >= 2 and text[0] == text[-1] and text[0] in ['"', "'"]:
            text = text[1:-1].strip()

        for _ in range(3):
            try:
                normalized = json.loads(text)
            except Exception:
                try:
                    normalized = ast.literal_eval(text)
                except Exception:
                    normalized = None

            if isinstance(normalized, dict):
                return normalized
            if isinstance(normalized, str):
                if normalized == text:
                    break
                text = normalized.strip()
                continue
            if isinstance(normalized, (list, tuple)):
                return {"input": normalized}
            if normalized is not None:
                return {"input": normalized}
            break

        logger.debug(f"Failed to parse tool input string as JSON or literal: {original}")
        return {"input": original}

    if isinstance(tool_input, list):
        return {"input": tool_input}
    return {"input": tool_input}


def _build_db_connection(tool_input: Any) -> DatabaseConnection:
    tool_input = _normalize_tool_input(tool_input)
    if not isinstance(tool_input, dict):
        logger.error(f"Normalized tool input is not a dict: {type(tool_input)} {tool_input}")
        raise ValueError("Tool input must be a JSON object or dictionary")

    connection = get_connection_details()
    for key in ["host", "port", "user", "password", "ssl"]:
        if key in tool_input:
            connection[key] = tool_input[key]

    connection["port"] = int(connection["port"])
    ssl_value = connection["ssl"]
    if isinstance(ssl_value, str):
        connection["ssl"] = ssl_value.lower() in ("true", "1", "yes")
    else:
        connection["ssl"] = bool(ssl_value)

    return DatabaseConnection(
        host=connection["host"],
        port=connection["port"],
        user=connection["user"],
        password=connection["password"],
        database=connection["database"],
        ssl=connection["ssl"],
    )


def _resolve_query_database(tool_input: Dict[str, Any]) -> str:
    """Always query the database the user authenticated against in the UI."""
    connected_db = get_connection_details()["database"]
    requested = tool_input.get("database")
    if requested and requested != connected_db:
        logger.info(
            "Ignoring LLM database '%s'; using connected database '%s'",
            requested,
            connected_db,
        )
    return connected_db


def _format_result_as_text(result: Any) -> str:
    if isinstance(result, list):
        if not result:
            return "No rows returned."
        return "\n".join([json.dumps(row, default=str) for row in result])
    if isinstance(result, dict):
        return json.dumps(result, default=str)
    return str(result)


class MCPClient:
    """
    HTTP-based client for connecting to MCP Server.
    Uses httpx to communicate with the MCP server directly.
    """
    
    def __init__(self, mcp_server_url: str = "http://localhost:8001"):
        """
        Initialize MCP client.
        
        Args:
            mcp_server_url: URL of the MCP server
        """
        self.mcp_server_url = mcp_server_url.rstrip('/')
        self.client: Optional[httpx.AsyncClient] = None
        self.tools_cache: Optional[List[Dict[str, Any]]] = None
        self.connected = False
    
    async def connect(self) -> bool:
        """
        Connect to the MCP server (test connection).
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Create async HTTP client
            self.client = httpx.AsyncClient(timeout=10.0)
            
            # Test connection with health check
            response = await self.client.get(f"{self.mcp_server_url}/health")
            
            if response.status_code == 200:
                logger.info(f"Connected to MCP server at {self.mcp_server_url}")
                self.connected = True
                return True
            else:
                logger.error(f"MCP server returned status {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.client:
            await self.client.aclose()
            self.client = None
            self.connected = False
            logger.info("Disconnected from MCP server")
    
    async def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools from MCP server.
        For now, returns a static list since we can't query via HTTP.
        
        Returns:
            List of tool definitions
        """
        # Return cached tools if available
        if self.tools_cache is not None:
            return self.tools_cache
        
        # Return default tools (since MCP server doesn't expose via HTTP)
        self.tools_cache = [
            {
                "name": "list_databases",
                "description": "List all available PostgreSQL databases",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "list_tables",
                "description": "List all tables in a database",
                "inputSchema": {
                    "type": "object",
                    "properties": {"database": {"type": "string"}},
                    "required": ["database"]
                }
            },
            {
                "name": "get_table_schema",
                "description": "Get column definitions of a table",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string"},
                        "table_name": {"type": "string"}
                    },
                    "required": ["database", "table_name"]
                }
            },
            {
                "name": "execute_query",
                "description": "Execute a SQL SELECT query",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string"},
                        "query": {"type": "string"}
                    },
                    "required": ["database", "query"]
                }
            },
            {
                "name": "update_data",
                "description": "Update records in a table",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string"},
                        "table": {"type": "string"},
                        "set_clause": {"type": "object"},
                        "where_clause": {"type": "string"}
                    },
                    "required": ["database", "table", "set_clause", "where_clause"]
                }
            },
            {
                "name": "preview_table",
                "description": "Preview first N rows of a table",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string"},
                        "table": {"type": "string"},
                        "limit": {"type": "integer"}
                    },
                    "required": ["database", "table"]
                }
            },
            {
                "name": "health_check",
                "description": "Test connection to the MCP server",
                "inputSchema": {"type": "object", "properties": {}}
            }
        ]
        
        logger.info(f"Returned {len(self.tools_cache)} tools")
        return self.tools_cache
    
    async def call_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Execute a registered tool using local database utilities.
        """
        try:
            logger.info(f"Calling tool '{tool_name}' with input: {tool_input} (type={type(tool_input)})")
            tool_input = _normalize_tool_input(tool_input)
            logger.info(f"Normalized tool input: {tool_input} (type={type(tool_input)})")
            db_conn = _build_db_connection(tool_input)
            db_ops = DatabaseOperations(db_conn)

            if tool_name == "execute_query":
                query = tool_input.get("query")
                if not query:
                    raise ValueError("Missing query for execute_query")
                if not isinstance(query, str):
                    raise ValueError("Query must be a string")
                database = _resolve_query_database(tool_input)
                return await db_ops.execute_query(database, query)

            if tool_name == "preview_table":
                table = tool_input.get("table")
                if not table:
                    raise ValueError("Missing table for preview_table")
                limit = int(tool_input.get("limit", 10))
                return await db_ops.execute_query(
                    db_conn.database,
                    f'SELECT * FROM "{table}" LIMIT {limit}'
                )

            if tool_name == "list_tables":
                database = _resolve_query_database(tool_input)
                return await db_ops.list_tables(database)

            if tool_name == "get_table_schema":
                table_name = tool_input.get("table_name")
                if not table_name:
                    raise ValueError("Missing table_name for get_table_schema")
                database = _resolve_query_database(tool_input)
                return await db_ops.get_table_schema(database, table_name)

            if tool_name == "list_databases":
                return await db_ops.list_databases()

            if tool_name == "health_check":
                return await db_conn.test_connection()

            raise ValueError(f"Unsupported tool: {tool_name}")

        except Exception as e:
            error_msg = f"Error calling tool '{tool_name}': {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            return f"Error: {error_msg}"
    
    async def call_tool_streaming(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        Stream tool execution results.
        
        Args:
            tool_name: Name of the tool
            tool_input: Input parameters
        
        Yields:
            Tool response chunks
        """
        try:
            logger.info(f"Streaming tool '{tool_name}'")
            
            # Stream start event
            yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name})}\n\n"
            
            # Shield DB work from stream cancellation closing connections mid-query
            result_value = await asyncio.shield(self.call_tool(tool_name, tool_input))
            
            if isinstance(result_value, str):
                try:
                    result = json.loads(result_value)
                except Exception:
                    result = result_value
            else:
                result = result_value
            
            # Stream result event for tool handling
            result_payload = {
                'type': 'tool_result',
                'tool': tool_name,
                'result': result if not isinstance(result, str) else {'output': result}
            }
            yield f"data: {json.dumps(result_payload, default=str)}\n\n"

            # Emit event as assistant content so CopilotKit can render it
            text_output = _format_result_as_text(result)
            if text_output:
                yield f"data: {json.dumps({'choices': [{'delta': {'role': 'assistant', 'content': text_output}}]})}\n\n"

            # Stream complete event
            yield f"data: {json.dumps({'type': 'tool_complete', 'tool': tool_name})}\n\n"
            yield "data: [DONE]\n\n"
        
        except Exception as e:
            logger.error(f"Error streaming tool '{tool_name}': {e}")
            yield f"data: {json.dumps({'type': 'tool_error', 'tool': tool_name, 'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
    
    async def is_connected(self) -> bool:
        """Check if MCP server is reachable in real time and update connection state."""
       
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.mcp_server_url}/health")
                if resp.status_code == 200:
                    data = resp.json()
                    self.connected = data.get("status") == "healthy"
                    return self.connected
        except Exception:
            pass
        self.connected = False
        return False


# Global MCP client instance
_mcp_client: Optional[MCPClient] = None


async def get_mcp_client(mcp_server_url: str = "http://localhost:8001") -> MCPClient:
    """
    Get or create global MCP client instance.
    
    Args:
        mcp_server_url: URL of the MCP server
    
    Returns:
        MCPClient instance
    """
    global _mcp_client
    
    if _mcp_client is None:
        _mcp_client = MCPClient(mcp_server_url)
    
    return _mcp_client


async def initialize_mcp_client(mcp_server_url: str = "http://localhost:8001") -> bool:
    """
    Initialize and connect the global MCP client.
    
    Args:
        mcp_server_url: URL of the MCP server
    
    Returns:
        True if successful, False otherwise
    """
    client = await get_mcp_client(mcp_server_url)
    return await client.connect()


async def close_mcp_client():
    """Close the global MCP client connection."""
    global _mcp_client
    if _mcp_client:
        await _mcp_client.disconnect()
        _mcp_client = None
