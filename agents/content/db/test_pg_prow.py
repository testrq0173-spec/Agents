import asyncio
import asyncpg

async def test_conn():
    passwords = ['postgres', 'password', 'admin', 'root', '']
    for pwd in passwords:
        try:
            print(f"Testing password: '{pwd}'")
            conn = await asyncpg.connect(user='postgres', password=pwd, host='localhost', port=5432, database='postgres')
            print(f"SUCCESS with password: '{pwd}'")
            await conn.close()
            return pwd
        except Exception as e:
            print(f"Failed with '{pwd}': {e}")
    return None

if __name__ == "__main__":
    asyncio.run(test_conn())
