"""Vision analyzer — image → observations via Claude Sonnet."""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

import structlog
from anthropic import Anthropic

from src.config.settings import settings
from src.engine.supabase_client import get_client

logger = structlog.get_logger(__name__)


async def analyze_image(
    image_bytes: bytes,
    context: str = "",
    implementation: str = "",
) -> str:
    """Analyze a single image using Claude Sonnet vision.

    Args:
        image_bytes: Raw image bytes (JPEG/PNG/WebP)
        context: Optional context about the visit type

    Returns:
        Text description of what's visible in the image.
    """
    start = time.time()
    logger.info("vision_analyze_start", size=len(image_bytes), context=context[:50] if context else "")

    try:
        # Load vision prompt from implementation config
        from src.engine.config_loader import get_vision_prompt
        vision_prompt = await get_vision_prompt(implementation)

        client = Anthropic(api_key=settings.anthropic_api_key, timeout=90.0)

        # Encode image to base64
        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        # Detect media type from magic bytes
        media_type = _detect_media_type(image_bytes)

        # Build user message with optional context
        user_text = "Analiza esta imagen capturada durante una visita de campo."
        if context:
            user_text += f"\nContexto: {context}"

        # Use Haiku for Vision (60% cheaper than Sonnet, sufficient for image description)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=vision_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": user_text},
                    ],
                }
            ],
        )

        text = message.content[0].text.strip()
        elapsed_ms = int((time.time() - start) * 1000)
        logger.info("vision_analyze_complete", chars=len(text), elapsed_ms=elapsed_ms)
        return text

    except Exception as e:
        logger.error("vision_analyze_failed", error=str(e))
        return f"[Error analizando imagen: {e}]"


async def analyze_images_batch(
    images: list[bytes],
    context: str = "",
    implementation: str = "",
) -> list[str]:
    """Analyze multiple images in parallel using asyncio.gather."""
    start = time.time()
    logger.info("vision_batch_start", count=len(images))

    tasks = [analyze_image(img, context, implementation) for img in images]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    descriptions: list[str] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("vision_batch_item_failed", index=i, error=str(result))
            descriptions.append(f"[Error en imagen {i+1}: {result}]")
        else:
            descriptions.append(result)

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info("vision_batch_complete", count=len(descriptions), elapsed_ms=elapsed_ms)
    return descriptions


async def analyze_from_storage(
    storage_path: str,
    context: str = "",
    implementation: str = "",
) -> str:
    """Download image from Supabase Storage and analyze it."""
    sb = get_client()
    image_bytes = sb.storage.from_("media").download(storage_path)
    return await analyze_image(image_bytes, context, implementation)


def _detect_media_type(image_bytes: bytes) -> str:
    """Detect image media type from magic bytes."""
    if image_bytes[:2] == b"\xff\xd8":
        return "image/jpeg"
    elif image_bytes[:4] == b"\x89PNG":
        return "image/png"
    elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"  # Default fallback
