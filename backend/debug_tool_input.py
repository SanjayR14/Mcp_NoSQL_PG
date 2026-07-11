import asyncio
import json
from mcp_client import MCPClient

async def main():
    client = MCPClient('http://127.0.0.1:8001')

    inputs = [
        {'database': 'company_db', 'query': 'SELECT * FROM employees WHERE id = 10'},
        json.dumps({'database': 'company_db', 'query': 'SELECT * FROM employees WHERE id = 10'}),
        '{"database":"company_db","query":"SELECT * FROM employees WHERE id = 10"}',
    ]

    for inp in inputs:
        print('---')
        print('INPUT TYPE:', type(inp), 'VALUE:', repr(inp))
        try:
            result = await client.call_tool('execute_query', inp)
            print('RESULT TYPE:', type(result))
            print('RESULT:', result)
        except Exception as e:
            import traceback
            traceback.print_exc()

asyncio.run(main())
