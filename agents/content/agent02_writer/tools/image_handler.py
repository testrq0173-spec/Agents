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
    """

    import httpx
    import cloudinary.uploader
    import base64
    
    # 1. Generate image via Freepik AI
    freepik_url = "https://api.freepik.com/v1/ai/text-to-image"
    headers = {
        "x-freepik-api-key": settings.FREEPIK_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": f"{prompt_hint or title} — professional digital art, 16:9, high resolution, vibrant colors",
        "num_images": 1,
        "image": {
            "size": "landscape_16_9"
        },
        "styling": {
            "style": "digital-art"
        }
    }
    
    async with httpx.AsyncClient() as http:
        resp = await http.post(freepik_url, headers=headers, json=payload, timeout=60.0)
        if resp.status_code != 200:
            # Fallback to Unsplash if Freepik fails or key is missing
            if settings.UNSPLASH_ACCESS_KEY:
                return await _fallback_to_unsplash(title, prompt_hint)
            raise Exception(f"Freepik AI error ({resp.status_code}): {resp.text}")
        
        data = resp.json()
        image_data = data.get("data", [])[0]
        
        # Freepik usually returns base64 for fast generation
        if "base64" in image_data:
            img_bytes = base64.b64decode(image_data["base64"])
        elif "url" in image_data:
            img_resp = await http.get(image_data["url"])
            img_bytes = img_resp.content
        else:
            raise Exception("No image data found in Freepik response.")

    # 2. Upload to Cloudinary
    result = cloudinary.uploader.upload(
        img_bytes,
        folder="openclaw/posts",
        resource_type="image",
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    )
    
    return result["secure_url"], result["public_id"]

async def _fallback_to_unsplash(title: str, prompt_hint: Optional[str]) -> tuple[str, str]:
    """Fallback search if Freepik is unavailable."""
    import httpx
    import cloudinary.uploader
    from ...config.settings import settings

    search_query = prompt_hint or title
    unsplash_url = "https://api.unsplash.com/search/photos"
    headers = {"Authorization": f"Client-ID {settings.UNSPLASH_ACCESS_KEY}"}
    params = {"query": search_query, "per_page": 1, "orientation": "landscape"}
    
    async with httpx.AsyncClient() as http:
        resp = await http.get(unsplash_url, headers=headers, params=params)
        data = resp.json()
        if not data.get("results"):
            params["query"] = "technology"
            resp = await http.get(unsplash_url, headers=headers, params=params)
            data = resp.json()
        
        image_url = data["results"][0]["urls"]["regular"]
        img_resp = await http.get(image_url)
        img_bytes = img_resp.content

    result = cloudinary.uploader.upload(
        img_bytes,
        folder="openclaw/posts",
        resource_type="image",
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    )
    return result["secure_url"], result["public_id"]
