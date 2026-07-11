#!/usr/bin/env python
import asyncio
import asyncpg
import traceback

async def test(host):
    try:
        print(f"Attempting to connect to PostgreSQL at {host}:5432...")
        conn = await asyncpg.connect(
            host=host,
            port=5432,
            user='sanju',
            password='sanju140908',
            database='testdb',
            timeout=10
        )
        print(f'✓ Connection successful to {host}')
        result = await conn.fetchval("SELECT 1")
        print(f"✓ Query result: {result}")
        await conn.close()
        return True
    except Exception as e:
        print(f'✗ Error with {host}: {type(e).__name__}: {e}')
        return False

async def main():
    # Try localhost first (might be Unix socket on Windows)
    success = await test('localhost')
    
    if not success:
        # Try 127.0.0.1 second
        print("\nTrying 127.0.0.1...")
        success = await test('127.0.0.1')
    
    if success:
        print("\n✓ Database connection successful!")
    else:
        print("\n✗ Could not connect to database")
        print("Please check:")
        print("1. PostgreSQL is running (netstat -ano | findstr 5432)")
        print("2. User 'sanju' exists and password is correct")
        print("3. Database 'testdb' exists")

if __name__ == '__main__':
    asyncio.run(main())

