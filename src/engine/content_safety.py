"""Content safety — pre-screen media before AI processing.

Screens images for business relevance and audio transcriptions for PII.
Runs BEFORE the main Vision/Whisper analysis to prevent inappropriate
content from entering the pipeline.

Categories for images:
  - business_relevant: field visit photo (shelf, store, product, POP)
  - personal: selfie, family photo, food, screenshot
  - nsfw: intimate/explicit content
  - confidential: document, contract, spreadsheet with sensitive data
  - unclear: can't determine (low quality, too dark, abstract)

For audio transcriptions:
  - Regex + pattern matching for phone numbers, emails, IDs
  - Replaces detected PII with [REDACTED]
"""

from __future__ import annotations

import base64
import re
import time
from typing import Any

import structlog
from anthropic import AsyncAnthropic

from src.config.settings import settings

logger = structlog.get_logger(__name__)

# Singleton async Haiku client for cheap classification calls
_haiku_client: AsyncAnthropic | None = None


def _get_haiku() -> AsyncAnthropic:
    global _haiku_client
    if _haiku_client is None:
        _haiku_client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=30.0)
    return _haiku_client


# ── Image Content Moderation ─────────────────────────────────────


MODERATION_PROMPT = """You are a content classifier for a business field intelligence platform.
Field agents send photos from store/retail visits. Your job is to classify each image.

Respond with ONLY one of these categories (no explanation):
- BUSINESS: photo of a store, shelf, product, price tag, POP material, storefront, gondola, display, installation, equipment
- PERSONAL: selfie, family photo, food, pet, personal screenshot, meme, social media
- NSFW: intimate, explicit, or sexually suggestive content
- CONFIDENTIAL: document, contract, spreadsheet, ID card, credit card, internal memo
- UNCLEAR: too dark, too blurry, abstract, or cannot determine content

Respond with the single word category only."""


async def classify_image(image_bytes: bytes) -> dict[str, Any]:
    """Classify an image for content safety using Haiku (cheap + fast).

    Returns:
        {
            "category": "BUSINESS" | "PERSONAL" | "NSFW" | "CONFIDENTIAL" | "UNCLEAR",
            "is_safe": True/False,
            "should_process": True/False,
            "elapsed_ms": int,
        }
    """
    start = time.time()

    try:
        client = _get_haiku()

        # Detect media type
        if image_bytes[:2] == b"\xff\xd8":
            media_type = "image/jpeg"
        elif image_bytes[:4] == b"\x89PNG":
            media_type = "image/png"
        elif image_bytes[:4] == b"RIFF":
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"

        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            system=MODERATION_PROMPT,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": "Classify this image."},
                ],
            }],
        )

        category = message.content[0].text.strip().upper()

        # Normalize unexpected responses
        valid = {"BUSINESS", "PERSONAL", "NSFW", "CONFIDENTIAL", "UNCLEAR"}
        if category not in valid:
            for v in valid:
                if v in category:
                    category = v
                    break
            else:
                category = "UNCLEAR"

        elapsed_ms = int((time.time() - start) * 1000)

        is_safe = category not in ("NSFW",)
        should_process = category in ("BUSINESS", "UNCLEAR")

        logger.info(
            "content_classification",
            category=category,
            is_safe=is_safe,
            should_process=should_process,
            elapsed_ms=elapsed_ms,
        )

        return {
            "category": category,
            "is_safe": is_safe,
            "should_process": should_process,
            "elapsed_ms": elapsed_ms,
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error("content_classification_failed", error=str(e), elapsed_ms=elapsed_ms)
        # On failure, allow processing (don't block the pipeline)
        return {
            "category": "UNCLEAR",
            "is_safe": True,
            "should_process": True,
            "elapsed_ms": elapsed_ms,
        }


# ── PII Scrubbing for Text ───────────────────────────────────────

# Patterns for common PII in Latin America
PII_PATTERNS = [
    # Phone numbers: +57 300 123 4567, 300-123-4567, (506) 8800-1234
    (r"(\+?\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4})", "[TEL REDACTED]"),
    # Email addresses
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL REDACTED]"),
    # Colombian cedula: 8-10 digits
    (r"\b\d{8,10}\b(?=.*(?:cedula|cc|ci|documento|identidad))", "[CEDULA REDACTED]"),
    # Credit card numbers: 16 digits with optional spaces/dashes
    (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[CARD REDACTED]"),
    # Costa Rica cedula: X-XXXX-XXXX
    (r"\b\d{1}-\d{4}-\d{4}\b", "[CEDULA REDACTED]"),
]

# Compiled patterns for performance
_COMPILED_PII = [(re.compile(p, re.IGNORECASE), r) for p, r in PII_PATTERNS]


def scrub_pii(text: str) -> tuple[str, int]:
    """Remove PII from text using regex patterns.

    Returns:
        (scrubbed_text, pii_count) — the cleaned text and number of PII instances found.
    """
    if not text:
        return text, 0

    pii_count = 0
    result = text

    for pattern, replacement in _COMPILED_PII:
        matches = pattern.findall(result)
        if matches:
            pii_count += len(matches)
            result = pattern.sub(replacement, result)

    if pii_count > 0:
        logger.info("pii_scrubbed", count=pii_count, original_len=len(text), scrubbed_len=len(result))

    return result, pii_count
