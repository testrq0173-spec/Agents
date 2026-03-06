"""
Quick smoke-test: runs Agent 01 pipeline against the real Gemini API.
Requires .env with GEMINI_API_KEY set.

Run from ANY directory:
    python d:/Agents/openclaw/agents/content/test_smoke.py

Or from d:/Agents/:
    python -m openclaw.agents.content.test_smoke
"""

import asyncio
import os
import sys

# ── Point sys.path to d:/Agents so that `openclaw.agents.content.*`
#    resolves correctly and relative imports (... ) work as intended.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Load .env from the content/ directory
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import redis.asyncio as aioredis
import json

# ── Now safe to import using full package paths ────────────────────────────
from openclaw.agents.content.shared.schemas.trend_data import (
    TrendData, TrendSource, GoogleTrendsSignal,
)
from openclaw.agents.content.agent01_strategist.tools.deduplicator import (
    deduplicate_trends,
)
from openclaw.agents.content.agent01_strategist.tools.brief_generator import (
    generate_brief,
)


async def smoke_test() -> None:
    print("\n" + "=" * 60)
    print("  OpenClaw Smoke Test -- Gemini Brief Generator")
    print("=" * 60)

    # 0. Connect to Redis for live demonstration
    r = aioredis.from_url("redis://localhost:6379", decode_responses=True)
    
    # Send a Heartbeat so the Dashboard sees the agent
    await r.publish("openclaw:agents:heartbeats", json.dumps({
        "agent_id": "strategist-01",
        "agent_name": "Strategist Agent",
        "status": "running",
        "cycle_count": 1
    }))

    # 1. Create a fake TrendData
    trend = TrendData(
        topic="AI Agents in Production 2025",
        primary_source=TrendSource.GOOGLE_TRENDS,
        trend_score=92.0,
        novelty_score=0.95,
        google_trends=GoogleTrendsSignal(
            interest_over_time=[45, 60, 75, 88, 95, 100, 98],
            related_queries=["LangGraph", "CrewAI", "AutoGen", "LLM tools"],
            geo="US",
            breakout=True,
        ),
    )
    print(f"\n[1/3] TrendData created: '{trend.topic}' (score={trend.trend_score})")

    # 2. Deduplication (stub in dev — always passes)
    novel = await deduplicate_trends([trend], threshold=0.85)
    print(f"[2/3] Deduplication passed: {len(novel)} novel trend(s)")

    # 3. Brief generation via Gemini
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key:
        print("\n[!] WARNING: GEMINI_API_KEY is not set in .env")
        print("    The brief_generator will fall back to the stub brief.")
        print("    Get a free key at: https://aistudio.google.com/app/apikey\n")

    print("[3/3] Calling Gemini to generate ContentBrief ...")
    brief = await generate_brief(novel[0])

    print("\n  Title      :", brief.title)
    print("  Slug       :", brief.seo.slug)
    print("  Priority   :", brief.priority)

    # 4. PUBLISH TO REDIS (The Magic Link!)
    print("\n🚀 PUBLISHING TO REDIS for Dashboard...")
    event_payload = {
        "agent_id": "strategist-01",
        "agent_name": "Strategist Agent",
        "payload": brief.redis_payload()
    }
    await r.publish("openclaw:events:content_briefs_ready", json.dumps(event_payload))
    
    # Send idle heartbeat
    await r.publish("openclaw:agents:heartbeats", json.dumps({
        "agent_id": "strategist-01",
        "agent_name": "Strategist Agent",
        "status": "idle",
        "cycle_count": 1
    }))
    
    await r.aclose()

    print("\n" + "=" * 60)
    print("  Smoke test PASSED & Event Published!")
    print("=" * 60 + "\n")



if __name__ == "__main__":
    asyncio.run(smoke_test())
