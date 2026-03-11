"""
OpenClaw Content Department — Application Settings
===================================================
Loads from environment variables (or .env via python-dotenv).
Pass all secrets via environment; NEVER hardcode them.

AI Stack:
  - Writing / Briefing : Google Gemini (google-generativeai)
  - Embeddings         : OpenAI text-embedding-3-small
  - Images             : OpenAI DALL-E 3
"""

from __future__ import annotations
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────
    APP_NAME: str       = "OpenClaw Content Department"
    ENVIRONMENT: str    = "development"
    DEBUG: bool         = False
    SECRET_KEY: str     = "change-me-in-production"

    # ── PostgreSQL ────────────────────────────────────────────────────────
    DATABASE_URL: str   = "postgresql+asyncpg://openclaw:password@localhost:5432/openclaw_content"

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_HOST: str     = "localhost"
    REDIS_PORT: int     = 6379
    REDIS_DB: int       = 0
    REDIS_PASSWORD: Optional[str] = None

    # ── Qdrant ────────────────────────────────────────────────────────────
    QDRANT_HOST: str    = "localhost"
    QDRANT_PORT: int    = 6333
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "content_topics"

    # ── AI APIs ───────────────────────────────────────────────────────────
    # Google Gemini — writing, briefing, auditing
    GEMINI_API_KEY: str             = ""
    GEMINI_MODEL: str               = "gemini-2.0-flash"  # This is the latest Flash available

    # OpenAI — embeddings (text-embedding-3-small) + DALL-E 3 images
    OPENAI_API_KEY: str             = ""
    EMBEDDING_MODEL: str            = "text-embedding-3-small"
    DALLE_MODEL: str                = "dall-e-3"

    # Unsplash — free alternative for thumbnails
    UNSPLASH_ACCESS_KEY: str        = ""

    # Freepik — AI image generation
    FREEPIK_API_KEY: str           = ""

    # ── Cloudinary ────────────────────────────────────────────────────────
    CLOUDINARY_CLOUD_NAME: str      = ""
    CLOUDINARY_API_KEY: str         = ""
    CLOUDINARY_API_SECRET: str      = ""

    # ── CMS ───────────────────────────────────────────────────────────────
    WORDPRESS_SITE_URL: str         = ""
    WORDPRESS_USERNAME: str         = ""
    WORDPRESS_APP_PASSWORD: str     = ""
    WEBFLOW_API_TOKEN: Optional[str] = None
    WEBFLOW_COLLECTION_ID: Optional[str] = None

    # ── Trend APIs ────────────────────────────────────────────────────────
    REDDIT_CLIENT_ID: str           = ""
    REDDIT_CLIENT_SECRET: str       = ""
    AHREFS_API_KEY: Optional[str]   = None

    # ── Google APIs ───────────────────────────────────────────────────────
    GOOGLE_SERVICE_ACCOUNT_JSON: Optional[str] = None  # Path to JSON key file
    GOOGLE_SEARCH_CONSOLE_SITE_URL: str = ""

    # ── Agent Timings ─────────────────────────────────────────────────────
    AGENT01_CYCLE_HOURS: float    = 4.0
    AGENT02_CYCLE_HOURS: float    = 2.0
    AGENT03_CYCLE_DAYS: float     = 7.0
    AGENT_HEARTBEAT_SECONDS: float = 30.0
    DEDUP_SIMILARITY_THRESHOLD: float = 0.85
    AUDIT_REWRITE_THRESHOLD: float    = 60.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
