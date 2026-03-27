"""Session manager — accumulates files per user/day, detects trigger words."""

from __future__ import annotations

import datetime
from typing import Any

import structlog

from src.engine.supabase_client import (
    get_or_create_session,
    add_file_to_session,
    update_session_status,
    get_user_by_phone,
    update_user_implementation,
    list_active_implementations,
)

logger = structlog.get_logger(__name__)

# Default trigger words (fallback if DB has none)
DEFAULT_TRIGGER_WORDS = {"reporte", "generar", "listo", "fin", "report", "done"}

# Menu keywords that trigger project selection
MENU_KEYWORDS = {"menu", "menú", "proyectos", "proyecto", "cambiar"}

# In-memory state: phone → list of implementation options shown
_pending_menu: dict[str, list[dict[str, Any]]] = {}


async def get_trigger_words(impl_id: str) -> set[str]:
    """Load trigger words from DB for the given implementation, fallback to defaults."""
    try:
        from src.engine.config_loader import get_implementation
        config = await get_implementation(impl_id)
        if config.trigger_words:
            return {w.lower() for w in config.trigger_words}
    except Exception as e:
        logger.warning("trigger_words_load_failed", implementation=impl_id, error=str(e))
    return DEFAULT_TRIGGER_WORDS


def is_trigger_sync(text: str) -> bool:
    """Quick sync check against default trigger words (used before session exists)."""
    return text.strip().lower() in DEFAULT_TRIGGER_WORDS


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


async def handle_menu(phone: str) -> dict[str, Any]:
    """Show the project selection menu."""
    implementations = await list_active_implementations()
    if not implementations:
        return {
            "action": "menu_empty",
            "message": "No hay proyectos configurados.",
        }

    _pending_menu[phone] = implementations

    # Get current implementation
    user = await get_user_by_phone(phone)
    current = user.get("implementation", "?") if user else "?"

    lines = ["*Selecciona un proyecto:*\n"]
    for i, impl in enumerate(implementations, 1):
        marker = " (actual)" if impl["id"] == current else ""
        lines.append(f"{i}. {impl['name']}{marker}")
    lines.append(f"\nResponde con el numero (1-{len(implementations)})")

    return {
        "action": "menu_shown",
        "message": "\n".join(lines),
    }


async def handle_menu_selection(phone: str, choice: str) -> dict[str, Any] | None:
    """Handle a numeric reply to the project menu. Returns None if not in menu state."""
    if phone not in _pending_menu:
        return None

    options = _pending_menu[phone]
    try:
        idx = int(choice.strip()) - 1
        if 0 <= idx < len(options):
            selected = options[idx]
            del _pending_menu[phone]
            await update_user_implementation(phone, selected["id"])
            return {
                "action": "project_changed",
                "message": f"Proyecto cambiado a *{selected['name']}*.\nTodo lo que envies ahora se asocia a este proyecto.",
                "implementation": selected["id"],
            }
    except (ValueError, IndexError):
        pass

    # Invalid choice — show menu again
    return {
        "action": "menu_invalid",
        "message": f"Opcion no valida. Responde con un numero del 1 al {len(options)}.",
    }


async def handle_text(
    phone: str,
    body: str,
) -> dict[str, Any]:
    """Handle a text message — either trigger processing or add as text note.

    Returns dict with 'action': 'trigger' | 'text_added' and session data.
    """
    today = datetime.date.today()
    session = await get_or_create_session(phone, today)

    impl_id = session.get("implementation", "eficacia")
    trigger_words = await get_trigger_words(impl_id)

    # Check if any trigger word appears in the message (not just exact match)
    words_in_message = set(body.strip().lower().split())
    triggered = bool(words_in_message & trigger_words)

    if triggered:
        status = session.get("status", "accumulating")

        # Guard: already processing
        if status in ("segmenting", "processing"):
            logger.info("trigger_already_processing", phone=phone, status=status)
            return {
                "action": "empty_session",
                "session": session,
                "message": "Tu reporte se está procesando. Espera un momento.",
            }

        # Guard: already completed today
        if status == "completed":
            logger.info("trigger_already_completed", phone=phone)
            return {
                "action": "empty_session",
                "session": session,
                "message": "Ya generaste tu reporte de hoy. Los archivos nuevos se incluirán en el reporte de mañana.",
            }

        # Allow retry on failed sessions
        if status == "failed":
            logger.info("trigger_retry_failed", phone=phone, session_id=session["id"])

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

    # If session is waiting for clarification, treat any text as clarification response
    status = session.get("status", "accumulating")
    if status == "needs_clarification":
        logger.info(
            "clarification_response_received",
            phone=phone,
            session_id=session["id"],
            response=body[:100],
        )
        # Save the clarification response as a text note
        text_meta = {
            "filename": None,
            "storage_path": None,
            "type": "clarification_response",
            "content_type": "text/plain",
            "body": body,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        }
        await add_file_to_session(session["id"], text_meta)
        return {
            "action": "clarification_received",
            "session": session,
            "message": "Gracias, procesando tu reporte con esa informacion...",
            "clarification_text": body,
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
