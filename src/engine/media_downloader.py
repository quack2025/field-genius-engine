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


class UnsupportedMediaError(ValueError):
    """Raised when user sends a content type we can't process (PDF, doc, sticker)."""
    def __init__(self, content_type: str):
        super().__init__(f"Unsupported media type: {content_type}")
        self.content_type = content_type


def is_supported_media(content_type: str) -> tuple[bool, str]:
    """Return (supported, media_type) for a claimed MIME type.

    Returns (True, 'image'|'audio'|'video') if we can process it,
    (False, '') otherwise.
    """
    ct = (content_type or "").lower().split(";")[0].strip()
    if ct in MIME_TO_EXT:
        return True, MIME_TO_TYPE[ct]
    # Infer from prefix for common variations
    if ct.startswith("image/") and "sticker" not in ct and "webp.animated" not in ct:
        return True, "image"
    if ct.startswith("audio/"):
        return True, "audio"
    if ct.startswith("video/"):
        return True, "video"
    return False, ""


async def download_and_store(
    media_url: str,
    content_type: str,
    session_id: str,
    user_phone: str,
) -> dict[str, Any]:
    """Download media from Twilio URL and upload to Supabase Storage.

    Returns file metadata dict to store in session.raw_files.
    Raises UnsupportedMediaError for PDFs, docs, stickers, contacts, etc.
    """
    # Normalize content type
    ct_norm = (content_type or "").lower().split(";")[0].strip()

    # Hard reject known-unsupported types (friendly message sent by caller)
    if ct_norm in MIME_TO_EXT:
        ext = MIME_TO_EXT[ct_norm]
        media_type = MIME_TO_TYPE[ct_norm]
    else:
        # Try to infer from prefix
        if ct_norm.startswith("image/") and "webp" not in ct_norm:
            # Unusual image subtype (heic, heif, tiff, etc) — treat as JPEG
            logger.warning("media_unusual_image_type", content_type=content_type)
            ext = ".jpg"
            media_type = "image"
        elif ct_norm.startswith("audio/"):
            logger.warning("media_unusual_audio_type", content_type=content_type)
            ext = ".ogg"
            media_type = "audio"
        elif ct_norm.startswith("video/"):
            logger.warning("media_unusual_video_type", content_type=content_type)
            ext = ".mp4"
            media_type = "video"
        elif ct_norm == "application/octet-stream":
            # Ambiguous binary — WhatsApp sometimes sends photos this way
            logger.warning("media_octet_stream_treating_as_image", content_type=content_type)
            ext = ".jpg"
            media_type = "image"
        else:
            # PDFs, docs, vcards, stickers, contacts, etc — we can't process these
            logger.info("media_unsupported_type_rejected", content_type=content_type)
            raise UnsupportedMediaError(content_type)
    file_id = str(uuid.uuid4())[:8]
    filename = f"{file_id}{ext}"
    storage_path = f"{session_id}/{filename}"

    logger.info(
        "media_download_start",
        media_url=media_url[:60],
        content_type=content_type,
        storage_path=storage_path,
    )

    # Validate URL is from Twilio (SSRF protection).
    # Twilio redirects from api.twilio.com to *.twiliocdn.com — we allow any
    # subdomain of twiliocdn.com (media, mms, ccustatic, etc) + api.twilio.com itself.
    parsed = urlparse(media_url)
    host = (parsed.hostname or "").lower()
    allowed = (
        host == "api.twilio.com"
        or host.endswith(".twiliocdn.com")
        or host == "twiliocdn.com"
    )
    if parsed.scheme != 'https' or not allowed:
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

            # Handle Twilio redirects manually — only follow to allowed hosts.
            # Follow up to 3 redirects (Twilio typically does api.twilio.com → *.twiliocdn.com).
            max_redirects = 3
            while response.status_code in (301, 302, 303, 307, 308) and max_redirects > 0:
                redirect_url = response.headers.get("location", "")
                redirect_parsed = urlparse(redirect_url)
                r_host = (redirect_parsed.hostname or "").lower()
                r_allowed = (
                    r_host == "api.twilio.com"
                    or r_host.endswith(".twiliocdn.com")
                    or r_host == "twiliocdn.com"
                )
                if not r_allowed:
                    raise ValueError(f"Redirect to disallowed host: {r_host}")
                response = await http.get(
                    redirect_url,
                    auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                    follow_redirects=False,
                    timeout=30.0,
                )
                max_redirects -= 1

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
