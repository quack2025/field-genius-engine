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

# ── MessageSid dedup (in-memory with TTL cleanup) ──────────────────
# Prevents Twilio retry from re-processing the same message
_seen_sids: dict[str, float] = {}
_DEDUP_TTL_SECONDS = 300  # 5 minutes

# Keywords that trigger sending the configured sample report (no impl switch)
EXAMPLE_KEYWORDS = {"ejemplo", "example", "sample", "muestra", "ver ejemplo"}


def _is_duplicate(message_sid: str) -> bool:
    """Check if MessageSid was already processed. Thread-safe for single process."""
    import time
    now = time.time()

    # Cleanup expired entries (every 100th check)
    if len(_seen_sids) > 100:
        expired = [k for k, v in _seen_sids.items() if now - v > _DEDUP_TTL_SECONDS]
        for k in expired:
            _seen_sids.pop(k, None)

    if message_sid in _seen_sids:
        return True

    _seen_sids[message_sid] = now
    return False


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

    IMPORTANT: always returns 200 with empty TwiML, even on errors.
    Returning 500 causes Twilio to retry, creating duplicate processing.
    """
    try:
        return await _webhook_inner(request)
    except Exception as e:
        logger.exception("webhook_top_level_error", error=str(e))
        twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
        return Response(content=twiml, media_type="application/xml")


async def _webhook_inner(request: Request) -> Response:
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}

    # ── Dedup: reject Twilio retries for the same message ──
    message_sid = params.get("MessageSid", "")
    if message_sid and _is_duplicate(message_sid):
        logger.info("webhook_dedup_skip", message_sid=message_sid)
        twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
        return Response(content=twiml, media_type="application/xml")

    # Validate Twilio signature — hardcoded URL required in production
    signature = request.headers.get("X-Twilio-Signature", "")
    if settings.webhook_public_url:
        request_url = f"{settings.webhook_public_url}{request.url.path}"
    elif settings.environment.lower() in ("development", "dev", "local"):
        # Header fallback ONLY in development (spoofable in production)
        proto = request.headers.get("X-Forwarded-Proto", request.url.scheme)
        host = request.headers.get("Host", request.url.netloc)
        request_url = f"{proto}://{host}{request.url.path}"
    else:
        logger.error("webhook_public_url_missing_in_production")
        return Response(content="Server misconfigured", status_code=500)
    if not validate_twilio_signature(request_url, params, signature):
        logger.warning("twilio_signature_invalid")
        return Response(content="Forbidden", status_code=403)

    from_phone = params.get("From", "")  # whatsapp:+573001234567
    to_number = params.get("To", "")      # whatsapp:+17792284312
    body = params.get("Body", "").strip()
    try:
        num_media = min(int(params.get("NumMedia", "0")), 10)  # Twilio max is 10
    except (ValueError, TypeError):
        num_media = 0

    # Strip 'whatsapp:' prefix for internal use
    phone = from_phone.replace("whatsapp:", "")

    # Resolve implementation from the Twilio number the message was sent TO
    resolved_impl = None
    if to_number:
        from src.engine.supabase_client import get_implementation_by_whatsapp_number
        resolved_impl = await get_implementation_by_whatsapp_number(to_number)

    logger.info(
        "webhook_received",
        phone=phone,
        body=body[:50] if body else "",
        num_media=num_media,
        message_sid=message_sid[:12] if message_sid else "",
        to_number=to_number,
        resolved_impl=resolved_impl,
    )

    # ── Access control + Keyword routing + Onboarding flow ──
    impl_config = None
    user = None
    if resolved_impl:
        try:
            from src.engine.config_loader import get_implementation, get_impl_by_keyword
            from src.engine.supabase_client import get_user_by_phone

            # Step 0: Read user early (needed by keyword + sticky logic)
            user = await get_user_by_phone(phone)

            # Step 1: Keyword override — strongest signal
            # If the first token of the body matches any implementation's demo_keywords,
            # switch the user to that impl, persist it, send ACK, and return early.
            if body and body.strip():
                first_token = body.strip().lower().split()[0]
                matched_impl = await get_impl_by_keyword(first_token)
                if matched_impl and matched_impl != resolved_impl:
                    try:
                        target_config = await get_implementation(matched_impl)
                    except Exception:
                        target_config = None
                    if target_config and target_config.access_mode == "open":
                        from src.engine.supabase_client import (
                            update_user_implementation,
                            update_session_implementation_today,
                        )
                        # Create user if needed (first contact via keyword)
                        if not user:
                            # get_or_create_session creates user implicitly; call it with impl override
                            import datetime as _dt
                            from src.engine.supabase_client import get_or_create_session as _goc
                            await _goc(phone, _dt.date.today(), matched_impl)
                        else:
                            await update_user_implementation(phone, matched_impl)
                            await update_session_implementation_today(phone, matched_impl)
                        # Use configurable post_switch_message if set, fallback to generic ACK
                        target_onboarding = target_config.onboarding_config or {}
                        ack_msg = target_onboarding.get(
                            "post_switch_message",
                            f"Cambiado a *{target_config.name}*. Envia una foto o describe tu caso para analizar.",
                        )
                        await send_message(from_phone, ack_msg, from_number=to_number)
                        logger.info(
                            "demo_keyword_switched",
                            phone=phone,
                            from_impl=resolved_impl,
                            to_impl=matched_impl,
                        )
                        twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
                        return Response(content=twiml, media_type="application/xml")

            impl_config = await get_implementation(resolved_impl)
            onboarding = impl_config.onboarding_config

            # Step 2: Whitelist check with fallback
            if impl_config.access_mode == "whitelist":
                user_is_whitelisted = (
                    user is not None
                    and user.get("implementation") == resolved_impl
                )
                if not user_is_whitelisted:
                    # Try fallback_implementation before rejecting
                    fallback = impl_config.fallback_implementation
                    if fallback:
                        try:
                            fb_config = await get_implementation(fallback)
                        except Exception:
                            fb_config = None
                        if fb_config and fb_config.access_mode == "open":
                            logger.info(
                                "whitelist_fallback_activated",
                                phone=phone,
                                from_impl=resolved_impl,
                                to_impl=fallback,
                            )
                            resolved_impl = fallback
                            impl_config = fb_config
                            onboarding = impl_config.onboarding_config
                        else:
                            logger.warning(
                                "whitelist_fallback_invalid",
                                phone=phone,
                                fallback=fallback,
                            )
                            rejection = onboarding.get(
                                "rejection_message",
                                "No tienes acceso a este servicio. Contacta a tu administrador.",
                            )
                            logger.warning("webhook_access_denied", phone=phone, impl=resolved_impl)
                            sid = await send_message(from_phone, rejection, from_number=to_number)
                            logger.info("rejection_message_result", sid=sid, to=from_phone)
                            twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
                            return Response(content=twiml, media_type="application/xml")
                    else:
                        rejection = onboarding.get(
                            "rejection_message",
                            "No tienes acceso a este servicio. Contacta a tu administrador.",
                        )
                        logger.warning("webhook_access_denied", phone=phone, impl=resolved_impl)
                        sid = await send_message(from_phone, rejection, from_number=to_number)
                        logger.info("rejection_message_result", sid=sid, to=from_phone)
                        twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
                        return Response(content=twiml, media_type="application/xml")

            # Step 3: Sticky switching — if user already belongs to an OPEN demo impl
            # (different from resolved), respect their persistent choice
            if user and user.get("implementation") and user["implementation"] != resolved_impl:
                try:
                    user_config = await get_implementation(user["implementation"])
                    if user_config.access_mode == "open":
                        logger.info(
                            "sticky_user_impl",
                            phone=phone,
                            from_impl=resolved_impl,
                            to_impl=user["implementation"],
                        )
                        resolved_impl = user["implementation"]
                        impl_config = user_config
                        onboarding = impl_config.onboarding_config
                except Exception:
                    pass  # user's impl doesn't exist or failed to load — stay with resolved_impl

            # Step 3.5: "ejemplo" command — send sample report without processing a real photo
            if body and body.strip().lower() in EXAMPLE_KEYWORDS:
                sample = impl_config.onboarding_config.get("sample_report", "")
                if sample:
                    await send_message(from_phone, sample, from_number=to_number)
                    logger.info("sample_report_sent", phone=phone, impl=resolved_impl)
                else:
                    await send_message(
                        from_phone,
                        "No hay reporte de muestra configurado para este demo. Envia una foto para ver tu análisis real.",
                        from_number=to_number,
                    )
                    logger.warning("sample_report_missing", impl=resolved_impl)
                twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
                return Response(content=twiml, media_type="application/xml")

            # Step 4: Terms acceptance check
            if user and onboarding.get("require_terms", False) and not user.get("accepted_terms"):
                body_lower = body.strip().lower()

                if body_lower in ("acepto", "accept", "si", "sí", "ok"):
                    from src.engine.supabase_client import _run, get_client
                    import datetime
                    await _run(lambda: get_client().table("users").update({
                        "accepted_terms": True,
                        "onboarded_at": datetime.datetime.now(datetime.UTC).isoformat(),
                    }).eq("phone", phone).execute())
                    accepted_msg = onboarding.get(
                        "terms_accepted_message",
                        "Perfecto! Ya puedes empezar. Envía tus fotos y audios.",
                    )
                    await send_message(from_phone, accepted_msg, from_number=to_number)
                    logger.info("user_accepted_terms", phone=phone, impl=resolved_impl)
                    twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
                    return Response(content=twiml, media_type="application/xml")
                else:
                    await _send_welcome(onboarding, from_phone, to_number)
                    logger.info("user_onboarding_sent", phone=phone, impl=resolved_impl)
                    twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
                    return Response(content=twiml, media_type="application/xml")

            # Step 5: First contact for open-mode users (no terms, just welcome)
            if not user and impl_config.access_mode == "open":
                if onboarding.get("welcome_message") or onboarding.get("welcome_content_sid"):
                    await _send_welcome(onboarding, from_phone, to_number)

        except Exception as e:
            logger.error("access_check_failed", phone=phone, error=str(e))

    # Process location sharing (Twilio sends Latitude/Longitude params)
    latitude = params.get("Latitude")
    longitude = params.get("Longitude")
    if latitude and longitude:
        try:
            import datetime
            from src.engine.supabase_client import get_or_create_session

            session = await get_or_create_session(phone, datetime.date.today(), resolved_impl)
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

            session = await get_or_create_session(phone, datetime.date.today(), resolved_impl)

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
            # Use configurable hint message
            hint_template = (impl_config.onboarding_config.get("first_photo_hint") if impl_config else None) or "Recibido ({count} archivo(s) hoy). Escribe *reporte* cuando termines."
            await send_message(from_phone, hint_template.replace("{count}", str(file_count)))

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
            # Enqueue pipeline to background — NEVER run inline (blocks webhook 30-120s)
            import datetime as dt
            from src.engine.supabase_client import get_or_create_session
            session = await get_or_create_session(phone, dt.date.today(), resolved_impl)
            asyncio.create_task(_run_pipeline_safe(session["id"], from_phone))
        elif result["action"] == "clarification_received":
            await send_message(from_phone, result["message"])
            # Resume pipeline in background
            session = result["session"]
            asyncio.create_task(_resume_pipeline_safe(
                session["id"],
                result["clarification_text"],
                from_phone,
            ))
        elif result["action"] == "empty_session":
            await send_message(from_phone, result["message"])
        elif result["action"] == "text_added":
            # QW2: Hint about trigger words if any word in the message looks like intent
            words_in_msg = set(body.lower().strip("!.?").split())
            intent_words = {"informe", "reportar", "enviar", "procesar"}
            if words_in_msg & intent_words:
                await send_message(from_phone, "Para generar tu reporte escribe: *reporte*")

    # Return empty TwiML response immediately (Twilio expects XML within 15s)
    twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
    return Response(content=twiml, media_type="application/xml")


async def _send_welcome(
    onboarding_config: dict,
    to_phone: str,
    from_number: str,
) -> None:
    """Send the welcome message: interactive content template if configured, else plain text.

    If `onboarding_config.welcome_content_sid` is set, use Twilio Content API
    (interactive buttons, list picker, etc). Falls back to `welcome_message` text
    if the template fails or isn't configured.
    """
    content_sid = onboarding_config.get("welcome_content_sid")
    welcome_text = onboarding_config.get(
        "welcome_message",
        "Bienvenido a Radar Xponencial!",
    )

    if content_sid:
        from src.channels.whatsapp.sender import send_content_template
        content_vars = onboarding_config.get("welcome_content_variables")
        sid = await send_content_template(
            to_phone,
            content_sid,
            content_variables=content_vars,
            from_number=from_number,
        )
        if sid:
            return
        # Template failed — fall back to text
        logger.warning("welcome_content_fallback_to_text", content_sid=content_sid)

    await send_message(to_phone, welcome_text, from_number=from_number)


async def _run_pipeline_safe(session_id: str, reply_phone: str) -> None:
    """Run pipeline in background. Catch errors and notify user."""
    try:
        from src.engine.pipeline import process_session
        await process_session(session_id)
    except Exception as e:
        logger.error("pipeline_background_failed", session_id=session_id, error=str(e))
        try:
            await send_message(reply_phone, "Hubo un error generando tu reporte. Intenta de nuevo con *reporte*.")
        except Exception:
            pass


async def _resume_pipeline_safe(session_id: str, clarification: str, reply_phone: str) -> None:
    """Resume pipeline after clarification in background."""
    try:
        from src.engine.pipeline import resume_after_clarification
        await resume_after_clarification(session_id, clarification)
    except Exception as e:
        logger.error("pipeline_resume_failed", session_id=session_id, error=str(e))
        try:
            await send_message(reply_phone, "Hubo un error procesando tu respuesta. Intenta de nuevo.")
        except Exception:
            pass
