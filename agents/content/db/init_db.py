"""
Initialize PostgreSQL Database
==============================
Creates all tables defined in content_models.py.
"""

import asyncio
import sys
import os

# Add parent directory to sys.path so we can import modules
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from openclaw.agents.content.db.session import engine
from openclaw.agents.content.db.models.content_models import Base

async def init_db():
    print("Connecting to database and creating tables...")
    async with engine.begin() as conn:
        # Import models here to ensure they are registered with Base
        from openclaw.agents.content.db.models.content_models import ContentBriefModel, PostModel
        
        # Create tables
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialization complete!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())
