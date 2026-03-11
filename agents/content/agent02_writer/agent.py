"""
Agent 02 — Blog Writer
======================
Triggered by 'content_briefs_ready' Redis events or runs a 2-hour sweep.

Workflow
--------
1. Receive ContentBrief (via event or DB sweep of PENDING briefs)
2. llm_writer       → Claude writes 1,500–2,500 word HTML article
3. seo_formatter    → Validates H-tags, keyword density, meta tags
4. internal_linker  → Injects internal links from suggestions
5. image_handler    → DALL-E 3 generation + Cloudinary upload
6. cms_publisher    → POST to WordPress / Webflow REST API
7. emit             → Publish 'post_published' Redis event
"""

from __future__ import annotations

import logging
from typing import Any

from ..core.base_agent import AgentConfig, BaseAgent
from ..shared.schemas.content_brief import ContentBrief, BriefStatus
from ..shared.schemas.seo_formatter_result import SEOFormatterResult
from .tools.llm_writer import write_post
from .tools.seo_formatter import format_and_validate
from .tools.internal_linker import inject_internal_links
from .tools.image_handler import generate_and_upload_image
from .tools.cms_publisher import publish_to_cms
from ..db.session import async_session
from ..db.models.content_models import ContentBriefModel, PostModel
from sqlalchemy import update

logger = logging.getLogger("openclaw.agents.blog_writer")


