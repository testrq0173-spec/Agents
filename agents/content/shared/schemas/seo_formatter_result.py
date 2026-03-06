"""
SEOFormatterResult Schema
=========================
The validated output of the SEO Formatter tool used by Agent 02 (Blog Writer).
Contains the final article content plus a detailed SEO compliance report that
Agent 03 (Content Auditor) reads during its audit cycle.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class SEOPassFail(str, Enum):
    PASS    = "pass"
    WARN    = "warn"    # Within tolerance but not ideal
    FAIL    = "fail"


# ─────────────────────────────────────────────────────────────────────────────
# Sub-models: individual SEO checks
# ─────────────────────────────────────────────────────────────────────────────

class HeadingAudit(BaseModel):
    """Validates the H-tag structure of the generated HTML."""
    h1_count: int = Field(..., ge=0)
    h2_count: int = Field(..., ge=0)
    h3_count: int = Field(..., ge=0)
    h1_contains_focus_keyword: bool = False
    first_h2_within_first_200_words: bool = False
    status: SEOPassFail = SEOPassFail.FAIL

    @model_validator(mode="after")
    def evaluate_status(self) -> "HeadingAudit":
        if self.h1_count == 1 and self.h1_contains_focus_keyword:
            self.status = SEOPassFail.PASS
        elif self.h1_count == 1:
            self.status = SEOPassFail.WARN
        else:
            self.status = SEOPassFail.FAIL
        return self


class KeywordDensityAudit(BaseModel):
    """Measures focus-keyword density across the post body."""
    focus_keyword: str
    word_count: int = Field(..., ge=0)
    keyword_occurrences: int = Field(..., ge=0)
    density_pct: float = Field(..., ge=0.0)
    target_density_pct: float = Field(default=1.2, ge=0.5, le=2.0)
    keyword_in_first_100_words: bool = False
    keyword_in_last_100_words: bool = False
    status: SEOPassFail = SEOPassFail.FAIL

    @model_validator(mode="after")
    def evaluate_status(self) -> "KeywordDensityAudit":
        lo, hi = 0.5, 2.0
        if lo <= self.density_pct <= hi and self.keyword_in_first_100_words:
            self.status = SEOPassFail.PASS
        elif lo <= self.density_pct <= hi:
            self.status = SEOPassFail.WARN
        else:
            self.status = SEOPassFail.FAIL
        return self


class MetaTagAudit(BaseModel):
    """Validates <title> and <meta description> tags."""
    title_tag: str = Field(..., max_length=65)
    title_tag_length: int = Field(..., ge=0)
    title_contains_focus_keyword: bool = False
    meta_description: str = Field(..., max_length=160)
    meta_description_length: int = Field(..., ge=0)
    meta_contains_focus_keyword: bool = False
    canonical_url: Optional[HttpUrl] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image_url: Optional[HttpUrl] = None
    status: SEOPassFail = SEOPassFail.FAIL

    @model_validator(mode="after")
    def evaluate_status(self) -> "MetaTagAudit":
        title_ok = (
            50 <= self.title_tag_length <= 65
            and self.title_contains_focus_keyword
        )
        desc_ok = (
            120 <= self.meta_description_length <= 160
            and self.meta_contains_focus_keyword
        )
        if title_ok and desc_ok:
            self.status = SEOPassFail.PASS
        elif title_ok or desc_ok:
            self.status = SEOPassFail.WARN
        else:
            self.status = SEOPassFail.FAIL
        return self


class InternalLinkAudit(BaseModel):
    """Validates internal link injection results."""
    links_injected: int = Field(..., ge=0)
    target_slugs: list[str] = Field(default_factory=list)
    broken_links: list[str] = Field(default_factory=list)
    status: SEOPassFail = SEOPassFail.FAIL

    @model_validator(mode="after")
    def evaluate_status(self) -> "InternalLinkAudit":
        if self.links_injected >= 2 and not self.broken_links:
            self.status = SEOPassFail.PASS
        elif self.links_injected >= 1 and not self.broken_links:
            self.status = SEOPassFail.WARN
        else:
            self.status = SEOPassFail.FAIL
        return self


class ImageAudit(BaseModel):
    """Validates featured image and inline images."""
    featured_image_url: Optional[HttpUrl] = None
    featured_image_alt_text: Optional[str] = None
    featured_image_alt_contains_keyword: bool = False
    inline_image_count: int = Field(default=0, ge=0)
    all_images_have_alt: bool = False
    cloudinary_public_id: Optional[str] = None
    status: SEOPassFail = SEOPassFail.FAIL

    @model_validator(mode="after")
    def evaluate_status(self) -> "ImageAudit":
        if (
            self.featured_image_url
            and self.featured_image_alt_contains_keyword
            and self.all_images_have_alt
        ):
            self.status = SEOPassFail.PASS
        elif self.featured_image_url and self.all_images_have_alt:
            self.status = SEOPassFail.WARN
        else:
            self.status = SEOPassFail.FAIL
        return self


class ReadabilityAudit(BaseModel):
    """Basic readability metrics (Flesch-Kincaid)."""
    flesch_reading_ease: float = Field(..., ge=0.0, le=100.0)
    avg_sentence_length_words: float = Field(..., ge=0.0)
    avg_paragraph_length_words: float = Field(..., ge=0.0)
    passive_voice_pct: float = Field(..., ge=0.0, le=100.0)
    status: SEOPassFail = SEOPassFail.FAIL

    @model_validator(mode="after")
    def evaluate_status(self) -> "ReadabilityAudit":
        if self.flesch_reading_ease >= 60 and self.passive_voice_pct <= 15:
            self.status = SEOPassFail.PASS
        elif self.flesch_reading_ease >= 45:
            self.status = SEOPassFail.WARN
        else:
            self.status = SEOPassFail.FAIL
        return self


# ─────────────────────────────────────────────────────────────────────────────
# Main Schema
# ─────────────────────────────────────────────────────────────────────────────

class SEOFormatterResult(BaseModel):
    """
    Complete output of Agent 02's SEO Formatter tool.

    Wraps the final polished HTML article together with a structured
    compliance report across every SEO dimension. Agent 03 reads
    all sub-audits when computing its 7-dimension performance score.
    """

    # ── Identity ──────────────────────────────────────────────────────────
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    brief_id: uuid.UUID = Field(
        ...,
        description="FK → ContentBrief.id — ties this result back to its brief"
    )
    agent_run_id: str = Field(
        ...,
        description="Celery task ID or trace ID for this Agent 02 execution"
    )

    # ── Article content ───────────────────────────────────────────────────
    title: str = Field(..., min_length=10, max_length=120)
    html_content: str = Field(
        ...,
        description="Full, publication-ready HTML body (no <html>/<body> wrapper)"
    )
    word_count: int = Field(..., ge=1500, le=2500)
    reading_time_minutes: int = Field(
        ...,
        ge=1,
        description="Estimated reading time (word_count / 200 words-per-minute)"
    )

    # ── SEO sub-audits ────────────────────────────────────────────────────
    heading_audit:        HeadingAudit
    keyword_density_audit: KeywordDensityAudit
    meta_tag_audit:       MetaTagAudit
    internal_link_audit:  InternalLinkAudit
    image_audit:          ImageAudit
    readability_audit:    ReadabilityAudit

    # ── Aggregate pass/fail ───────────────────────────────────────────────
    overall_seo_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Weighted composite of the 6 sub-audit scores (0–100)"
    )
    passed_seo_check: bool = Field(
        default=False,
        description="True when overall_seo_score ≥ 70"
    )
    validation_errors: list[str] = Field(
        default_factory=list,
        description="Human-readable list of FAIL reasons; empty = clean"
    )

    # ── Publish metadata ──────────────────────────────────────────────────
    cms_post_id: Optional[str] = Field(
        None,
        description="ID assigned by the CMS (WordPress post ID, Webflow item ID, etc.)"
    )
    cms_post_url: Optional[HttpUrl] = None
    published_at: Optional[datetime] = None
    formatted_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def compute_overall_score(self) -> "SEOFormatterResult":
        """
        Weighted scoring across all sub-audits.
        Weights: heading=15, keyword=25, meta=25, links=10, image=10, readability=15
        """
        weights = {
            "heading_audit":         15,
            "keyword_density_audit": 25,
            "meta_tag_audit":        25,
            "internal_link_audit":   10,
            "image_audit":           10,
            "readability_audit":     15,
        }
        score_map = {
            SEOPassFail.PASS: 1.0,
            SEOPassFail.WARN: 0.5,
            SEOPassFail.FAIL: 0.0,
        }
        total_weight = sum(weights.values())
        raw_score = sum(
            score_map[getattr(self, field).status] * w
            for field, w in weights.items()
        )
        self.overall_seo_score = round((raw_score / total_weight) * 100, 2)
        self.passed_seo_check = self.overall_seo_score >= 70

        if not self.passed_seo_check:
            self.validation_errors = [
                f"{field}: {getattr(self, field).status.value}"
                for field in weights
                if getattr(self, field).status == SEOPassFail.FAIL
            ]
        return self

    @field_validator("reading_time_minutes", mode="before")
    @classmethod
    def auto_reading_time(cls, v, info) -> int:
        if v is None:
            wc = info.data.get("word_count", 0)
            return max(1, round(wc / 200))
        return v

    def redis_payload(self) -> dict:
        """Minimal payload emitted via the 'post_published' Redis event."""
        return {
            "result_id":         str(self.id),
            "brief_id":          str(self.brief_id),
            "cms_post_id":       self.cms_post_id,
            "cms_post_url":      str(self.cms_post_url) if self.cms_post_url else None,
            "overall_seo_score": self.overall_seo_score,
            "passed_seo_check":  self.passed_seo_check,
            "word_count":        self.word_count,
            "published_at":      self.published_at.isoformat() if self.published_at else None,
        }
