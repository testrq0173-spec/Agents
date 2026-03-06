"""
Brief Generator tool using the NEW google-genai SDK.
Generates a structured ContentBrief from a trending topic.
"""

from __future__ import annotations
import logging
import json
import os
from typing import TYPE_CHECKING, Optional

from google import genai
from google.genai import types

from ...config.settings import settings

if TYPE_CHECKING:
    from ...shared.schemas.trend_data import TrendData
    from ...shared.schemas.content_brief import (
        ContentBrief, SEODirectives, OutlineSection, ContentTone, TargetAudience,
        InternalLinkSuggestion,
    )

logger = logging.getLogger("openclaw.tools.brief_generator")

# --- System Prompt ---
SYSTEM_PROMPT = """You are an expert Content Strategist. 
Your task is to turn a trending topic into a detailed SEO Content Brief.
You MUST respond with valid JSON that matches the ContentBrief schema EXACTLY.
Values for 'tone' and 'target_audience' MUST be chosen from the provided lists below.
"""

USER_PROMPT_TEMPLATE = """Generate a ContentBrief for this trending topic:
TOPIC: {topic}
SOURCE: {source}
TREND SCORE: {score}

The brief must include:
1. A catchy SEO Title
2. A unique slug
3. A meta title and description
4. A 5-8 section outline with word counts
5. Secondary keywords
6. Content tone and target audience

JSON Schema requirement:
{{
  "title": str,
  "seo": {{ "slug": str, "focus_keyword": str, "meta_title": str, "meta_description": str, "secondary_keywords": list[str] }},
  "outline": [ {{ "heading": str, "suggested_word_count": int, "key_points": list[str] }} ],
  "tone": "educational" | "conversational" | "authoritative" | "opinion_piece" | "how_to" | "listicle" | "case_study",
  "target_audience": "developers" | "business_owners" | "marketers" | "general_public" | "enterprise"
}}
"""

_client = None

def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client

async def generate_brief(trend: "TrendData") -> "ContentBrief":
    """Calls Gemini to generate a ContentBrief JSON."""
    from ...shared.schemas.content_brief import ContentBrief # Local import to avoid circular

    client = get_client()
    prompt = USER_PROMPT_TEMPLATE.format(
        topic=trend.topic,
        source=trend.primary_source.value,
        score=trend.trend_score
    )

    try:
        # Using the new SDK call style
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.7
            )
        )
        
        # Parse result
        response_text = response.text.strip()
        logger.info(f"Gemini response: {response_text}")
        brief_dict = json.loads(response_text)
        
        # Inject IDs and Trend lineage
        from uuid import uuid4
        brief_dict["id"] = str(uuid4())
        brief_dict["trend"] = trend.model_dump()
        
        return ContentBrief(**brief_dict)

    except Exception as e:
        logger.error(f"Gemini generation failed: {e}. Using fallback.")
        # Fallback logic remains same as before...
        from ...shared.schemas.content_brief import ContentBrief, SEODirectives, ContentTone, TargetAudience
        return ContentBrief(
            title=f"The Complete Guide to {trend.topic}",
            seo=SEODirectives(
                slug=trend.topic.lower().replace(" ", "-"),
                focus_keyword=trend.topic,
                meta_title=f"{trend.topic} — OpenClaw Guide",
                meta_description=f"Learn everything about {trend.topic}: best practices and expert tips.",
                secondary_keywords=["AI agents", "production ML", "autonomous systems"]
            ),
            outline=[],
            tone=ContentTone.EDUCATIONAL,
            target_audience=TargetAudience.DEVELOPERS,
            priority=7
        )
