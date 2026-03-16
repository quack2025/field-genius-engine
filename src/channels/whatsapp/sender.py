"""Twilio WhatsApp sender — send messages and media to users."""

from __future__ import annotations

import structlog
from twilio.rest import Client

from src.config.settings import settings

logger = structlog.get_logger(__name__)

_twilio_client: Client | None = None


def get_twilio_client() -> Client:
    """Return a singleton Twilio client."""
    global _twilio_client
    if _twilio_client is None:
        _twilio_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        logger.info("twilio_client_initialized")
    return _twilio_client


async def send_message(to_phone: str, body: str) -> str | None:
    """Send a WhatsApp text message via Twilio.

    Automatically splits messages exceeding Twilio's 1600 char limit.
    Returns the last message SID on success, None on failure.
    """
    MAX_CHARS = 1500  # Leave margin below Twilio's 1600 limit

    try:
        client = get_twilio_client()
        to_whatsapp = f"whatsapp:{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone

        # Split long messages into chunks
        chunks = _split_message(body, MAX_CHARS) if len(body) > MAX_CHARS else [body]
        last_sid = None

        for i, chunk in enumerate(chunks):
            message = client.messages.create(
                from_=settings.twilio_whatsapp_number,
                to=to_whatsapp,
                body=chunk,
            )
            last_sid = message.sid
            logger.info("message_sent", to=to_phone, sid=message.sid, part=i + 1, total=len(chunks))

        return last_sid

    except Exception as e:
        logger.error("message_send_failed", to=to_phone, error=str(e))
        return None


def _split_message(text: str, max_chars: int) -> list[str]:
    """Split text into chunks at paragraph boundaries, falling back to line breaks."""
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break

        # Try to split at a double newline (paragraph) within limit
        cut = remaining[:max_chars].rfind("\n\n")
        if cut == -1 or cut < max_chars // 3:
            # Fall back to single newline
            cut = remaining[:max_chars].rfind("\n")
        if cut == -1 or cut < max_chars // 3:
            # Fall back to space
            cut = remaining[:max_chars].rfind(" ")
        if cut == -1:
            cut = max_chars

        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()

    return chunks


async def send_media(to_phone: str, body: str, media_url: str) -> str | None:
    """Send a WhatsApp message with media attachment via Twilio."""
    try:
        client = get_twilio_client()
        to_whatsapp = f"whatsapp:{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone

        message = client.messages.create(
            from_=settings.twilio_whatsapp_number,
            to=to_whatsapp,
            body=body,
            media_url=[media_url],
        )

        logger.info("media_message_sent", to=to_phone, sid=message.sid)
        return message.sid

    except Exception as e:
        logger.error("media_message_send_failed", to=to_phone, error=str(e))
        return None
