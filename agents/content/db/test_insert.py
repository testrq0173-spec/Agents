
import asyncio
import os
import sys

# Add workspace root to sys.path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from openclaw.agents.content.db.session import async_session, engine
from openclaw.agents.content.db.models.content_models import ContentBriefModel
import uuid

async def do_insert():
    async with async_session() as session:
        new_model = ContentBriefModel(
            id=uuid.uuid4(),
            topic="Test Topic from Script",
            title="Test Title from Script",
            status="pending",
            priority=5,
            trend_data={"dummy": "data"},
            seo_directives={"dummy": "data"},
            outline=[{"dummy": "data"}]
        )
        session.add(new_model)
        await session.commit()
        print(f"Committed model with ID: {new_model.id}")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(do_insert())
