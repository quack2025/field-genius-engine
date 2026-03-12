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

    Returns the message SID on success, None on failure.
    """
    try:
        client = get_twilio_client()
        # Twilio expects 'whatsapp:+573001234567' format
        to_whatsapp = f"whatsapp:{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone

        message = client.messages.create(
            from_=settings.twilio_whatsapp_number,
            to=to_whatsapp,
            body=body,
        )

        logger.info("message_sent", to=to_phone, sid=message.sid)
        return message.sid

    except Exception as e:
        logger.error("message_send_failed", to=to_phone, error=str(e))
        return None


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
