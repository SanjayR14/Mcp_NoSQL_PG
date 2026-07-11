#!/usr/bin/env python
import asyncio
import asyncpg

async def test():
    try:
        conn = await asyncpg.connect(
            host='127.0.0.1',
            port=5432,
            user='sanju140988',
            password='sanju140988',
            database='testdb'
        )
        print('Connection successful')
        await conn.close()
    except Exception as e:
        print(f'Error: {type(e).__name__}: {e}')

if __name__ == '__main__':
    asyncio.run(test())
