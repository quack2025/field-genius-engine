"""Pre-processor — transcribe audio and analyze images at ingestion time.

Runs as a fire-and-forget background task after media is saved to storage.
Results are written back to the file entry in session.raw_files so the
segmenter can skip re-processing.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from src.engine.supabase_client import update_file_in_session

logger = structlog.get_logger(__name__)


async def preprocess_file(
    session_id: str,
    file_meta: dict[str, Any],
    implementation: str = "",
) -> None:
    """Pre-process a single file: transcribe audio or analyze image.

    Updates the file entry in raw_files with the result. Safe to call
    fire-and-forget — all errors are caught and logged.
    """
    filename = file_meta.get("filename")
    file_type = file_meta.get("type", "unknown")
    storage_path = file_meta.get("storage_path")

    if not filename or not storage_path:
        return

    try:
        if file_type == "audio":
            await _preprocess_audio(session_id, filename, storage_path)
        elif file_type == "image":
            await _preprocess_image(session_id, filename, storage_path, implementation)
        elif file_type == "video":
            await _preprocess_video(session_id, filename, storage_path, implementation)
    except Exception as e:
        logger.error(
            "preprocess_failed",
            session_id=session_id,
            filename=filename,
            file_type=file_type,
            error=str(e),
        )


async def _preprocess_audio(session_id: str, filename: str, storage_path: str) -> None:
    """Transcribe audio and store result in raw_files entry."""
    from src.engine.transcriber import transcribe

    start = time.time()
    logger.info("preprocess_audio_start", filename=filename)

    text = await transcribe(storage_path)
    elapsed_ms = int((time.time() - start) * 1000)

    if text:
        await update_file_in_session(session_id, filename, {"transcription": text})
        logger.info("preprocess_audio_done", filename=filename, chars=len(text), elapsed_ms=elapsed_ms)
    else:
        logger.info("preprocess_audio_empty", filename=filename, elapsed_ms=elapsed_ms)


async def _preprocess_image(
    session_id: str, filename: str, storage_path: str, implementation: str
) -> None:
    """Analyze image with Vision and store description in raw_files entry."""
    from src.engine.vision import analyze_from_storage

    start = time.time()
    logger.info("preprocess_image_start", filename=filename)

    desc = await analyze_from_storage(storage_path, implementation=implementation)
    elapsed_ms = int((time.time() - start) * 1000)

    if desc and not desc.startswith("[Error"):
        await update_file_in_session(session_id, filename, {"image_description": desc})
        logger.info("preprocess_image_done", filename=filename, chars=len(desc), elapsed_ms=elapsed_ms)
    else:
        logger.info("preprocess_image_failed", filename=filename, elapsed_ms=elapsed_ms)


async def _preprocess_video(
    session_id: str, filename: str, storage_path: str, implementation: str
) -> None:
    """Extract frames + audio from video, transcribe audio, analyze first frame."""
    from src.engine.video import process_video
    from src.engine.transcriber import transcribe_bytes
    from src.engine.vision import analyze_image

    start = time.time()
    logger.info("preprocess_video_start", filename=filename)

    video_result = await process_video(storage_path)
    updates: dict[str, Any] = {}

    # Transcribe extracted audio
    if video_result.audio_bytes:
        text = await transcribe_bytes(video_result.audio_bytes)
        if text:
            updates["transcription"] = text

    # Analyze first frame only (for preview — full frames done in segmenter)
    if video_result.frames:
        desc = await analyze_image(
            video_result.frames[0],
            context="frame de video de visita de campo",
            implementation=implementation,
        )
        if desc and not desc.startswith("[Error"):
            updates["image_description"] = desc

    elapsed_ms = int((time.time() - start) * 1000)

    if updates:
        await update_file_in_session(session_id, filename, updates)
        logger.info("preprocess_video_done", filename=filename, keys=list(updates.keys()), elapsed_ms=elapsed_ms)
    else:
        logger.info("preprocess_video_empty", filename=filename, elapsed_ms=elapsed_ms)
