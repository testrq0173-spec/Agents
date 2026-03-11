"""
PostgreSQL Models for OpenClaw Content Department
=================================================
Using SQLAlchemy 2.0 with Asyncpg.
"""

from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ...shared.schemas.content_brief import ContentBrief
    from ...shared.schemas.seo_formatter_result import SEOFormatterResult


class Base(DeclarativeBase):
    pass


class ContentBriefModel(Base):
    """
    SQLAlchemy model for the ContentBrief schema.
    Stores the full lifecycle from discovery to rewrite.
    """
    __tablename__ = "content_briefs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_brief_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("content_briefs.id"), nullable=True)
    
    # Core Data
    topic: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True) # pending, in_review, published, rewrite
    priority: Mapped[int] = mapped_column(Integer, default=5)
    
    # Complex JSON fields (storing Pydantic sub-models)
    trend_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    seo_directives: Mapped[dict[str, Any]] = mapped_column(JSON)
    outline: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    
    # Audit Feedback
    last_audit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rewrite_instructions: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def from_schema(cls, brief: "ContentBrief") -> "ContentBriefModel":
        """Convert Pydantic ContentBrief to SQLAlchemy model."""
        return cls(
            id=brief.id,
            version=brief.version,
            parent_brief_id=brief.parent_brief_id,
            topic=brief.trend.topic,
            title=brief.title,
            status=brief.status.value,
            priority=brief.priority,
            # Use JSON-safe dumps to avoid datetime serialization errors
            trend_data=brief.trend.model_dump(mode="json"),
            seo_directives=brief.seo.model_dump(mode="json"),
            outline=[section.model_dump(mode="json") for section in brief.outline],
        )

    # Relationships
    post = relationship("PostModel", back_populates="brief", uselist=False)


class PostModel(Base):
    """
    SQLAlchemy model for published blog posts.
    """
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brief_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_briefs.id"), unique=True)
    
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    cms_post_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cms_post_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Content storage (HTML)
    html_content: Mapped[str] = mapped_column(String)
    word_count: Mapped[int] = mapped_column(Integer)
    
    # Evaluation Data
    overall_seo_score: Mapped[float] = mapped_column(Float)
    full_audit_results: Mapped[dict[str, Any]] = mapped_column(JSON) # SEOFormatterResult stored as JSON
    
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @classmethod
    def from_schema(cls, result: "SEOFormatterResult") -> "PostModel":
        """Convert Pydantic SEOFormatterResult to SQLAlchemy model."""
        # Extract slug from URL or use result ID
        slug_val = str(result.id)
        if result.cms_post_url:
            # cms_post_url can be HttpUrl or str depending on assignment time
            if hasattr(result.cms_post_url, "path"):
                path = result.cms_post_url.path or ""
            else:
                from urllib.parse import urlparse
                path = urlparse(str(result.cms_post_url)).path or ""
            slug_val = path.strip("/").split("/")[-1] or str(result.id)

        return cls(
            id=result.id,
            brief_id=result.brief_id,
            slug=slug_val,
            cms_post_id=result.cms_post_id,
            cms_post_url=str(result.cms_post_url) if result.cms_post_url else None,
            html_content=result.html_content,
            word_count=result.word_count,
            overall_seo_score=result.overall_seo_score,
            full_audit_results=result.model_dump(mode="json"),
            published_at=result.published_at,
        )

    # Relationships
    brief = relationship("ContentBriefModel", back_populates="post")
