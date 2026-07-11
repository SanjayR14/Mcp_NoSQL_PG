"""
MCP Server for PostgreSQL Database Operations
Uses proper MCP (Model Context Protocol) with SSE transport
"""

import logging
import os
from typing import Any
import asyncpg
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastMCP server for PostgreSQL tools
mcp = FastMCP("NLTOSQL-Database-Server", "1.0.0")

# ============================================================================
# Database Connection Helper
# ============================================================================

async def connect_db(db_name: str = None) -> asyncpg.Connection:
    """Connect to PostgreSQL database."""
    target_db = db_name or os.getenv("DATABASE_NAME", "postgres")
    
    try:
        conn = await asyncpg.connect(
            database=target_db,
            user=os.getenv("DATABASE_USER", "postgres"),
            password=os.getenv("DATABASE_PASSWORD", ""),
            host=os.getenv("DATABASE_HOST", "localhost"),
            port=int(os.getenv("DATABASE_PORT", "5432")),
            ssl=os.getenv("DATABASE_SSL", "false").lower() == "true"
        )
        logger.info(f"Connected to database: {target_db}")
        return conn
    except Exception as e:
        logger.error(f"Connection error: {e}")
        raise


# ============================================================================
# MCP Tools - Database Operations
# ============================================================================

@mcp.tool(
    name="list_databases",
    description="List all available PostgreSQL databases on the server"
)
async def list_databases():
    """
    List all databases on the PostgreSQL server.
    
    Returns:
        Newline-separated list of database names
    """
    try:
        conn = await connect_db("postgres")
        rows = await conn.fetch(
            "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;"
        )
        await conn.close()
        
        if not rows:
            return "No databases found."
        
        db_list = "\n".join([row["datname"] for row in rows])
        logger.info(f"Listed {len(rows)} databases")
        return db_list
    
    except Exception as e:
        error_msg = f"Error listing databases: {str(e)}"
        logger.error(error_msg)
        return f"Error: {error_msg}"


@mcp.tool(
    name="list_tables",
    description="List all public tables in a PostgreSQL database"
)
async def list_tables(database: str):
    """
    List all tables in the specified database.
    
    Args:
        database: Name of the database
    
    Returns:
        Newline-separated list of table names
    """
    try:
        conn = await connect_db(database)
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_type='BASE TABLE' "
            "ORDER BY table_name;"
        )
        await conn.close()
        
        if not rows:
            return f"No public tables found in database '{database}'."
        
        tables = "\n".join([row["table_name"] for row in rows])
        logger.info(f"Listed {len(rows)} tables in database '{database}'")
        return tables
    
    except Exception as e:
        error_msg = f"Error listing tables in '{database}': {str(e)}"
        logger.error(error_msg)
        return f"Error: {error_msg}"


@mcp.tool(
    name="get_table_schema",
    description="Get column names, types, and constraints of a PostgreSQL table"
)
async def get_table_schema(database: str, table_name: str):
    """
    Get the schema (columns, types, constraints) of a table.
    
    Args:
        database: Name of the database
        table_name: Name of the table
    
    Returns:
        Column information formatted as 'column_name: data_type (constraints)'
    """
    try:
        conn = await connect_db(database)
        rows = await conn.fetch(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_name = $1 AND table_schema = 'public' "
            "ORDER BY ordinal_position;",
            table_name
        )
        await conn.close()
        
        if not rows:
            return f"No schema found for table '{table_name}' in database '{database}'."
        
        schema_lines = []
        for row in rows:
            nullable = "NULL" if row["is_nullable"] == "YES" else "NOT NULL"
            default = f" DEFAULT {row['column_default']}" if row["column_default"] else ""
            schema_lines.append(
                f"{row['column_name']}: {row['data_type']} ({nullable}{default})"
            )
        
        logger.info(f"Retrieved schema for table '{table_name}' with {len(rows)} columns")
        return "\n".join(schema_lines)
    
    except Exception as e:
        error_msg = f"Error retrieving schema: {str(e)}"
        logger.error(error_msg)
        return f"Error: {error_msg}"


