
import asyncio
import os
import sys

# Add workspace root to sys.path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from openclaw.agents.content.db.session import async_session
from openclaw.agents.content.db.models.content_models import ContentBriefModel
from sqlalchemy import select, func

async def count():
    async with async_session() as s:
        c = await s.scalar(select(func.count(ContentBriefModel.id)))
        print(f"Total Briefs in DB: {c}")

if __name__ == "__main__":
    asyncio.run(count())
