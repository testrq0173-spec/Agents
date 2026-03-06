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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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

    # Relationships
    brief = relationship("ContentBriefModel", back_populates="post")