@mcp.tool(
    name="execute_query",
    description="Execute a SQL SELECT query against a PostgreSQL database"
)
async def execute_query(database: str, query: str):
    """
    Execute a SELECT query and return results.
    
    Args:
        database: Name of the database
        query: SQL SELECT query to execute
    
    Returns:
        Query results as formatted strings
    
    Security:
        - Only supports SELECT queries
        - Blocks DROP, DELETE, TRUNCATE operations
    """
    try:
        # Security check: prevent dangerous operations
        dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "INSERT", "UPDATE", "ALTER"]
        query_upper = query.strip().upper()
        
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                error_msg = f"Dangerous query operation '{keyword}' not allowed"
                logger.warning(f"Blocked dangerous query: {query[:50]}...")
                return f"Error: {error_msg}"
        
        conn = await connect_db(database)
        rows = await conn.fetch(query)
        await conn.close()
        
        if not rows:
            return "Query executed successfully. No results returned."
        
        # Format results
        result_lines = []
        for row in rows:
            row_dict = dict(row)
            result_lines.append(str(row_dict))
        
        logger.info(f"Query executed successfully, returned {len(rows)} rows")
        return "\n".join(result_lines)
    
    except Exception as e:
        error_msg = f"Error executing query: {str(e)}"
        logger.error(error_msg)
        return f"Error: {error_msg}"


@mcp.tool(
    name="update_data",
    description="Update records in a PostgreSQL table"
)
async def update_data(
    database: str,
    table: str,
    set_clause: dict,
    where_clause: str
):
    """
    Update data in a table.
    
    Args:
        database: Name of the database
        table: Name of the table
        set_clause: Dict of column: value pairs to update (e.g., {"status": "active"})
        where_clause: SQL WHERE condition (e.g., "id = 5 AND age > 18")
    
    Returns:
        Number of rows affected
    """
    try:
        if not set_clause:
            return "Error: No columns to update"
        
        # Build the SET clause with proper parameterization
        set_parts = [f'"{col}" = ${i+1}' for i, col in enumerate(set_clause.keys())]
        set_sql = ", ".join(set_parts)
        
        # Build the full query
        query = f'UPDATE "{table}" SET {set_sql} WHERE {where_clause}'
        values = list(set_clause.values())
        
        conn = await connect_db(database)
        result = await conn.execute(query, *values)
        await conn.close()
        
        # Parse result to get number of rows affected
        affected_rows = int(result.split()[-1])
        logger.info(f"Updated {affected_rows} row(s) in table '{table}'")
        
        return f"Successfully updated {affected_rows} row(s) in table '{table}'"
    
    except Exception as e:
        error_msg = f"Error updating data: {str(e)}"
        logger.error(error_msg)
        return f"Error: {error_msg}"


@mcp.tool(
    name="preview_table",
    description="Get first N rows from a table for preview"
)
async def preview_table(database: str, table: str, limit: int = 10):
    """
    Preview data from a table.
    
    Args:
        database: Name of the database
        table: Name of the table
        limit: Number of rows to return (default: 10)
    
    Returns:
        Formatted table data
    """
    try:
        conn = await connect_db(database)
        rows = await conn.fetch(f'SELECT * FROM "{table}" LIMIT {limit}')
        await conn.close()
        
        if not rows:
            return f"No rows found in table '{table}'."
        
        result_lines = []
        for idx, row in enumerate(rows, 1):
            row_dict = dict(row)
            result_lines.append(f"Row {idx}: {row_dict}")
        
        logger.info(f"Previewed {len(rows)} rows from table '{table}'")
        return "\n".join(result_lines)
    
    except Exception as e:
        error_msg = f"Error previewing table: {str(e)}"
        logger.error(error_msg)
        return f"Error: {error_msg}"


@mcp.tool(
    name="health_check",
    description="Test connection to the MCP server"
)
async def health_check():
    """
    Test MCP server connectivity.
    
    Returns:
        Status message
    """
    try:
        conn = await connect_db("postgres")
        await conn.fetchval("SELECT 1")
        await conn.close()
        return "MCP Server is healthy and connected to PostgreSQL"
    except Exception as e:
        error_msg = f"Health check failed: {str(e)}"
        logger.error(error_msg)
        return f"Error: {error_msg}"


# ============================================================================
# Server Initialization
# ============================================================================

def get_mcp_server():
    """Get the MCP server instance for SSE transport."""
    return mcp._mcp_server
