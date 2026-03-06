"""
Image Handler tool for Agent 02.
Generates a featured image via DALL-E 3 and uploads it to Cloudinary.
"""

from __future__ import annotations
from typing import Optional

from ...config.settings import settings


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
            model=settings.DALLE_MODEL,
            prompt=f"{prompt_hint or title} — digital art, 16:9, vibrant",
            size="1792x1024",
            quality="hd",
            n=1,
        )
        image_url = response.data[0].url

        # Download and upload to Cloudinary
        import cloudinary.uploader, httpx
        async with httpx.AsyncClient() as http:
            img_bytes = (await http.get(image_url)).content
        result = cloudinary.uploader.upload(
            img_bytes,
            folder="openclaw/posts",
            resource_type="image",
        )
        return result["secure_url"], result["public_id"]

    Returns:
        (cloudinary_secure_url, cloudinary_public_id)
    """
    # STUB
    return (
        "https://res.cloudinary.com/openclaw/image/upload/v1/posts/stub-image.webp",
        "openclaw/posts/stub-image",
    )
