"""Transcriber — audio → text via OpenAI Whisper API."""

from __future__ import annotations

import io
import time
from typing import Any

import structlog
from openai import OpenAI

from src.config.settings import settings
from src.engine.supabase_client import get_client

logger = structlog.get_logger(__name__)

# Supported audio formats for Whisper
SUPPORTED_FORMATS = {".ogg", ".mp3", ".mp4", ".m4a", ".wav", ".webm", ".mpeg"}


async def transcribe(storage_path: str) -> str:
    """Download audio from Supabase Storage and transcribe via Whisper.

    Args:
        storage_path: Path in Supabase Storage bucket 'media'

    Returns:
        Transcribed text, or empty string if audio is too short/invalid.
    """
    start = time.time()
    logger.info("transcribe_start", storage_path=storage_path)

    try:
        # Download audio from Supabase Storage
        sb = get_client()
        audio_bytes = sb.storage.from_("media").download(storage_path)

        if len(audio_bytes) < 1000:
            # Very small file — likely <1 second or corrupt
            logger.info("transcribe_skip_short", storage_path=storage_path, size=len(audio_bytes))
            return ""

        # Determine file extension for Whisper
        ext = storage_path.rsplit(".", 1)[-1] if "." in storage_path else "ogg"
        filename = f"audio.{ext}"

        # Call Whisper API
        client = OpenAI(api_key=settings.openai_api_key, timeout=60.0)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename

        # Auto-detect language (supports Spanish, English, Portuguese, Creole, etc.)
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )

        elapsed_ms = int((time.time() - start) * 1000)
        text = result.text.strip()
        logger.info(
            "transcribe_complete",
            storage_path=storage_path,
            chars=len(text),
            elapsed_ms=elapsed_ms,
        )
        return text

    except Exception as e:
        logger.error("transcribe_failed", storage_path=storage_path, error=str(e))
        return ""


async def transcribe_bytes(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    """Transcribe raw audio bytes (for video-extracted audio)."""
    if len(audio_bytes) < 1000:
        return ""

    start = time.time()
    logger.info("transcribe_bytes_start", filename=filename, size=len(audio_bytes))

    try:
        client = OpenAI(api_key=settings.openai_api_key, timeout=60.0)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename

        # Auto-detect language (supports Spanish, English, Portuguese, Creole, etc.)
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )

        elapsed_ms = int((time.time() - start) * 1000)
        text = result.text.strip()
        logger.info("transcribe_bytes_complete", chars=len(text), elapsed_ms=elapsed_ms)
        return text

    except Exception as e:
        logger.error("transcribe_bytes_failed", error=str(e))
        return ""
