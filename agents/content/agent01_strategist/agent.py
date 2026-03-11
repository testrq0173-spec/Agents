"""
Agent 01 — Content Strategist
==============================
Runs on a 4-hour cron cycle.

Workflow
--------
1. trend_scanner    → Fetch signals from Google Trends, Reddit, Ahrefs
2. deduplicator     → Query Qdrant; reject topics with cosine sim ≥ 0.85
3. brief_generator  → Claude creates a ContentBrief per approved trend
4. db_writer        → Persist ContentBrief to PostgreSQL
5. emit             → Publish 'content_briefs_ready' Redis event
"""

from __future__ import annotations

import logging
from typing import Any

from ..core.base_agent import AgentConfig, BaseAgent
from ..shared.schemas.content_brief import ContentBrief
from ..shared.schemas.trend_data import TrendData
from .tools.trend_scanner import scan_trends
from .tools.deduplicator import deduplicate_trends
from .tools.brief_generator import generate_brief
from ..db.session import async_session
from ..db.models.content_models import ContentBriefModel

logger = logging.getLogger("openclaw.agents.content_strategist")

# Cosine similarity threshold — topics above this are rejected as duplicates
DEDUP_THRESHOLD: float = 0.85


class ContentStrategistAgent(BaseAgent):
    """Agent 01: discovers trends, deduplicates, and generates ContentBriefs."""

    def __init__(self, config: AgentConfig) -> None:
        super().__init__(config)

        # Register all tools
        self.register_tool("trend_scanner",   scan_trends,       "Fetch raw trends")
        self.register_tool("deduplicator",    deduplicate_trends, "Qdrant dedup")
        self.register_tool("brief_generator", generate_brief,    "Claude briefing")

    async def run_cycle(self) -> None:
        # ── Step 1: Scan for trends ────────────────────────────────────────
        raw_trends: list[TrendData] = await self.run_tool(
            "trend_scanner",
            sources=["google_trends", "reddit", "ahrefs"],
        )
        logger.info("Trend scanner returned %d raw trends.", len(raw_trends))

        if not raw_trends:
            logger.info("No new trends detected — skipping cycle.")
            return

        # ── Step 2: Deduplicate against Qdrant ────────────────────────────
        novel_trends: list[TrendData] = await self.run_tool(
            "deduplicator",
            trends=raw_trends,
            threshold=DEDUP_THRESHOLD,
        )
        logger.info(
            "%d/%d trends passed dedup (threshold=%.2f).",
            len(novel_trends), len(raw_trends), DEDUP_THRESHOLD
        )

        if not novel_trends:
            logger.info("All trends were duplicates — skipping cycle.")
            return

        # ── Step 3: Generate ContentBriefs via Claude ─────────────────────
        briefs: list[ContentBrief] = []
        for trend in novel_trends:
            brief: ContentBrief = await self.run_tool(
                "brief_generator",
                trend=trend,
            )
            briefs.append(brief)

        logger.info("Generated %d ContentBriefs.", len(briefs))

        # ── Step 4 & 5: Persist and emit ──────────────────────────────────
        for brief in briefs:
            # Persist to PostgreSQL
            async with async_session() as session:
                session.add(ContentBriefModel.from_schema(brief))
                await session.commit()
                logger.info("Brief '%s' persisted to PostgreSQL.", brief.title)

            receivers = await self.emit(
                "content_briefs_ready",
                brief.redis_payload(),
            )
            logger.info(
                "Brief '%s' emitted → %d receiver(s).", brief.title, receivers
            )
