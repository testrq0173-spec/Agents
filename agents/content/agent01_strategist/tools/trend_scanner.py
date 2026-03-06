"""
Tool stubs for Agent 01 — Content Strategist.

Replace each stub body with real API client code.
Each tool MUST be an async function matching the ToolFn signature.
"""

from __future__ import annotations
from ...shared.schemas.trend_data import TrendData, TrendSource, GoogleTrendsSignal


async def scan_trends(sources: list[str]) -> list[TrendData]:
    """
    Fetch trending topics from configured sources.

    Integrations to implement:
      - Google Trends API  (pytrends or Official API)
      - Reddit API         (PRAW or Reddit Data API v2)
      - Ahrefs API         (https://ahrefs.com/api/)

    Args:
        sources: List of source keys to query, e.g. ["google_trends", "reddit"]

    Returns:
        List of TrendData objects, unsorted and un-deduped.
    """
    # ── STUB ──────────────────────────────────────────────────────────────
    # TODO: implement real API calls
    return [
        TrendData(
            topic="LLM Agents in Production 2025",
            primary_source=TrendSource.GOOGLE_TRENDS,
            trend_score=91.5,
            novelty_score=0.95,
            google_trends=GoogleTrendsSignal(
                interest_over_time=[50, 60, 72, 85, 92, 100, 98],
                related_queries=["AutoGen", "LangGraph", "CrewAI"],
                geo="US",
                breakout=True,
            ),
        )
    ]
