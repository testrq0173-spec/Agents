"""
Blog Writer tool using the NEW google-genai SDK.
"""

from __future__ import annotations
import logging
import re
from google import genai
from google.genai import types

from ...config.settings import settings
from ...shared.schemas.content_brief import ContentBrief

logger = logging.getLogger("openclaw.tools.llm_writer")

WRITER_SYSTEM_PROMPT = """You are an expert technical blog writer.
Output ONLY the HTML body content. Use <h1> for the title, <h2> for sections. 
No <html>/<body> tags. Do NOT use markdown.
"""

_client = None

def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client

async def write_post(brief: ContentBrief) -> str:
    client = get_client()
    
    prompt = f"Write a 1500 word blog post as HTML for: {brief.title}. Outline: {brief.outline}"

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=WRITER_SYSTEM_PROMPT,
                temperature=0.8
            )
        )
        html_content = response.text.strip()
        
        # Clean up any potential markdown fences
        html_content = re.sub(r"^```html?\s*", "", html_content, flags=re.MULTILINE)
        html_content = re.sub(r"```\s*$", "", html_content, flags=re.MULTILINE)
        
        return html_content
    except Exception as e:
        logger.error(f"Gemini writing failed: {e}")
        return f"<h1>{brief.title}</h1><p>Content generation failed.</p>"
