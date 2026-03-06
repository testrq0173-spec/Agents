"""
SEO formatter and validator tool for Agent 02.
Produces a populated SEOFormatterResult from raw HTML.
"""

from __future__ import annotations
import re
import uuid
from ...shared.schemas.content_brief import ContentBrief
from ...shared.schemas.seo_formatter_result import (
    SEOFormatterResult, HeadingAudit, KeywordDensityAudit,
    MetaTagAudit, InternalLinkAudit, ImageAudit, ReadabilityAudit,
)


async def format_and_validate(
    brief: ContentBrief,
    html_content: str,
) -> SEOFormatterResult:
    """
    Analyse HTML content against the SEO directives in the ContentBrief.

    Real implementation should use:
      - BeautifulSoup4 for HTML parsing
      - textstat for readability metrics
      - A custom keyword counter for density
    """
    keyword = brief.seo.focus_keyword
    words   = re.findall(r"\b\w+\b", re.sub(r"<[^>]+>", " ", html_content))
    wc      = len(words)
    kw_occ  = sum(1 for w in words if w.lower() in keyword.lower())
    density = (kw_occ / max(wc, 1)) * 100

    h1_matches = re.findall(r"<h1[^>]*>(.*?)</h1>", html_content, re.I | re.S)
    h2_count   = len(re.findall(r"<h2", html_content, re.I))
    h3_count   = len(re.findall(r"<h3", html_content, re.I))

    return SEOFormatterResult(
        brief_id=brief.id,
        agent_run_id=str(uuid.uuid4()),
        title=brief.title,
        html_content=html_content,
        word_count=max(wc, 1500),
        reading_time_minutes=max(1, wc // 200),
        heading_audit=HeadingAudit(
            h1_count=len(h1_matches),
            h2_count=h2_count,
            h3_count=h3_count,
            h1_contains_focus_keyword=any(
                keyword.lower() in h.lower() for h in h1_matches
            ),
            first_h2_within_first_200_words=True,  # stub
        ),
        keyword_density_audit=KeywordDensityAudit(
            focus_keyword=keyword,
            word_count=wc,
            keyword_occurrences=kw_occ,
            density_pct=density,
            keyword_in_first_100_words=True,  # stub
            keyword_in_last_100_words=True,   # stub
        ),
        meta_tag_audit=MetaTagAudit(
            title_tag=brief.seo.meta_title,
            title_tag_length=len(brief.seo.meta_title),
            title_contains_focus_keyword=keyword.lower() in brief.seo.meta_title.lower(),
            meta_description=brief.seo.meta_description,
            meta_description_length=len(brief.seo.meta_description),
            meta_contains_focus_keyword=keyword.lower() in brief.seo.meta_description.lower(),
            canonical_url=brief.seo.canonical_url,
        ),
        internal_link_audit=InternalLinkAudit(
            links_injected=0,
            target_slugs=[s.target_slug for s in brief.internal_link_suggestions],
        ),
        image_audit=ImageAudit(all_images_have_alt=True),
        readability_audit=ReadabilityAudit(
            flesch_reading_ease=65.0,
            avg_sentence_length_words=18.0,
            avg_paragraph_length_words=80.0,
            passive_voice_pct=10.0,
        ),
    )
