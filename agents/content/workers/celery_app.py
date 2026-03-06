"""
Celery Worker Entry-Point
=========================
Registers all three agent tasks as Celery tasks.
Run with:
    celery -A openclaw.agents.content.workers.celery_app worker --loglevel=info
    celery -A openclaw.agents.content.workers.celery_app beat --loglevel=info
"""

from __future__ import annotations
import asyncio
import logging
from celery import Celery
from celery.schedules import crontab

from ..config.settings import settings
from ..core.base_agent import AgentConfig, RedisConfig
from ..agent01_strategist.agent import ContentStrategistAgent
from ..agent02_writer.agent import BlogWriterAgent
from ..agent03_auditor.agent import ContentAuditorAgent

logger = logging.getLogger("openclaw.workers")

# ─────────────────────────────────────────────────────────────────────────────
# Celery application
# ─────────────────────────────────────────────────────────────────────────────

redis_url = (
    f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    if settings.REDIS_PASSWORD
    else f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
)

app = Celery(
    "openclaw_content",
    broker=redis_url,
    backend=redis_url,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ─────────────────────────────────────────────────────────────────────────────
# Beat schedule
# ─────────────────────────────────────────────────────────────────────────────

app.conf.beat_schedule = {
    # Agent 01: every 4 hours
    "agent01-content-strategist": {
        "task":     "openclaw.workers.run_agent01",
        "schedule": crontab(minute=0, hour="*/4"),
    },
    # Agent 02: every 2 hours (DB sweep for orphaned briefs)
    "agent02-blog-writer-sweep": {
        "task":     "openclaw.workers.run_agent02_sweep",
        "schedule": crontab(minute=30, hour="*/2"),
    },
    # Agent 03: weekly on Monday at 08:00 UTC
    "agent03-content-auditor-weekly": {
        "task":     "openclaw.workers.run_agent03",
        "schedule": crontab(minute=0, hour=8, day_of_week=1),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Celery task definitions
# ─────────────────────────────────────────────────────────────────────────────

def _make_redis_config() -> RedisConfig:
    return RedisConfig(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
    )


@app.task(name="openclaw.workers.run_agent01", bind=True, max_retries=3)
def run_agent01(self):
    """Celery task: runs one Agent 01 cycle synchronously."""
    config = AgentConfig(
        agent_name="ContentStrategist",
        redis=_make_redis_config(),
    )
    agent = ContentStrategistAgent(config)
    try:
        asyncio.run(agent.run_cycle())
    except Exception as exc:
        logger.exception("Agent 01 task failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@app.task(name="openclaw.workers.run_agent02_sweep", bind=True, max_retries=3)
def run_agent02_sweep(self):
    """Celery task: runs one Agent 02 sweep cycle."""
    config = AgentConfig(
        agent_name="BlogWriter",
        redis=_make_redis_config(),
    )
    agent = BlogWriterAgent(config)
    try:
        asyncio.run(agent.run_cycle())
    except Exception as exc:
        logger.exception("Agent 02 sweep task failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@app.task(name="openclaw.workers.run_agent02_brief", bind=True, max_retries=3)
def run_agent02_brief(self, brief_id: str):
    """Celery task: process a single ContentBrief — triggered by Redis event."""
    config = AgentConfig(
        agent_name="BlogWriter",
        redis=_make_redis_config(),
    )
    agent = BlogWriterAgent(config)
    # TODO: load brief from DB and call agent._process_brief(brief)
    logger.info("Processing brief_id=%s via Celery task", brief_id)


@app.task(name="openclaw.workers.run_agent03", bind=True, max_retries=3)
def run_agent03(self):
    """Celery task: runs Agent 03 weekly audit sweep."""
    config = AgentConfig(
        agent_name="ContentAuditor",
        redis=_make_redis_config(),
    )
    agent = ContentAuditorAgent(config)
    try:
        asyncio.run(agent.run_cycle())
    except Exception as exc:
        logger.exception("Agent 03 task failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)
