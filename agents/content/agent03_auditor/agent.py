"""
Agent 03 — Content Auditor
===========================
Runs weekly or immediately upon a 'post_published' event.

7-Dimension Scoring Model
--------------------------
1. Ranking Score       (Google Search Console avg. position)
2. CTR                 (Click-through rate)
3. Freshness           (Days since last edit vs. topic half-life)
4. Keyword Coverage    (Secondary keyword presence)
5. Engagement          (Time-on-page, bounce rate from GA4)
6. Backlinks           (Ahrefs backlink count)
7. SEO Score           (Stored SEOFormatterResult.overall_seo_score)

If the composite score < 60 → generate a Rewrite Brief and emit it
back to Agent 02 with priority=8 via 'content_briefs_ready'.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from ..core.base_agent import AgentConfig, BaseAgent
from ..shared.schemas.content_brief import ContentBrief, BriefStatus, ContentTone
from ..shared.schemas.seo_formatter_result import SEOFormatterResult
from .tools.performance_crawler import crawl_post_performance
from .tools.scoring_engine import compute_audit_score

logger = logging.getLogger("openclaw.agents.content_auditor")

REWRITE_THRESHOLD: float = 60.0
REWRITE_PRIORITY: int    = 8


class ContentAuditorAgent(BaseAgent):
    """Agent 03: scores published posts and triggers rewrites for underperformers."""

    def __init__(self, config: AgentConfig) -> None:
        super().__init__(config)

        self.register_tool("performance_crawler", crawl_post_performance, "GSC crawler")
        self.register_tool("scoring_engine",      compute_audit_score,   "7-dim scorer")

    async def handle_post_published(self, envelope: dict) -> None:
        """
        Immediately audit a newly published post.
        Triggered by the 'post_published' Redis event.
        """
        payload = envelope.get("payload", {})
        brief_id = payload.get("brief_id")
        cms_post_url = payload.get("cms_post_url")
        logger.info("On-publish audit triggered for brief_id=%s", brief_id)

        # NOTE: Give the CMS time to index before auditing on-publish
        # In production, schedule this 24 hours after publish via Celery beat.
        # await asyncio.sleep(86_400)

        await self._audit_post(brief_id=brief_id, cms_post_url=cms_post_url)

    async def _audit_post(
        self,
        brief_id: str,
        cms_post_url: str | None = None,
    ) -> float:
        """
        Full 7-dimension audit for a single post.

        Returns the composite score (0–100).
        Triggers a rewrite brief if score < REWRITE_THRESHOLD.
        """
        # Step 1: Crawl performance metrics
        performance_data: dict[str, Any] = await self.run_tool(
            "performance_crawler",
            brief_id=brief_id,
            post_url=cms_post_url,
        )

        # Step 2: Compute 7-dimension score
        score: float = await self.run_tool(
            "scoring_engine",
            performance_data=performance_data,
        )

        logger.info("Audit score for brief_id=%s: %.1f", brief_id, score)

        # TODO: Update ContentBrief.last_audit_score in PostgreSQL

        # Step 3: Trigger rewrite if below threshold
        if score < REWRITE_THRESHOLD:
            await self._emit_rewrite_brief(
                brief_id=brief_id,
                score=score,
                performance_data=performance_data,
            )

        return score

    async def _emit_rewrite_brief(
        self,
        brief_id: str,
        score: float,
        performance_data: dict[str, Any],
    ) -> None:
        """
        Build a Rewrite Brief and emit 'content_briefs_ready' with high priority.

        The rewrite brief is a new ContentBrief with:
          - parent_brief_id set to the original brief
          - status = REWRITE
          - priority = 8
          - rewrite_instructions generated from performance_data
        """
        logger.warning(
            "Score %.1f < %.1f — generating rewrite brief for brief_id=%s",
            score, REWRITE_THRESHOLD, brief_id
        )

        rewrite_instructions = self._build_rewrite_instructions(
            score=score,
            performance_data=performance_data,
        )

        # TODO: Load original brief from DB, clone it with incremented version
        # original_brief = await load_brief_from_db(brief_id)
        # rewrite_brief = original_brief.model_copy(update={
        #     "id": uuid.uuid4(),
        #     "parent_brief_id": original_brief.id,
        #     "version": original_brief.version + 1,
        #     "status": BriefStatus.REWRITE,
        #     "priority": REWRITE_PRIORITY,
        #     "rewrite_instructions": rewrite_instructions,
        # })
        # await save_brief_to_db(rewrite_brief)

        rewrite_payload = {
            "brief_id":              str(uuid.uuid4()),  # placeholder
            "parent_brief_id":       brief_id,
            "priority":              REWRITE_PRIORITY,
            "is_rewrite":            True,
            "audit_score":           score,
            "rewrite_instructions":  rewrite_instructions,
        }

        await self.emit("content_briefs_ready", rewrite_payload)
        logger.info(
            "Rewrite brief emitted with priority=%d for original brief_id=%s",
            REWRITE_PRIORITY, brief_id
        )

    def _build_rewrite_instructions(
        self,
        score: float,
        performance_data: dict[str, Any],
    ) -> str:
        """Generate natural-language rewrite instructions from audit data."""
        lines = [
            f"This post scored {score:.1f}/100 on the 7-dimension audit.",
            "Focus on the following improvements:",
        ]
        if performance_data.get("avg_position", 999) > 20:
            lines.append("- Improve keyword targeting; current avg. SERP position is poor.")
        if performance_data.get("ctr_pct", 0) < 2.0:
            lines.append("- Rewrite the meta title/description to improve CTR.")
        if performance_data.get("freshness_days", 0) > 90:
            lines.append("- Update statistics, examples, and publication date for freshness.")
        if performance_data.get("backlinks", 0) < 5:
            lines.append("- Add more linkable assets (data, original research, infographics).")
        return "\n".join(lines)

    async def run_cycle(self) -> None:
        """Weekly sweep: audit all published posts."""
        logger.info("Weekly audit sweep starting…")
        # TODO: Query PostgreSQL for all posts with status=PUBLISHED
        # posts = await load_published_posts()
        # for post in posts:
        #     await self._audit_post(brief_id=str(post.id), cms_post_url=post.cms_url)
        pass
