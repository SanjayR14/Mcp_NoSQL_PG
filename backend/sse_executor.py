"""
SSE (Server-Sent Events) client for communicating with MCP tools
Handles tool execution with streaming responses
"""
import json
import asyncio
from typing import Dict, Any, AsyncGenerator


class ToolExecutor:
    """Executes tools and streams responses via SSE"""
    
    def __init__(self, mcp_tools_module):
        """Initialize with MCP tools module"""
        self.mcp_tools = mcp_tools_module
    
    async def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """
        Execute a tool and yield SSE-formatted responses
        
        Yields:
            SSE formatted strings (data: json\n\n)
        """
        try:
            # Send start event
            yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name})}\n\n"
            
            # Execute the tool
            result = await self.mcp_tools.handle_tool_call(tool_name, tool_input)
            result_data = json.loads(result)
            
            # Send result event
            yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'result': result_data})}\n\n"
            
            # Send completion event
            yield f"data: {json.dumps({'type': 'tool_complete', 'tool': tool_name})}\n\n"
        
        except Exception as e:
            # Send error event
            error_response = {
                'type': 'tool_error',
                'tool': tool_name,
                'error': str(e)
            }
            yield f"data: {json.dumps(error_response)}\n\n"
    
    async def execute_tool_batch(self, tools_list: list) -> AsyncGenerator[str, None]:
        """
        Execute multiple tools in sequence and stream responses
        
        Args:
            tools_list: List of dicts with 'name' and 'input' keys
        
        Yields:
            SSE formatted strings
        """
        for tool_call in tools_list:
            tool_name = tool_call.get('name')
            tool_input = tool_call.get('input', {})
            
            async for event in self.execute_tool(tool_name, tool_input):
                yield event
            
            # Small delay between tool executions
            await asyncio.sleep(0.1)


class ToolRegistry:
    """Registry of available tools"""
    
    def __init__(self):
        self.tools = {}
    
    def register(self, tool_definition: Dict[str, Any]):
        """Register a tool definition"""
        tool_name = tool_definition.get('name')
        self.tools[tool_name] = tool_definition
    
    def register_multiple(self, tool_definitions: list):
        """Register multiple tools"""
        for tool in tool_definitions:
            self.register(tool)
    
    def get_tool(self, tool_name: str) -> Dict[str, Any]:
        """Get a tool definition by name"""
        return self.tools.get(tool_name)
    
    def get_all_tools(self) -> list:
        """Get all registered tools"""
        return list(self.tools.values())
    
    def validate_tool_input(self, tool_name: str, tool_input: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate tool input against schema
        
        Returns:
            (is_valid, error_message)
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return False, f"Tool '{tool_name}' not found"
        
        schema = tool.get('inputSchema', {})
        required = schema.get('required', [])
        properties = schema.get('properties', {})
        
        # Check required fields
        for field in required:
            if field not in tool_input:
                return False, f"Required field '{field}' missing for tool '{tool_name}'"
        
        # Check field types (basic validation)
        for field, value in tool_input.items():
            if field not in properties:
                return False, f"Unknown field '{field}' for tool '{tool_name}'"
        
        return True, ""
