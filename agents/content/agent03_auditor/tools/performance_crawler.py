"""Stub tools for Agent 03 — performance crawler and scoring engine."""

from __future__ import annotations
from typing import Any


async def crawl_post_performance(
    brief_id: str,
    post_url: str | None = None,
) -> dict[str, Any]:
    """
    Collect all 7 scoring dimensions from external APIs.

    Real implementation:
      - Google Search Console API → avg_position, ctr_pct, impressions, clicks
      - Google Analytics 4 API   → time_on_page_sec, bounce_rate_pct
      - Ahrefs API               → backlinks, referring_domains
      - Content DB               → last_edited_at (for freshness)
      - SEOFormatterResult DB    → seo_score (from Agent 02)

    Returns a flat dict consumed by compute_audit_score().
    """
    # STUB — returns simulated values
    return {
        "avg_position":      45.0,   # Google SERP avg position (lower is better)
        "ctr_pct":            1.2,   # Click-through rate %
        "impressions":        500,
        "clicks":               6,
        "time_on_page_sec":   180,
        "bounce_rate_pct":   72.0,
        "backlinks":            2,
        "referring_domains":    2,
        "freshness_days":      30,   # Days since last edit
        "seo_score":          68.0,  # From SEOFormatterResult
        "keyword_coverage":    0.6,  # % of secondary keywords present
    }


async def compute_audit_score(performance_data: dict[str, Any]) -> float:
    """
    Compute a 7-dimension composite audit score (0–100).

    Dimension weights:
      1. Ranking Score    (25%) — based on avg_position
      2. CTR              (20%) — based on ctr_pct
      3. Freshness        (10%) — based on freshness_days
      4. Keyword Coverage (10%) — based on keyword_coverage
      5. Engagement       (15%) — based on time_on_page and bounce_rate
      6. Backlinks        (10%) — based on backlink count
      7. SEO Score        (10%) — from SEOFormatterResult.overall_seo_score
    """

    def norm_position(pos: float) -> float:
        """Position 1 → 100 pts; position 100+ → 0 pts."""
        return max(0.0, min(100.0, (101 - pos)))

    def norm_ctr(ctr: float) -> float:
        """CTR 0% → 0pts; CTR ≥ 5% → 100pts (linear)."""
        return min(100.0, ctr * 20)

    def norm_freshness(days: int) -> float:
        """Fresh (≤30d) → 100pts; stale (>180d) → 0pts."""
        if days <= 30:   return 100.0
        if days >= 180:  return 0.0
        return 100.0 * (1 - (days - 30) / 150)

    def norm_engagement(time_sec: float, bounce_pct: float) -> float:
        time_score   = min(100.0, time_sec / 3)   # 300s → 100pts
        bounce_score = max(0.0, 100 - bounce_pct)
        return (time_score + bounce_score) / 2

    def norm_backlinks(bl: int) -> float:
        return min(100.0, bl * 5)  # 20 backlinks → 100pts

    d = performance_data
    dimensions = {
        "ranking":   (norm_position(d.get("avg_position", 100)),  0.25),
        "ctr":       (norm_ctr(d.get("ctr_pct", 0)),              0.20),
        "freshness": (norm_freshness(d.get("freshness_days", 365)), 0.10),
        "keywords":  (d.get("keyword_coverage", 0) * 100,          0.10),
        "engagement":(norm_engagement(
                          d.get("time_on_page_sec", 0),
                          d.get("bounce_rate_pct", 100)
                      ),                                            0.15),
        "backlinks": (norm_backlinks(d.get("backlinks", 0)),       0.10),
        "seo":       (d.get("seo_score", 0),                       0.10),
    }

    score: float = sum(score * weight for score, weight in dimensions.values())
    return round(score, 2)
