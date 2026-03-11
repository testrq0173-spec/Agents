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
    """
    import os
    import httpx
    import base64
    import logging

    logger = logging.getLogger("openclaw.cms_publisher")

    # 1. ALWAYS generate the local preview first (so the dashboard link works)
    preview_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api", "previews"))
    os.makedirs(preview_dir, exist_ok=True)
    
    filename = f"{brief.seo.slug}.html"
    filepath = os.path.join(preview_dir, filename)
    
    featured_img_html = ""
    if seo_result.image_audit.featured_image_url:
        featured_img_html = f'<img src="{seo_result.image_audit.featured_image_url}" alt="{brief.title}">'

    preview_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{brief.title}</title>
    <style>
        body {{ font-family: Inter, system-ui; line-height: 1.6; max-width: 800px; margin: 2rem auto; padding: 0 1rem; color: #334155; }}
        h1 {{ color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem; }}
        h2 {{ color: #1e293b; margin-top: 2rem; }}
        img {{ width: 100%; border-radius: 0.5rem; margin: 1.5rem 0; }}
        .meta {{ background: #f8fafc; padding: 1rem; border-radius: 0.5rem; margin-bottom: 2rem; font-size: 0.9rem; }}
    </style>
</head>
<body>
    <div class="meta">
        <strong>SEO Meta Title:</strong> {seo_result.meta_tag_audit.title_tag or brief.seo.meta_title}<br>
        <strong>Meta Description:</strong> {seo_result.meta_tag_audit.meta_description or brief.seo.meta_description}<br>
        <strong>Focus Keyword:</strong> {brief.seo.focus_keyword}
    </div>
    {featured_img_html}
    {seo_result.html_content}
</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(preview_html)

    # 2. Handle WordPress Publication
    if target.lower() == "wordpress":
        if not settings.WORDPRESS_SITE_URL or not settings.WORDPRESS_APP_PASSWORD:
            logger.warning("WordPress credentials missing in .env. Skipping CMS post.")
        else:
            try:
                logger.info(f"Publishing to WordPress: {settings.WORDPRESS_SITE_URL}")
                
                # Setup Auth
                user_pass = f"{settings.WORDPRESS_USERNAME}:{settings.WORDPRESS_APP_PASSWORD}"
                credentials = base64.b64encode(user_pass.encode()).decode()
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    # 2a. Optional: Upload Featured Image to WordPress Media Library
                    featured_media_id = None
                    if seo_result.image_audit.featured_image_url:
                        try:
                            img_resp = await client.get(str(seo_result.image_audit.featured_image_url))
                            if img_resp.status_code == 200:
                                media_resp = await client.post(
                                    f"{settings.WORDPRESS_SITE_URL.rstrip('/')}/wp-json/wp/v2/media",
                                    headers={
                                        "Authorization": f"Basic {credentials}",
                                        "Content-Disposition": f'attachment; filename="{brief.seo.slug}.jpg"',
                                        "Content-Type": "image/jpeg",
                                    },
                                    content=img_resp.content,
                                )
                                if media_resp.status_code in [200, 201]:
                                    featured_media_id = media_resp.json().get("id")
                                    logger.info(f"Uploaded featured image to WordPress. Media ID: {featured_media_id}")
                        except Exception as img_err:
                            logger.error(f"Failed to upload media to WordPress: {img_err}")

                    # 2b. Create Post
                    post_payload = {
                        "title":   brief.title,
                        "content": seo_result.html_content,
                        "status":  "publish",
                        "slug":    brief.seo.slug,
                    }
                    if featured_media_id:
                        post_payload["featured_media"] = featured_media_id

                    resp = await client.post(
                        f"{settings.WORDPRESS_SITE_URL.rstrip('/')}/wp-json/wp/v2/posts",
                        headers={"Authorization": f"Basic {credentials}"},
                        json=post_payload,
                    )
                    
                    if resp.status_code in [200, 201]:
                        data = resp.json()
                        cms_id = str(data.get("id"))
                        cms_url = data.get("link")
                        logger.info(f"Successfully published to WordPress! ID: {cms_id}")
                        return (cms_id, cms_url)
                    else:
                        logger.error(f"WordPress API error ({resp.status_code}): {resp.text}")
            except Exception as e:
                logger.error(f"Failed to publish to WordPress: {e}")

    # Fallback to local preview URL
    stub_id  = f"local-post-{brief.id!s:.8}"
    stub_url = f"http://localhost:8000/previews/{filename}"
    return (stub_id, stub_url)

