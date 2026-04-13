"""Media downloader — downloads media from Twilio and uploads to Supabase Storage."""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.config.settings import settings
from src.engine.supabase_client import get_client, _run

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

# Magic bytes for file type validation
MAGIC_BYTES: dict[str, list[tuple[bytes, int]]] = {
    "image/jpeg": [(b"\xff\xd8\xff", 0)],
    "image/png": [(b"\x89PNG\r\n\x1a\n", 0)],
    "image/webp": [(b"RIFF", 0), (b"WEBP", 8)],
    "audio/ogg": [(b"OggS", 0)],
    "audio/mpeg": [(b"\xff\xfb", 0), (b"\xff\xf3", 0), (b"\xff\xf2", 0), (b"ID3", 0)],
    "audio/mp4": [(b"ftyp", 4)],
    "video/mp4": [(b"ftyp", 4)],
    "video/3gpp": [(b"ftyp", 4)],
}

MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB (WhatsApp videos can be large)


def _validate_magic_bytes(file_bytes: bytes, claimed_type: str) -> bool:
    """Validate file content matches claimed MIME type via magic bytes."""
    checks = MAGIC_BYTES.get(claimed_type)
    if not checks:
        return False  # Unknown type — reject

    for magic, offset in checks:
        if len(file_bytes) > offset + len(magic):
            if file_bytes[offset:offset + len(magic)] == magic:
                return True
    return False


async def download_and_store(
    media_url: str,
    content_type: str,
    session_id: str,
    user_phone: str,
) -> dict[str, Any]:
    """Download media from Twilio URL and upload to Supabase Storage.

    Returns file metadata dict to store in session.raw_files.
    """
    # Warn on unknown content types but continue — Twilio/WhatsApp sometimes
    # sends unusual MIME types (heic, application/octet-stream, etc). We'd
    # rather accept + log than reject the user's photo.
    if content_type not in MIME_TO_EXT:
        logger.warning("media_unknown_content_type", content_type=content_type)
        # Fallback: try to infer from URL or default to image/jpeg
        if "image" in content_type.lower() or content_type == "application/octet-stream":
            content_type_effective = "image/jpeg"
        elif "audio" in content_type.lower():
            content_type_effective = "audio/ogg"
        elif "video" in content_type.lower():
            content_type_effective = "video/mp4"
        else:
            content_type_effective = "image/jpeg"
        ext = MIME_TO_EXT[content_type_effective]
        media_type = MIME_TO_TYPE[content_type_effective]
    else:
        ext = MIME_TO_EXT[content_type]
        media_type = MIME_TO_TYPE[content_type]
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
        # Download from Twilio — disable redirects to prevent SSRF via redirect
        async with httpx.AsyncClient() as http:
            response = await http.get(
                media_url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                follow_redirects=False,
                timeout=30.0,
            )

            # Handle Twilio redirects manually — only follow to allowed hosts
            if response.status_code in (301, 302, 303, 307, 308):
                redirect_url = response.headers.get("location", "")
                redirect_parsed = urlparse(redirect_url)
                if redirect_parsed.hostname not in allowed_hosts:
                    raise ValueError(f"Redirect to disallowed host: {redirect_parsed.hostname}")
                response = await http.get(
                    redirect_url,
                    auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                    follow_redirects=False,
                    timeout=30.0,
                )

            response.raise_for_status()
            file_bytes = response.content

        # Enforce file size limit
        if len(file_bytes) > MAX_FILE_SIZE:
            logger.warning("media_too_large", size=len(file_bytes), max=MAX_FILE_SIZE)
            raise ValueError(f"File too large: {len(file_bytes)} bytes (max {MAX_FILE_SIZE})")

        # Validate magic bytes match claimed content type (warn but don't reject —
        # WhatsApp/Twilio sometimes sends unusual formats we'd rather accept)
        if content_type in MAGIC_BYTES and not _validate_magic_bytes(file_bytes, content_type):
            logger.warning(
                "media_magic_bytes_mismatch",
                claimed=content_type,
                size=len(file_bytes),
                first_bytes=file_bytes[:8].hex() if len(file_bytes) >= 8 else "",
            )

        # Upload to Supabase Storage (async via thread)
        client = get_client()
        await _run(lambda: client.storage.from_("media").upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": content_type},
        ))

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
    # Validate content type
    if content_type not in MIME_TO_EXT:
        raise ValueError(f"Unsupported content type: {content_type}")

    # Validate magic bytes
    if not _validate_magic_bytes(file_bytes, content_type):
        raise ValueError(f"File content does not match claimed type {content_type}")

    # Enforce size limit
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {len(file_bytes)} bytes (max {MAX_FILE_SIZE})")

    ext = MIME_TO_EXT[content_type]
    media_type = MIME_TO_TYPE[content_type]

    if filename is None:
        file_id = str(uuid.uuid4())[:8]
        filename = f"{file_id}{ext}"

    storage_path = f"{session_id}/{filename}"

    logger.info("media_store_bytes", storage_path=storage_path, size=len(file_bytes))

    client = get_client()
    await _run(lambda: client.storage.from_("media").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": content_type},
    ))

    file_meta = {
        "filename": filename,
        "storage_path": storage_path,
        "type": media_type,
        "content_type": content_type,
        "size_bytes": len(file_bytes),
    }

    logger.info("media_store_complete", **file_meta)
    return file_meta
