"""
Database utility functions for PostgreSQL operations
"""
import asyncio
import logging
import asyncpg
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages PostgreSQL connection details and operations"""

    def __init__(self, host: str, port: int, user: str, password: str, database: str, ssl: bool = False):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.ssl = ssl

    @asynccontextmanager
    async def connect(self, db_name: Optional[str] = None):
        """Open a dedicated connection for the duration of one operation."""
        db = db_name or self.database
        conn = await asyncpg.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=db,
            ssl=self.ssl,
            timeout=30.0,
            command_timeout=60.0,
        )
        try:
            yield conn
        except asyncio.CancelledError:
            raise
        finally:
            if conn is not None and not conn.is_closed():
                try:
                    await conn.close()
                except Exception as exc:
                    logger.debug("Error closing connection for %s: %s", db, exc)

    async def test_connection(self) -> bool:
        """Test if connection is valid"""
        try:
            async with self.connect(self.database) as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False


class DatabaseOperations:
    """Database operations wrapper"""

    def __init__(self, db_conn: DatabaseConnection):
        self.db_conn = db_conn

    async def list_tables(self, database: str) -> List[str]:
        """List all tables in a database"""
        async with self.db_conn.connect(database) as conn:
            rows = await conn.fetch("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            return [row["table_name"] for row in rows]

    async def get_table_schema(self, database: str, table_name: str) -> Dict[str, str]:
        """Get column names and types for a table"""
        async with self.db_conn.connect(database) as conn:
            rows = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = $1 AND table_schema = 'public'
                ORDER BY ordinal_position
            """, table_name)

            schema = {}
            for row in rows:
                nullable = "NULL" if row["is_nullable"] == "YES" else "NOT NULL"
                schema[row["column_name"]] = f"{row['data_type']} ({nullable})"
            return schema

    async def execute_query(self, database: str, query: str, params: List[Any] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results"""
        dangerous_keywords = ["DROP", "DELETE", "TRUNCATE"]
        if any(keyword in query.upper() for keyword in dangerous_keywords):
            raise ValueError("Dangerous query operations are not allowed")

        target_db = database or self.db_conn.database
        async with self.db_conn.connect(target_db) as conn:
            if params:
                rows = await conn.fetch(query, *params)
            else:
                rows = await conn.fetch(query)
            return [dict(row) for row in rows]

    async def update_data(self, database: str, table: str, set_clause: Dict[str, Any], where_clause: str) -> int:
        """Update data in a table"""
        if not set_clause:
            raise ValueError("No columns to update")

        set_parts = [f'"{col}" = ${i+1}' for i, col in enumerate(set_clause.keys())]
        set_sql = ", ".join(set_parts)
        query = f'UPDATE "{table}" SET {set_sql} WHERE {where_clause}'
        values = list(set_clause.values())

        async with self.db_conn.connect(database) as conn:
            result = await conn.execute(query, *values)

        return int(result.split()[-1])

    async def list_databases(self) -> List[str]:
        """List all databases on the server"""
        async with self.db_conn.connect("postgres") as conn:
            rows = await conn.fetch("""
                SELECT datname
                FROM pg_database
                WHERE datistemplate = false
                ORDER BY datname
            """)
            return [row["datname"] for row in rows]


async def clear_connection_pools() -> None:
    """Kept for API compatibility; no pools are used."""
    return None
