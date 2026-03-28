"""Twilio WhatsApp webhook — receives incoming messages via POST."""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Request, Response

import asyncio

from src.config.settings import settings
from src.channels.whatsapp.session_manager import (
    handle_media,
    handle_text,
    handle_menu,
    handle_menu_selection,
    MENU_KEYWORDS,
)
from src.channels.whatsapp.sender import send_message
from src.engine.media_downloader import download_and_store

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["webhook"])


def validate_twilio_signature(url: str, params: dict, signature: str) -> bool:
    """Validate X-Twilio-Signature HMAC to verify request authenticity."""
    if not settings.twilio_auth_token:
        logger.error("twilio_auth_token_missing", msg="Rejecting request — no auth token configured")
        return False

    # Build the data string: URL + sorted POST params concatenated
    data = url
    for key in sorted(params.keys()):
        data += key + params[key]

    expected = hmac.new(
        settings.twilio_auth_token.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha1,
    ).digest()

    import base64
    expected_b64 = base64.b64encode(expected).decode("utf-8")

    return hmac.compare_digest(expected_b64, signature)


@router.post("/webhook/whatsapp")
async def twilio_webhook(request: Request) -> Response:
    """Handle incoming Twilio WhatsApp messages.

    Twilio sends form-encoded POST with fields like:
    - From: whatsapp:+573001234567
    - Body: text message
    - NumMedia: number of media attachments
    - MediaUrl0, MediaContentType0, etc.
    """
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}

    # Validate Twilio signature — reconstruct public URL from proxy headers
    # Behind Railway proxy, request.url is http://0.0.0.0:8080/... but Twilio
    # signed with the public https:// URL
    signature = request.headers.get("X-Twilio-Signature", "")
    proto = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    host = request.headers.get("Host", request.url.netloc)
    request_url = f"{proto}://{host}{request.url.path}"
    if not validate_twilio_signature(request_url, params, signature):
        logger.warning("twilio_signature_invalid")
        return Response(content="Forbidden", status_code=403)

    from_phone = params.get("From", "")  # whatsapp:+573001234567
    body = params.get("Body", "").strip()
    try:
        num_media = min(int(params.get("NumMedia", "0")), 10)  # Twilio max is 10
    except (ValueError, TypeError):
        num_media = 0

    # Strip 'whatsapp:' prefix for internal use
    phone = from_phone.replace("whatsapp:", "")

    logger.info(
        "webhook_received",
        phone=phone,
        body=body[:50] if body else "",
        num_media=num_media,
    )

    # Process location sharing (Twilio sends Latitude/Longitude params)
    latitude = params.get("Latitude")
    longitude = params.get("Longitude")
    if latitude and longitude:
        try:
            import datetime
            from src.engine.supabase_client import get_or_create_session

            session = await get_or_create_session(phone, datetime.date.today())
            location_meta = {
                "filename": None,
                "storage_path": None,
                "type": "location",
                "content_type": "application/geo",
                "latitude": float(latitude),
                "longitude": float(longitude),
                "address": params.get("Address", ""),
                "label": params.get("Label", ""),
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            }
            await handle_media(phone, location_meta)
            await send_message(from_phone, "Ubicacion recibida")
            logger.info(
                "location_received",
                phone=phone,
                lat=latitude,
                lng=longitude,
                address=params.get("Address", ""),
            )
        except Exception as e:
            logger.error("location_processing_failed", phone=phone, error=str(e))

    # Process media attachments
    for i in range(num_media):
        media_url = params.get(f"MediaUrl{i}", "")
        content_type = params.get(f"MediaContentType{i}", "application/octet-stream")

        if not media_url:
            continue

        try:
            # Get or create session first to get session_id
            import datetime
            from src.engine.supabase_client import get_or_create_session

            session = await get_or_create_session(phone, datetime.date.today())

            # Download media and upload to Supabase Storage
            file_meta = await download_and_store(
                media_url=media_url,
                content_type=content_type,
                session_id=session["id"],
                user_phone=phone,
            )

            # Add file to session
            await handle_media(phone, file_meta)

            # QW4: Acknowledge receipt with file count
            file_count = len(session.get("raw_files", [])) + 1
            await send_message(from_phone, f"Recibido ({file_count} archivo(s) hoy)")

            # Pre-process in background via queue (or inline fallback)
            impl_id = session.get("implementation", settings.default_implementation)
            from src.engine.worker import enqueue_preprocess
            await enqueue_preprocess(session["id"], file_meta, implementation=impl_id)

        except Exception as e:
            logger.error("media_processing_failed", phone=phone, error=str(e))
            # QW3: Notify user on media download failure
            await send_message(from_phone, "No pude procesar ese archivo. Intenta enviarlo de nuevo.")

    # Process text body (if any, and not just media caption)
    if body and num_media == 0:
        body_lower = body.strip().lower()

        # Check for menu keyword
        if body_lower in MENU_KEYWORDS:
            menu_result = await handle_menu(phone)
            await send_message(from_phone, menu_result["message"])
            twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
            return Response(content=twiml, media_type="application/xml")

        # Check for pending menu selection (numeric reply)
        menu_selection = await handle_menu_selection(phone, body)
        if menu_selection:
            await send_message(from_phone, menu_selection["message"])
            twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
            return Response(content=twiml, media_type="application/xml")

        result = await handle_text(phone, body)

        if result["action"] == "trigger":
            await send_message(from_phone, result["message"])
            # Run the full pipeline
            import datetime as dt
            from src.engine.supabase_client import get_or_create_session
            from src.engine.pipeline import process_session
            session = await get_or_create_session(phone, dt.date.today())
            await process_session(session["id"])
        elif result["action"] == "clarification_received":
            await send_message(from_phone, result["message"])
            # Resume pipeline from Phase 2 with clarification context
            from src.engine.pipeline import resume_after_clarification
            session = result["session"]
            await resume_after_clarification(
                session["id"],
                result["clarification_text"],
            )
        elif result["action"] == "empty_session":
            await send_message(from_phone, result["message"])
        elif result["action"] == "text_added":
            # QW2: Hint about trigger words if any word in the message looks like intent
            words_in_msg = set(body.lower().strip("!.?").split())
            intent_words = {"informe", "reportar", "enviar", "procesar"}
            if words_in_msg & intent_words:
                await send_message(from_phone, "Para generar tu reporte escribe: *reporte*")

    # Return empty TwiML response (Twilio expects XML)
    twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
    return Response(content=twiml, media_type="application/xml")
