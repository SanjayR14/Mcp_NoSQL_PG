import traceback
from mcp_client import _normalize_tool_input, _build_db_connection

inp = '{"database":"company_database","query":"SELECT id FROM departmentsWHERE name = \'IT\'"}'
print('raw type:', type(inp))
print('raw repr:', repr(inp))
try:
    normalized = _normalize_tool_input(inp)
    print('normalized type:', type(normalized))
    print('normalized repr:', repr(normalized))
    conn = _build_db_connection(inp)
    print('conn ok', conn.database)
except Exception as e:
    traceback.print_exc()
