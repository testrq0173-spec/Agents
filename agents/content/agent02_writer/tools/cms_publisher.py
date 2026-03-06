"""
CMS Publisher tool for Agent 02.
Publishes the formatted post to WordPress or Webflow via REST API.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from ...config.settings import settings

if TYPE_CHECKING:
    from ...shared.schemas.seo_formatter_result import SEOFormatterResult
    from ...shared.schemas.content_brief import ContentBrief


async def publish_to_cms(
    target: str,
    seo_result: "SEOFormatterResult",
    brief: "ContentBrief",
) -> tuple[str, str]:
    """
    Publish the formatted post to the target CMS via REST API.

    WordPress real implementation:
        import httpx, base64
        credentials = base64.b64encode(
            f"{settings.WORDPRESS_USERNAME}:{settings.WORDPRESS_APP_PASSWORD}".encode()
        ).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.WORDPRESS_SITE_URL}/wp-json/wp/v2/posts",
                headers={"Authorization": f"Basic {credentials}"},
                json={
                    "title":   brief.title,
                    "content": seo_result.html_content,
                    "status":  "publish",
                    "slug":    brief.seo.slug,
                    "meta": {
                        "_yoast_wpseo_title":    seo_result.meta_tag_audit.title_tag,
                        "_yoast_wpseo_metadesc": seo_result.meta_tag_audit.meta_description,
                    },
                },
            )
        data = resp.json()
        return str(data["id"]), data["link"]

    Webflow real implementation:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.webflow.com/v2/collections/{settings.WEBFLOW_COLLECTION_ID}/items",
                headers={"Authorization": f"Bearer {settings.WEBFLOW_API_TOKEN}"},
                json={"fields": {"name": brief.title, "slug": brief.seo.slug, ...}},
            )

    Args:
        target: "wordpress" or "webflow"
        seo_result: Fully validated SEOFormatterResult
        brief: Source ContentBrief

    Returns:
        (cms_post_id, cms_post_url)
    """
    # STUB
    stub_id  = f"wp-post-{brief.id!s:.8}"
    stub_url = f"https://blog.openclaw.io/{brief.seo.slug}"
    return (stub_id, stub_url)