class BlogWriterAgent(BaseAgent):
    """Agent 02: writes, formats, images, and publishes blog posts."""

    def __init__(self, config: AgentConfig) -> None:
        super().__init__(config)

        self.register_tool("llm_writer",       write_post,               "Gemini writer")
        self.register_tool("seo_formatter",    format_and_validate,      "SEO validator")
        self.register_tool("internal_linker",  inject_internal_links,    "Link injector")
        self.register_tool("image_handler",    generate_and_upload_image, "DALL-E + Cloudinary")
        self.register_tool("cms_publisher",    publish_to_cms,           "CMS REST publisher")

        self._listener_task: Optional[asyncio.Task] = None

    async def start_listening(self) -> None:
        """Start the Redis subscription loop for incoming briefs."""
        self._log.info("Agent 02 starting event listener for 'content_briefs_ready'...")
        await self.subscribe("content_briefs_ready", self.handle_brief_event)

    async def start(self, cycle_interval_seconds: float = 7200.0) -> None:
        """Override start to include the background event listener."""
        # Start the listener in the background BEFORE calling super().start() (which blocks)
        self._listener_task = asyncio.create_task(self.start_listening())
        await super().start(cycle_interval_seconds)

    async def stop(self) -> None:
        """Ensure listener is cancelled on stop."""
        if self._listener_task:
            self._listener_task.cancel()
        await super().stop()

    # ── Event handler — called by subscribe() ─────────────────────────────

    async def handle_brief_event(self, envelope: dict) -> None:
        """Process a single 'content_briefs_ready' event envelope."""
        payload = envelope.get("payload", {})
        brief_id: str = payload.get("brief_id", "unknown")
        self._log.info(f"Received brief event for brief_id={brief_id}")

        # For smoke tests/development: Allow passing the full brief in the payload
        # to avoid needing a real PostgreSQL connection.
        if "full_brief" in payload:
            self._log.info("Using full_brief from payload (Smoke Test mode)")
            brief_dict = payload["full_brief"]
            brief = ContentBrief(**brief_dict)
        else:
            # Load full ContentBrief from PostgreSQL by brief_id
            brief = await self._load_brief_from_db(brief_id)
            if not brief:
                self._log.warning(f"Brief {brief_id} not found in DB and no full_brief provided.")
                return

        try:
            await self._process_brief(brief)
        except Exception as e:
            self._log.error(f"Failed to process brief {brief_id}: {e}")

    async def _process_brief(self, brief: ContentBrief) -> SEOFormatterResult:
        """Full write → format → publish pipeline for one ContentBrief."""

        # Step 2: Write article
        raw_html: str = await self.run_tool("llm_writer", brief=brief)

        # Step 3: SEO format and validate
        seo_result: SEOFormatterResult = await self.run_tool(
            "seo_formatter",
            brief=brief,
            html_content=raw_html,
        )

        if not seo_result.passed_seo_check:
            logger.warning(
                "SEO check FAILED for brief '%s' (score=%.1f). Errors: %s",
                brief.title, seo_result.overall_seo_score, seo_result.validation_errors
            )
            # Optionally re-run writer with corrective prompt here

        # Step 4: Internal links
        linked_html: str = await self.run_tool(
            "internal_linker",
            html_content=seo_result.html_content,
            suggestions=brief.internal_link_suggestions,
        )
        seo_result.html_content = linked_html

        # Step 5: Featured image
        if brief.generate_featured_image:
            image_url, cloudinary_id = await self.run_tool(
                "image_handler",
                title=brief.title,
                prompt_hint=brief.image_prompt_hint,
            )
            seo_result.image_audit.featured_image_url = image_url
            seo_result.image_audit.cloudinary_public_id = cloudinary_id

        # Step 6: Publish to CMS
        for cms_target in brief.publish_targets:
            cms_post_id, cms_url = await self.run_tool(
                "cms_publisher",
                target=cms_target,
                seo_result=seo_result,
                brief=brief,
            )
            seo_result.cms_post_id  = cms_post_id
            seo_result.cms_post_url = cms_url

        # Step 7: Persist to PostgreSQL
        async with async_session() as session:
            # 7a. Save the Post record
            session.add(PostModel.from_schema(seo_result))
            
            # 7b. Update the Brief status to PUBLISHED
            stmt = (
                update(ContentBriefModel)
                .where(ContentBriefModel.id == brief.id)
                .values(status="published")
            )
            await session.execute(stmt)
            await session.commit()
            logger.info("Post and status persisted to PostgreSQL for: %s", brief.title)

        # Step 8: Emit event
        await self.emit("post_published", seo_result.redis_payload())
        logger.info("Post published: %s", seo_result.cms_post_url)

        return seo_result

    async def run_cycle(self) -> None:
        """2-hour sweep: pick up any PENDING briefs the event handler missed."""
        logger.info("Sweeping DB for PENDING briefs…")
        async with async_session() as session:
            from sqlalchemy import select
            stmt = select(ContentBriefModel).where(ContentBriefModel.status == "pending")
            result = await session.execute(stmt)
            pending_models = result.scalars().all()
            
            for model in pending_models:
                from ..shared.schemas.content_brief import ContentBrief
                brief = ContentBrief(
                    id=model.id,
                    version=model.version,
                    parent_brief_id=model.parent_brief_id,
                    title=model.title,
                    trend=model.trend_data,
                    seo=model.seo_directives,
                    outline=model.outline,
                    status=model.status,
                    priority=model.priority,
                    created_at=model.created_at,
                    updated_at=model.updated_at
                )
                await self._process_brief(brief)

    async def _load_brief_from_db(self, brief_id: str) -> Optional[ContentBrief]:
        """Load a single ContentBrief from PostgreSQL."""
        from uuid import UUID
        from sqlalchemy import select
        from ..shared.schemas.content_brief import ContentBrief
        
        try:
            async with async_session() as session:
                stmt = select(ContentBriefModel).where(ContentBriefModel.id == UUID(brief_id))
                result = await session.execute(stmt)
                model = result.scalar_one_or_none()
                if model:
                    return ContentBrief(
                        id=model.id,
                        version=model.version,
                        parent_brief_id=model.parent_brief_id,
                        title=model.title,
                        trend=model.trend_data,
                        seo=model.seo_directives,
                        outline=model.outline,
                        status=model.status,
                        priority=model.priority,
                        created_at=model.created_at,
                        updated_at=model.updated_at
                    )
        except Exception as e:
            self._log.error(f"Failed to load brief {brief_id} from DB: {e}")
        return None
