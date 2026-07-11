"""
MCP Server Entry Point
Runs the PostgreSQL MCP server with SSE transport
"""

import logging
import argparse
from typing import Any

import uvicorn
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server.sse import SseServerTransport

from server import get_mcp_server

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def create_starlette_app(debug: bool = False) -> Starlette:
    """
    Create a Starlette application that serves the MCP server with SSE transport.
    
    Args:
        debug: Enable debug mode
    
    Returns:
        Configured Starlette application
    """
    mcp_server = get_mcp_server()
    sse = SseServerTransport("/messages/")
    
    async def root_endpoint(request: Request):
        """Root endpoint showing server info."""
        from starlette.responses import JSONResponse
        return JSONResponse({
            "status": "running",
            "server": "NLTOSQL MCP Server",
            "version": "1.0.0",
            "endpoints": {
                "sse": "GET /sse",
                "health": "GET /health",
                "messages": "POST /messages/"
            }
        })
    
    async def handle_sse(request: Request):
        """Handle SSE connections from MCP clients."""
        try:
            logger.info("SSE connection initiated from %s", request.client)
            async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,
            ) as (read_stream, write_stream):
                logger.info("SSE connection established, starting MCP server")
                await mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp_server.create_initialization_options(),
                )
        except Exception as e:
            logger.error(f"Error in SSE handler: {e}", exc_info=True)
            raise
    
    return Starlette(
        debug=debug,
        routes=[
            Route("/", endpoint=root_endpoint, methods=["GET"]),
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
            Route("/health", endpoint=health_endpoint, methods=["GET"]),
        ],
    )


async def health_endpoint(request: Request):
    """Health check endpoint."""
    from starlette.responses import JSONResponse
    return JSONResponse({
        "status": "healthy",
        "server": "NLTOSQL-Database-Server",
        "version": "1.0.0"
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run MCP SSE-based PostgreSQL server")
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8001, help='Port to listen on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("🚀 MCP PostgreSQL Server Starting")
    print("="*70)
    print("\nAvailable Tools (MCP Protocol):")
    print("  1. list_databases       - List all databases")
    print("  2. list_tables          - List all tables in a database")
    print("  3. get_table_schema     - Get column definitions")
    print("  4. execute_query        - Run SELECT queries")
    print("  5. update_data          - Update records in a table")
    print("  6. preview_table        - Preview first N rows")
    print("  7. health_check         - Test server connectivity")
    print("\nServer Configuration:")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  SSE Endpoint: http://{args.host}:{args.port}/sse")
    print(f"  Health Check: http://{args.host}:{args.port}/health")
    print(f"  Debug Mode: {args.debug}")
    print("\n" + "="*70 + "\n")
    
    # Create the Starlette app
    starlette_app = create_starlette_app(debug=args.debug)
    
    # Run the server
    try:
        uvicorn.run(
            starlette_app,
            host=args.host,
            port=args.port,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n✋ Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise
