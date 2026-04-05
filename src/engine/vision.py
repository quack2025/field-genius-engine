"""Vision analyzer — image → observations via Claude Vision.

Supports two strategies per implementation:
  - sonnet_only: Always use Sonnet (best quality, higher cost)
  - tiered: Haiku first → escalate to Sonnet if description is too shallow
"""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

import structlog
from anthropic import AsyncAnthropic

from src.config.settings import settings
from src.engine.supabase_client import get_client

logger = structlog.get_logger(__name__)

SONNET = "claude-sonnet-4-20250514"
HAIKU = "claude-haiku-4-5-20251001"

# Thresholds for tiered escalation
TIERED_MIN_CHARS = 200        # Haiku response shorter than this → escalate
TIERED_MIN_ENTITIES = 2       # Fewer distinct product/brand mentions → escalate
TIERED_VAGUE_PHRASES = [      # Generic phrases that indicate shallow analysis
    "se observa", "se puede ver", "la imagen muestra",
    "varios productos", "different products", "some items",
]

# Singleton async client
_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=90.0)
    return _client


async def analyze_image(
    image_bytes: bytes,
    context: str = "",
    implementation: str = "",
    max_retries: int = 2,
) -> str:
    """Analyze a single image using the implementation's vision strategy.

    Strategy is read from the implementation config:
      - sonnet_only: direct Sonnet call
      - tiered: Haiku first, escalate to Sonnet if shallow
    """
    from src.engine.config_loader import get_vision_strategy
    strategy = await get_vision_strategy(implementation) if implementation else "sonnet_only"

    if strategy == "tiered":
        return await _analyze_tiered(image_bytes, context, implementation, max_retries)
    return await _analyze_with_model(image_bytes, context, implementation, SONNET, max_retries)


async def _analyze_tiered(
    image_bytes: bytes,
    context: str,
    implementation: str,
    max_retries: int,
) -> str:
    """Tiered strategy: Haiku first → escalate to Sonnet if quality is low."""
    start = time.time()

    # Step 1: Try Haiku (fast + cheap)
    haiku_result = await _analyze_with_model(image_bytes, context, implementation, HAIKU, max_retries)

    # Step 2: Evaluate quality
    should_escalate, reason = _should_escalate(haiku_result)

    if not should_escalate:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.info(
            "vision_tiered_haiku_sufficient",
            chars=len(haiku_result),
            elapsed_ms=elapsed_ms,
            implementation=implementation,
        )
        return haiku_result

    # Step 3: Escalate to Sonnet
    logger.info(
        "vision_tiered_escalating",
        reason=reason,
        haiku_chars=len(haiku_result),
        implementation=implementation,
    )
    sonnet_result = await _analyze_with_model(image_bytes, context, implementation, SONNET, max_retries)

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(
        "vision_tiered_escalated",
        haiku_chars=len(haiku_result),
        sonnet_chars=len(sonnet_result),
        escalation_reason=reason,
        elapsed_ms=elapsed_ms,
        implementation=implementation,
    )
    return sonnet_result


def _should_escalate(haiku_result: str) -> tuple[bool, str]:
    """Decide if Haiku result is too shallow and needs Sonnet escalation."""
    if haiku_result.startswith("[Error"):
        return True, "haiku_error"

    if len(haiku_result) < TIERED_MIN_CHARS:
        return True, f"too_short_{len(haiku_result)}_chars"

    # Check for vague/generic descriptions
    lower = haiku_result.lower()
    vague_count = sum(1 for phrase in TIERED_VAGUE_PHRASES if phrase in lower)
    unique_words = len(set(lower.split()))
    if vague_count >= 3 and unique_words < 80:
        return True, f"vague_{vague_count}_phrases"

    # Check if it mentions specific brands/prices (sign of useful detail)
    has_numbers = any(c.isdigit() for c in haiku_result)
    has_bold = "**" in haiku_result
    if not has_numbers and not has_bold and len(haiku_result) < 400:
        return True, "no_specifics"

    return False, ""


async def _analyze_with_model(
    image_bytes: bytes,
    context: str,
    implementation: str,
    model: str,
    max_retries: int,
) -> str:
    """Core image analysis using a specific Claude model."""
    start = time.time()
    model_label = "sonnet" if "sonnet" in model else "haiku"
    logger.info("vision_analyze_start", model=model_label, size=len(image_bytes), context=context[:50] if context else "")

    from src.engine.config_loader import get_vision_prompt
    vision_prompt = await get_vision_prompt(implementation)

    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    media_type = _detect_media_type(image_bytes)

    user_text = "Analiza esta imagen capturada durante una visita de campo."
    if context:
        user_text += f"\nContexto: {context}"

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            client = _get_client()
            message = await client.messages.create(
                model=model,
                max_tokens=1024,
                system=vision_prompt,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                        {"type": "text", "text": user_text},
                    ],
                }],
            )

            text = message.content[0].text.strip()
            elapsed_ms = int((time.time() - start) * 1000)
            logger.info(
                "vision_analyze_complete",
                model=model_label,
                chars=len(text),
                elapsed_ms=elapsed_ms,
                attempt=attempt,
                implementation=implementation,
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
            )
            return text

        except Exception as e:
            last_error = e
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning("vision_retry", model=model_label, attempt=attempt + 1, wait=wait, error=str(e)[:100])
                await asyncio.sleep(wait)
            else:
                logger.error("vision_analyze_failed", model=model_label, error=str(e), attempts=max_retries + 1)

    return f"[Error analizando imagen: {last_error}]"


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
    from src.engine.supabase_client import _run
    sb = get_client()
    image_bytes = await _run(lambda: sb.storage.from_("media").download(storage_path))
    return await analyze_image(image_bytes, context, implementation)


def _detect_media_type(image_bytes: bytes) -> str:
    """Detect image media type from magic bytes."""
    if image_bytes[:2] == b"\xff\xd8":
        return "image/jpeg"
    elif image_bytes[:4] == b"\x89PNG":
        return "image/png"
    elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"
