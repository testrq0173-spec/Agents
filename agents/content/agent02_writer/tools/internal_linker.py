"""Stub tools for Agent 02 — internal linker, image handler, CMS publisher."""

from __future__ import annotations
from typing import Optional
from ...shared.schemas.content_brief import InternalLinkSuggestion


async def inject_internal_links(
    html_content: str,
    suggestions: list[InternalLinkSuggestion],
) -> str:
    """
    Inject <a href> internal links into existing HTML text.

    Real implementation:
      1. Parse HTML with BeautifulSoup4
      2. For each suggestion, find the first occurrence of anchor_text in <p> tags
      3. Wrap with <a href="/blog/{target_slug}" rel="internal">{anchor_text}</a>
      4. Skip if already linked
    """
    # STUB: return content unchanged
    return html_content


async def generate_and_upload_image(
    title: str,
    prompt_hint: Optional[str] = None,
) -> tuple[str, str]:
    """
    Generate a featured image via DALL-E 3 and upload to Cloudinary.

    Real implementation:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.images.generate(
            model="dall-e-3",
            prompt=f"{prompt_hint or title} — digital art, 16:9, vibrant",
            size="1792x1024", quality="hd", n=1
        )
        image_url = response.data[0].url
        # Download bytes, upload to Cloudinary, return (secure_url, public_id)

    Returns:
        (cloudinary_secure_url, cloudinary_public_id)
    """
    # STUB
    return ("https://res.cloudinary.com/openclaw/stub-image.webp", "openclaw/stub-image")


async def publish_to_cms(
    target: str,
    seo_result,  # SEOFormatterResult
    brief,        # ContentBrief
) -> tuple[str, str]:
    """
    Publish the formatted post to the target CMS via REST API.

    Supported targets:
      - 'wordpress': POST /wp/v2/posts  (JWT auth)
      - 'webflow':   POST /v2/collections/{id}/items  (API token)

    Returns:
        (cms_post_id, cms_post_url)
    """
    # STUB
    stub_id  = "wp-post-12345"
    stub_url = f"https://blog.openclaw.io/stub-post"
    return (stub_id, stub_url)
