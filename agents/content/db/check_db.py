
import asyncio
import asyncpg

async def check():
    c = await asyncpg.connect(user='openclaw',password='password',database='openclaw_content',host='localhost')
    rows = await c.fetch('SELECT * FROM content_briefs;')
    print(f"Number of rows: {len(rows)}")
    for r in rows:
        print(r['topic'], r['status'])
    await c.close()

if __name__ == "__main__":
    asyncio.run(check())
