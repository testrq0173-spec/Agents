"""
PostgreSQL Session Manager
==========================
Handles async engine creation and session factory.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from ..config.settings import settings

# 1. Create the engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False, # Set to True for SQL logging
    pool_size=10,
    max_overflow=20,
)

# 2. Create the session factory
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    """Dependency for getting async database sessions."""
    async with async_session() as session:
        yield session
