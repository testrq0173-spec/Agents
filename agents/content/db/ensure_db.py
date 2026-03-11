import asyncio
import asyncpg

async def setup_db():
    admin_user = 'postgres'
    admin_password = 'admin'
    target_db = 'openclaw_content'
    target_user = 'openclaw'
    target_password = 'password'

    try:
        # Connect to default 'postgres' database as superuser
        conn = await asyncpg.connect(user=admin_user, password=admin_password, host='localhost', port=5432, database='postgres')
        
        # Check if database exists
        exists = await conn.fetchval(f"SELECT 1 FROM pg_database WHERE datname = '{target_db}'")
        if not exists:
            await conn.execute(f"CREATE DATABASE {target_db}")
            print(f"Database '{target_db}' created.")
        else:
            print(f"Database '{target_db}' already exists.")

        # Check if user exists
        user_exists = await conn.fetchval(f"SELECT 1 FROM pg_roles WHERE rolname = '{target_user}'")
        if not user_exists:
            await conn.execute(f"CREATE USER {target_user} WITH PASSWORD '{target_password}'")
            await conn.execute(f"ALTER USER {target_user} WITH SUPERUSER")
            print(f"User '{target_user}' created and granted superuser permissions.")
        else:
            # Update password just in case
            await conn.execute(f"ALTER USER {target_user} WITH PASSWORD '{target_password}'")
            print(f"User '{target_user}' already exists, password updated.")

        await conn.close()
        print("Setup complete!")
    except Exception as e:
        print(f"Setup failed: {e}")

if __name__ == "__main__":
    asyncio.run(setup_db())
