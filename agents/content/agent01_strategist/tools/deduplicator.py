"""
Qdrant deduplication tool for Agent 01.

Uses OpenAI text-embedding-3-small to embed each topic, then performs
a nearest-neighbour search in Qdrant.  Topics with cosine similarity
≥ threshold are rejected as duplicates.
"""

from __future__ import annotations
import re
from ...shared.schemas.trend_data import TrendData


async def deduplicate_trends(
    trends: list[TrendData],
    threshold: float = 0.85,
) -> list[TrendData]:
    """
    Filter out topics already covered in the Qdrant vector store.

    Steps for each trend:
      1. Embed topic text via OpenAI text-embedding-3-small
      2. Search Qdrant collection 'content_topics' for the nearest vector
      3. Reject if cosine similarity ≥ threshold
      4. Accept + upsert vector if the trend is novel

    Args:
        trends:    Raw list of TrendData from trend_scanner.
        threshold: Cosine similarity cut-off (default 0.85).

    Returns:
        Filtered list containing only novel trends.
    """
    # ── STUB ──────────────────────────────────────────────────────────────
    # TODO: Replace with real Qdrant + OpenAI client calls
    # from openai import AsyncOpenAI
    # from qdrant_client import AsyncQdrantClient
    # ...

    novel: list[TrendData] = []
    for trend in trends:
        # Simulate: all topics pass dedup in stub mode
        trend.novelty_score = 0.95
        trend.normalized_topic = re.sub(
            r"[^a-z0-9]+", "-", trend.topic.lower()
        ).strip("-")
        novel.append(trend)

    return novel
