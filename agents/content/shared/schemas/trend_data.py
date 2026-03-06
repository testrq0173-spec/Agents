"""
TrendData Schema
================
Captures a single trending topic discovered by Agent 01 (Content Strategist).
Supports signals from multiple sources: Google Trends, Reddit, Ahrefs/SEMrush.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class TrendSource(str, Enum):
    """Enumeration of all supported trend-signal sources."""
    GOOGLE_TRENDS = "google_trends"
    REDDIT = "reddit"
    AHREFS = "ahrefs"
    SEMRUSH = "semrush"
    TWITTER = "twitter"
    MANUAL = "manual"


class RedditSignal(BaseModel):
    """Reddit-specific engagement metrics."""
    subreddit: str = Field(..., description="e.g. 'r/technology'")
    post_count_24h: int = Field(..., ge=0)
    average_upvotes: float = Field(..., ge=0.0)
    top_post_url: Optional[HttpUrl] = None


class GoogleTrendsSignal(BaseModel):
    """Google Trends-specific data points."""
    interest_over_time: list[int] = Field(
        default_factory=list,
        description="Relative interest values (0–100) for the last 7 days"
    )
    related_queries: list[str] = Field(default_factory=list)
    geo: str = Field(default="US", description="ISO 3166-1 alpha-2 country code")
    breakout: bool = Field(
        default=False,
        description="True when search interest increased >5000% in 24h"
    )


class AhrefsSignal(BaseModel):
    """Keyword metrics from Ahrefs / SEMrush."""
    monthly_search_volume: Optional[int] = Field(None, ge=0)
    keyword_difficulty: Optional[float] = Field(None, ge=0.0, le=100.0)
    cost_per_click_usd: Optional[float] = Field(None, ge=0.0)
    top_ranking_url: Optional[HttpUrl] = None


class TrendData(BaseModel):
    """
    Full representation of one trending topic as discovered by Agent 01.

    This is the primary handoff document from the trend-scanner tool
    to the brief-generator tool within Agent 01.
    """

    # ── Core identity ──────────────────────────────────────────────────────
    topic: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Plain-text trend keyword or topic phrase"
    )
    normalized_topic: Optional[str] = Field(
        None,
        description="Lowercased, slug-safe version used for deduplication"
    )
    language: str = Field(default="en", description="ISO 639-1 language code")

    # ── Source signals ─────────────────────────────────────────────────────
    primary_source: TrendSource = Field(
        ...,
        description="The source that first surfaced this trend"
    )
    google_trends: Optional[GoogleTrendsSignal] = None
    reddit: Optional[RedditSignal] = None
    ahrefs: Optional[AhrefsSignal] = None

    # ── Scoring ────────────────────────────────────────────────────────────
    trend_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description=(
            "Composite score (0–100) aggregated from all available sources. "
            "Scores ≥ 70 are considered high-priority."
        )
    )
    novelty_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Cosine-distance complement from Qdrant: 1.0 = completely new, "
            "0.0 = already covered. Topics with novelty < 0.15 are rejected."
        )
    )

    # ── Temporal ───────────────────────────────────────────────────────────
    detected_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when Agent 01 first surfaced this trend"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Trend is stale after this UTC timestamp (usually +72h)"
    )

    # ── Qdrant deduplication ───────────────────────────────────────────────
    qdrant_vector_id: Optional[str] = Field(
        None,
        description="UUID of the stored vector in Qdrant after deduplication check"
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model used to generate the topic vector"
    )

    @field_validator("normalized_topic", mode="before")
    @classmethod
    def auto_normalize(cls, v: Optional[str], info) -> str:
        """Auto-derive normalized_topic from topic if not explicitly set."""
        if v is None:
            raw: str = info.data.get("topic", "")
            import re
            return re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "topic": "LLM Agents in Production",
                "primary_source": "google_trends",
                "trend_score": 87.5,
                "novelty_score": 0.92,
                "google_trends": {
                    "interest_over_time": [40, 55, 72, 80, 95, 100, 98],
                    "related_queries": ["Claude agents", "AutoGen", "LangGraph"],
                    "geo": "US",
                    "breakout": True
                }
            }
        }
    }
