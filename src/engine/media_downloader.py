"""Media downloader — downloads media from Twilio and uploads to Supabase Storage."""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.config.settings import settings
from src.engine.supabase_client import get_client

logger = structlog.get_logger(__name__)

# Map MIME types to file extensions
MIME_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "video/mp4": ".mp4",
    "video/3gpp": ".3gp",
}

# Classify media type from MIME
MIME_TO_TYPE: dict[str, str] = {
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "audio/ogg": "audio",
    "audio/mpeg": "audio",
    "audio/mp4": "audio",
    "video/mp4": "video",
    "video/3gpp": "video",
}


async def download_and_store(
    media_url: str,
    content_type: str,
    session_id: str,
    user_phone: str,
) -> dict[str, Any]:
    """Download media from Twilio URL and upload to Supabase Storage.

    Returns file metadata dict to store in session.raw_files.
    """
    ext = MIME_TO_EXT.get(content_type, ".bin")
    media_type = MIME_TO_TYPE.get(content_type, "unknown")
    file_id = str(uuid.uuid4())[:8]
    filename = f"{file_id}{ext}"
    storage_path = f"{session_id}/{filename}"

    logger.info(
        "media_download_start",
        media_url=media_url[:60],
        content_type=content_type,
        storage_path=storage_path,
    )

    # Validate URL is from Twilio (SSRF protection)
    parsed = urlparse(media_url)
    allowed_hosts = {'api.twilio.com', 'media.twiliocdn.com'}
    if parsed.scheme != 'https' or parsed.hostname not in allowed_hosts:
        raise ValueError(f'Media URL not from allowed Twilio domain: {media_url[:60]}')

    try:
        # Download from Twilio (requires basic auth)
        async with httpx.AsyncClient() as http:
            response = await http.get(
                media_url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                follow_redirects=True,
                timeout=30.0,
            )
            response.raise_for_status()
            file_bytes = response.content

        # Upload to Supabase Storage
        client = get_client()
        client.storage.from_("media").upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": content_type},
        )

        file_meta = {
            "filename": filename,
            "storage_path": storage_path,
            "type": media_type,
            "content_type": content_type,
            "size_bytes": len(file_bytes),
        }

        logger.info("media_download_complete", **file_meta)
        return file_meta

    except Exception as e:
        logger.error("media_download_failed", error=str(e), media_url=media_url[:60])
        raise


async def store_bytes(
    file_bytes: bytes,
    content_type: str,
    session_id: str,
    filename: str | None = None,
) -> dict[str, Any]:
    """Store raw bytes directly to Supabase Storage (used by /api/simulate)."""
    ext = MIME_TO_EXT.get(content_type, ".bin")
    media_type = MIME_TO_TYPE.get(content_type, "unknown")

    if filename is None:
        file_id = str(uuid.uuid4())[:8]
        filename = f"{file_id}{ext}"

    storage_path = f"{session_id}/{filename}"

    logger.info("media_store_bytes", storage_path=storage_path, size=len(file_bytes))

    client = get_client()
    client.storage.from_("media").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": content_type},
    )

    file_meta = {
        "filename": filename,
        "storage_path": storage_path,
        "type": media_type,
        "content_type": content_type,
        "size_bytes": len(file_bytes),
    }

    logger.info("media_store_complete", **file_meta)
    return file_meta
