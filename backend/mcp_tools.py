"""
MCP Server for PostgreSQL database operations
Handles List Tables, Get Schema, Execute Query, and Update Data operations
"""
import asyncio
import json
import sys
import os
from db_utils import DatabaseConnection, DatabaseOperations


# Global database operations instance
db_ops: DatabaseOperations = None


def initialize_db_connection(host: str, port: int, user: str, password: str, database: str, ssl: bool = False):
    """Initialize the database connection"""
    global db_ops
    db_conn = DatabaseConnection(host, port, user, password, database, ssl)
    db_ops = DatabaseOperations(db_conn)


async def handle_tool_call(tool_name: str, tool_input: dict) -> str:
    """
    Handle tool calls from FastAPI backend
    Returns JSON string with results
    """
    try:
        if tool_name == "list_tables":
            database = tool_input.get("database", "postgres")
            tables = await db_ops.list_tables(database)
            return json.dumps({
                "status": "success",
                "data": tables,
                "message": f"Found {len(tables)} tables in database '{database}'"
            })
        
        elif tool_name == "get_table_schema":
            database = tool_input.get("database", "postgres")
            table_name = tool_input.get("table_name")
            
            if not table_name:
                return json.dumps({"status": "error", "message": "table_name is required"})
            
            schema = await db_ops.get_table_schema(database, table_name)
            return json.dumps({
                "status": "success",
                "data": schema,
                "message": f"Schema for table '{table_name}' in database '{database}'"
            })
        
        elif tool_name == "execute_query":
            database = tool_input.get("database", "postgres")
            query = tool_input.get("query")
            
            if not query:
                return json.dumps({"status": "error", "message": "query is required"})
            
            results = await db_ops.execute_query(database, query)
            return json.dumps({
                "status": "success",
                "data": results,
                "message": f"Query executed successfully. Found {len(results)} rows."
            })
        
        elif tool_name == "update_data":
            database = tool_input.get("database", "postgres")
            table = tool_input.get("table")
            set_clause = tool_input.get("set_clause")  # Dict of column: value
            where_clause = tool_input.get("where_clause")
            
            if not table or not set_clause or not where_clause:
                return json.dumps({
                    "status": "error",
                    "message": "table, set_clause (dict), and where_clause are required"
                })
            
            affected_rows = await db_ops.update_data(database, table, set_clause, where_clause)
            return json.dumps({
                "status": "success",
                "data": {"affected_rows": affected_rows},
                "message": f"Updated {affected_rows} row(s) in table '{table}'"
            })
        
        elif tool_name == "list_databases":
            databases = await db_ops.list_databases()
            return json.dumps({
                "status": "success",
                "data": databases,
                "message": f"Found {len(databases)} databases"
            })
        
        else:
            return json.dumps({
                "status": "error",
                "message": f"Unknown tool: {tool_name}"
            })
    
    except ValueError as e:
        return json.dumps({"status": "error", "message": f"Validation error: {str(e)}"})
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error: {str(e)}"})


# Tool definitions that will be sent to the frontend/AI
AVAILABLE_TOOLS = [
    {
        "name": "list_tables",
        "description": "List all tables in a PostgreSQL database",
        "inputSchema": {
            "type": "object",
            "properties": {
                "database": {
                    "type": "string",
                    "description": "Database name (defaults to 'postgres')"
                }
            }
        }
    },
    {
        "name": "get_table_schema",
        "description": "Get the schema (column names and types) of a specific table",
        "inputSchema": {
            "type": "object",
            "properties": {
                "database": {
                    "type": "string",
                    "description": "Database name"
                },
                "table_name": {
                    "type": "string",
                    "description": "Name of the table"
                }
            },
            "required": ["database", "table_name"]
        }
    },
    {
        "name": "execute_query",
        "description": "Execute a SELECT query against a PostgreSQL database",
        "inputSchema": {
            "type": "object",
            "properties": {
                "database": {
                    "type": "string",
                    "description": "Database name"
                },
                "query": {
                    "type": "string",
                    "description": "SQL SELECT query to execute"
                }
            },
            "required": ["database", "query"]
        }
    },
    {
        "name": "update_data",
        "description": "Update data in a table (INSERT, UPDATE operations)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "database": {
                    "type": "string",
                    "description": "Database name"
                },
                "table": {
                    "type": "string",
                    "description": "Table name"
                },
                "set_clause": {
                    "type": "object",
                    "description": "Dictionary of column: value pairs to update. Example: {'status': 'active', 'count': 10}"
                },
                "where_clause": {
                    "type": "string",
                    "description": "WHERE condition. Example: 'id = 5 AND status = \"inactive\"'"
                }
            },
            "required": ["database", "table", "set_clause", "where_clause"]
        }
    },
    {
        "name": "list_databases",
        "description": "List all available databases on the PostgreSQL server",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]
