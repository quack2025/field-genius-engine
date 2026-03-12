"""Session manager — accumulates files per user/day, detects trigger words."""

from __future__ import annotations

import datetime
from typing import Any

import structlog

from src.engine.supabase_client import (
    get_or_create_session,
    add_file_to_session,
    update_session_status,
)

logger = structlog.get_logger(__name__)

# Trigger words that close a session and start processing
TRIGGER_WORDS = {"reporte", "generar", "listo", "fin", "report", "done"}


def is_trigger(text: str) -> bool:
    """Check if the text message is a processing trigger."""
    return text.strip().lower() in TRIGGER_WORDS


async def handle_media(
    phone: str,
    file_metadata: dict[str, Any],
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Add a media file to the user's daily session.

    Returns the session dict.
    """
    today = datetime.date.today()
    session = await get_or_create_session(phone, today)

    # Add timestamp to metadata
    if timestamp:
        file_metadata["timestamp"] = timestamp
    else:
        file_metadata["timestamp"] = datetime.datetime.now(datetime.UTC).isoformat()

    await add_file_to_session(session["id"], file_metadata)

    logger.info(
        "session_file_added",
        session_id=session["id"],
        phone=phone,
        filename=file_metadata.get("filename"),
        total_files=len(session.get("raw_files", [])) + 1,
    )

    return session


async def handle_text(
    phone: str,
    body: str,
) -> dict[str, Any]:
    """Handle a text message — either trigger processing or add as text note.

    Returns dict with 'action': 'trigger' | 'text_added' and session data.
    """
    today = datetime.date.today()
    session = await get_or_create_session(phone, today)

    if is_trigger(body):
        file_count = len(session.get("raw_files", []))
        if file_count == 0:
            logger.info("trigger_empty_session", phone=phone, session_id=session["id"])
            return {
                "action": "empty_session",
                "session": session,
                "message": "No tienes archivos acumulados hoy. Manda fotos, audios o videos primero.",
            }

        await update_session_status(session["id"], "segmenting")
        logger.info(
            "trigger_processing",
            phone=phone,
            session_id=session["id"],
            file_count=file_count,
        )
        return {
            "action": "trigger",
            "session": session,
            "message": f"Procesando {file_count} archivo(s). Te notifico cuando esté listo.",
        }

    # Not a trigger — add as text note
    text_meta = {
        "filename": None,
        "storage_path": None,
        "type": "text",
        "content_type": "text/plain",
        "body": body,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    await add_file_to_session(session["id"], text_meta)
    logger.info("session_text_added", session_id=session["id"], phone=phone)

    return {
        "action": "text_added",
        "session": session,
        "message": None,
    }
