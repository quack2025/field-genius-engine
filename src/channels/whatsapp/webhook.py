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

# Keywords that accept T&C (text or button title)
ACCEPT_KEYWORDS = {"acepto", "accept", "si", "sí", "ok", "acepta", "de acuerdo"}

# Keywords that decline T&C (text or button title)
DECLINE_KEYWORDS = {"no acepto", "no", "decline", "rechazo", "cancelar"}

# Keywords that trigger demo batch analysis (only when impl is in demo_mode)
DEMO_TRIGGER_KEYWORDS = {
    "generar", "generar reporte", "reporte", "listo", "ya",
    "analizar", "analiza", "fin", "terminé", "termine", "done",
}

# CTA keywords shown at the end of each demo report
CTA_OTRO_KEYWORDS = {"otro", "otro demo", "cambiar demo", "siguiente"}
CTA_CONTACTO_KEYWORDS = {"contacto", "contactar", "contact", "hablar", "humano"}

# TTL (minutes) for a pending contact-info capture — after this, ignore stale flag
PENDING_CONTACT_TTL_MIN = 10

# POC gating — "POC" is a meta-keyword that asks the user which client POC they want
POC_KEYWORDS = {"poc", "p.o.c.", "p.o.c"}
POC_COMPANY_KEYWORDS = {"argos", "telecable"}
PENDING_POC_TTL_MIN = 10

# Location prompt — asked on first media in demo mode
LOCATION_PROMPT_TTL_MIN = 10

# Hardcoded map of which demo is "the other one" for the `otro` CTA.
# After the POC gating sprint, the two public demos are Retail (laundry_care) and
# whichever POC the user is in. For now we keep the simple laundry_care ↔ telecable
# toggle; Argos-bound users who write "otro" fall through to laundry_care too.
OTHER_DEMO_MAP = {
    "laundry_care": "telecable",
    "telecable": "laundry_care",
    "argos": "laundry_care",
}

# Explicit commands the user can type even while in a pending POC/location state.
# These are "escape hatches" — they override the pending flow cleanly, falling
# through to their normal handler instead of being treated as lead data / wrong
# company name / etc.
DEMO_ESCAPE_KEYWORDS = (
    {"menu", "menú", "proyectos", "cambiar"}
    | {"generar", "generar reporte", "reporte", "listo", "ya", "analizar", "analiza", "fin", "terminé", "termine", "done"}
    | CTA_OTRO_KEYWORDS
    | CTA_CONTACTO_KEYWORDS
    | {"retail", "cpg", "shopper"}  # demo_keywords of laundry_care (the general retail demo)
)


def _pending_is_active(iso_ts: str | None, ttl_minutes: int) -> bool:
    """Check if a timestamptz ISO string from DB is still within TTL from now."""
    if not iso_ts:
        return False
    try:
        import datetime as _dt
        ts = _dt.datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        age_min = (_dt.datetime.now(_dt.UTC) - ts).total_seconds() / 60
        return age_min < ttl_minutes
    except Exception:
        return False


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
    pending_poc_active = False
    pending_location_active = False
    if resolved_impl:
        try:
            from src.engine.config_loader import get_implementation, get_impl_by_keyword
            from src.engine.supabase_client import get_user_by_phone

            # Step 0: Read user early (needed by keyword + sticky logic)
            user = await get_user_by_phone(phone)
            # Capture pending-state snapshot for this request (so we have a
            # stable view regardless of when clears happen later in the flow)
            pending_poc_active = (
                user is not None
                and _pending_is_active(user.get("pending_poc_selection_at"), PENDING_POC_TTL_MIN)
            )
            pending_location_active = (
                user is not None
                and _pending_is_active(user.get("pending_location_request_at"), LOCATION_PROMPT_TTL_MIN)
            )

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
                            upsert_user,
                            update_session_implementation_today,
                            clear_session_files_today,
                            clear_pending_poc_selection,
                            clear_pending_location_request,
                        )
                        # Create or update user row so the switch persists across messages
                        await upsert_user(phone, matched_impl)
                        await update_session_implementation_today(phone, matched_impl)
                        # Fresh-start the session: each demo switch wipes previously
                        # accumulated files so reports don't mix contexts (retail + telecom).
                        await clear_session_files_today(phone)
                        # Clear POC/location pending state — user made an explicit choice,
                        # so any stale pending flags are no longer valid.
                        await clear_pending_poc_selection(phone)
                        await clear_pending_location_request(phone)
                        # Re-fetch so later steps in this request see the new impl
                        user = await get_user_by_phone(phone)
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

            # Step 4: Terms acceptance check (only if require_terms=true)
            if user and onboarding.get("require_terms", False) and not user.get("accepted_terms"):
                body_lower = body.strip().lower() if body else ""

                # Accept path (text or button tap)
                if body_lower in ACCEPT_KEYWORDS:
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

                # Decline path (text or button tap)
                if body_lower in DECLINE_KEYWORDS:
                    decline_msg = onboarding.get(
                        "terms_declined_message",
                        "Entendido. Si cambias de opinión, escríbenos de nuevo. ¡Gracias por tu tiempo!",
                    )
                    await send_message(from_phone, decline_msg, from_number=to_number)
                    logger.info("user_declined_terms", phone=phone, impl=resolved_impl)
                    twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
                    return Response(content=twiml, media_type="application/xml")

                # Neither accept nor decline — show T&C prompt (card with buttons if configured)
                terms_sid = onboarding.get("terms_content_sid")
                if terms_sid:
                    from src.channels.whatsapp.sender import send_content_template
                    sid = await send_content_template(
                        from_phone,
                        terms_sid,
                        from_number=to_number,
                    )
                    if not sid:
                        # Fallback to text welcome if content template failed
                        await _send_welcome(onboarding, from_phone, to_number)
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
            # Clear any pending location-request flag — user answered it
            try:
                from src.engine.supabase_client import clear_pending_location_request
                await clear_pending_location_request(phone)
                pending_location_active = False
            except Exception:
                pass
            # Friendlier response for demo visitors — location alone doesn't generate a report
            location_ack = (
                "Ubicación recibida 📍\n\n"
                "Sigue enviando fotos, audios o videos de lo que quieras analizar, "
                "y escribe *generar* cuando termines. Tu ubicación se incluirá en el análisis."
            )
            await send_message(from_phone, location_ack, from_number=to_number)
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
    # POC gating: if the user tapped "POC" and is pending a company selection,
    # block ALL media until they answer with argos/telecable. Send the prompt
    # once per request (not per-attachment) to avoid spamming for multi-media.
    if num_media > 0 and pending_poc_active:
        await send_message(
            from_phone,
            "Primero dime el nombre de tu empresa para activar tu POC personalizado:\n\n"
            "• *argos*\n"
            "• *telecable*\n\n"
            "Cuando escribas el nombre, analizo tu material con los frameworks de ese cliente.",
            from_number=to_number,
        )
        logger.info("poc_pending_blocked_media", phone=phone, num_media=num_media)
        num_media = 0  # skip the media loop below

    for i in range(num_media):
        media_url = params.get(f"MediaUrl{i}", "")
        content_type = params.get(f"MediaContentType{i}", "application/octet-stream")

        if not media_url:
            continue

        try:
            # Get or create session first to get session_id
            import datetime
            from src.engine.supabase_client import get_or_create_session, get_session_files
            from src.engine.media_downloader import UnsupportedMediaError, is_supported_media
            from src.engine.demo_analyzer import MAX_IMAGES_PER_BATCH, MAX_AUDIOS_PER_BATCH

            session = await get_or_create_session(phone, datetime.date.today(), resolved_impl)

            demo_mode = bool(impl_config and impl_config.onboarding_config.get("demo_mode"))
            batch_mode = (
                impl_config.onboarding_config.get("demo_batch_mode", "explicit")
                if impl_config else "explicit"
            )

            # Demo+explicit: apply a high safety cap to prevent abuse, but let
            # users keep sending photos freely. The actual analysis uses the
            # most recent MAX_IMAGES_PER_BATCH (soft cap), with messaging in
            # the ack so the user knows.
            ABUSE_CAP_IMAGES = 30
            ABUSE_CAP_AUDIOS = 10
            if demo_mode and batch_mode == "explicit":
                supported, inferred_type = is_supported_media(content_type)
                if supported and inferred_type in ("image", "audio"):
                    try:
                        existing = await get_session_files(session["id"])
                        prior_n_images = sum(1 for f in existing if f.get("type") == "image")
                        prior_n_audios = sum(1 for f in existing if f.get("type") == "audio")
                    except Exception:
                        prior_n_images = 0
                        prior_n_audios = 0

                    if inferred_type == "image" and prior_n_images >= ABUSE_CAP_IMAGES:
                        await send_message(
                            from_phone,
                            f"Ya recibí {prior_n_images} fotos 😅 — es mucho material.\n\n"
                            f"Escribe *generar* para analizar las *{MAX_IMAGES_PER_BATCH} más recientes*, o *otro* para empezar un demo nuevo.",
                            from_number=to_number,
                        )
                        logger.info("demo_abuse_cap_rejected", phone=phone, type="image", current=prior_n_images)
                        continue
                    if inferred_type == "audio" and prior_n_audios >= ABUSE_CAP_AUDIOS:
                        await send_message(
                            from_phone,
                            f"Ya recibí {prior_n_audios} audios 😅 — suficiente.\n\n"
                            f"Escribe *generar* para analizar los *{MAX_AUDIOS_PER_BATCH} más recientes*.",
                            from_number=to_number,
                        )
                        logger.info("demo_abuse_cap_rejected", phone=phone, type="audio", current=prior_n_audios)
                        continue

            # Download media and upload to Supabase Storage
            try:
                file_meta = await download_and_store(
                    media_url=media_url,
                    content_type=content_type,
                    session_id=session["id"],
                    user_phone=phone,
                )
            except UnsupportedMediaError as ume:
                logger.info("media_rejected_unsupported", phone=phone, content_type=ume.content_type)
                await send_message(
                    from_phone,
                    "Este demo solo procesa *fotos*, *audios* y *videos*. "
                    "PDFs, documentos, stickers y contactos no se pueden analizar. "
                    "Envía una foto para probar.",
                    from_number=to_number,
                )
                continue

            # Add file to session
            await handle_media(phone, file_meta)

            # Pre-process in background via queue (content safety + vision description)
            impl_id = session.get("implementation", settings.default_implementation)
            from src.engine.worker import enqueue_preprocess
            await enqueue_preprocess(session["id"], file_meta, implementation=impl_id)

            ftype = file_meta.get("type")

            if demo_mode and batch_mode == "instant" and ftype == "image":
                # Legacy: single-photo → inline report
                await send_message(
                    from_phone,
                    "Recibí tu foto 📸\nAnalizando con múltiples modelos de IA… te envío el reporte en unos segundos 🔍",
                    from_number=to_number,
                )
                asyncio.create_task(
                    _run_demo_analysis_safe(
                        session_id=session["id"],
                        file_meta=file_meta,
                        impl_config=impl_config,
                        phone=phone,
                        from_phone=from_phone,
                        to_number=to_number,
                    )
                )
            elif demo_mode and batch_mode == "explicit":
                # Batch mode: ack receipt, wait for explicit trigger keyword
                label = {
                    "image": "foto 📸",
                    "audio": "audio 🎤",
                    "video": "video 🎬",
                }.get(ftype, "archivo")
                # Count files accumulated today (post-add)
                try:
                    all_files = await get_session_files(session["id"])
                    total_images = sum(1 for f in all_files if f.get("type") == "image")
                    total_audios = sum(1 for f in all_files if f.get("type") == "audio")
                    total = sum(1 for f in all_files if f.get("type") in ("image", "audio", "video"))
                except Exception:
                    total_images = 1 if ftype == "image" else 0
                    total_audios = 1 if ftype == "audio" else 0
                    total = 1

                base = f"Recibí tu {label} ({total} archivo{'s' if total != 1 else ''})."

                # Soft-cap messaging: over the analysis limit but not blocked
                if ftype == "image" and total_images > MAX_IMAGES_PER_BATCH:
                    ack = (
                        f"{base}\n\n"
                        f"📸 El demo analiza las *{MAX_IMAGES_PER_BATCH} fotos más recientes* al escribir *generar*. "
                        f"Tienes {total_images} en total, así que el reporte usará las últimas {MAX_IMAGES_PER_BATCH}.\n\n"
                        f"_En la versión completa de Radar Xponencial analizamos cientos de fotos por usuario al día._"
                    )
                elif ftype == "image" and total_images == MAX_IMAGES_PER_BATCH:
                    ack = (
                        f"{base}\n\n"
                        f"✅ Llegaste a *{MAX_IMAGES_PER_BATCH} fotos* — el tope del demo para un reporte. "
                        f"Puedes enviar más si quieres, pero solo las *{MAX_IMAGES_PER_BATCH} más recientes* se incluirán en el análisis. "
                        f"Escribe *generar* cuando estés listo."
                    )
                elif ftype == "audio" and total_audios > MAX_AUDIOS_PER_BATCH:
                    ack = (
                        f"{base}\n\n"
                        f"🎤 El demo usa los *{MAX_AUDIOS_PER_BATCH} audios más recientes*. Envía más fotos o escribe *generar* cuando termines."
                    )
                else:
                    ack = (
                        f"{base}\n\n"
                        f"Envía más si quieres o escribe *generar* cuando termines para ver el análisis."
                    )
                await send_message(from_phone, ack, from_number=to_number)

                # Location prompt: if this was the first visual piece of material
                # in the session AND there's no location yet AND we haven't already
                # prompted (pending_location_active), ask now.
                try:
                    visual_total = sum(1 for f in all_files if f.get("type") in ("image", "audio", "video"))
                    has_location = any(f.get("type") == "location" for f in all_files)
                    if (
                        visual_total == 1
                        and not has_location
                        and not pending_location_active
                    ):
                        from src.engine.supabase_client import set_pending_location_request
                        await set_pending_location_request(phone)
                        pending_location_active = True
                        await send_message(
                            from_phone,
                            "¿Dónde tomaste esto? 📍\n\n"
                            "Para que el análisis sea más preciso, cuéntame dónde estás:\n\n"
                            "📎 *Opción 1*: Comparte tu ubicación desde el menú adjuntar de WhatsApp\n"
                            "✍️ *Opción 2*: Escríbeme una descripción breve\n"
                            "   _Ejemplos: \"supermercado Éxito Chapinero\", \"norte de Bogotá\", \"Mercadona Madrid centro\"_\n\n"
                            "Puedes seguir enviando material mientras tanto. Al escribir *generar* analizo todo junto.",
                            from_number=to_number,
                        )
                        logger.info("location_prompt_sent", phone=phone, session_id=session["id"][:8])
                except Exception as e:
                    logger.warning("location_prompt_failed", phone=phone, error=str(e))
            else:
                # Field-agent flow: accumulate and wait for "reporte" trigger word
                file_count = len(session.get("raw_files", [])) + 1
                hint_template = (impl_config.onboarding_config.get("first_photo_hint") if impl_config else None) or "Recibido ({count} archivo(s) hoy). Escribe *reporte* cuando termines."
                await send_message(from_phone, hint_template.replace("{count}", str(file_count)))

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

        # ── POC gating flow ────────────────────────────────────────
        # "POC" intent: user explicitly asked for a personalized POC. Set the
        # pending flag and prompt for the client company name.
        is_demo_impl = bool(impl_config and impl_config.onboarding_config.get("demo_mode"))
        if is_demo_impl and body_lower in POC_KEYWORDS:
            from src.engine.supabase_client import set_pending_poc_selection, upsert_user
            if not user:
                await upsert_user(phone, resolved_impl or settings.default_implementation)
            await set_pending_poc_selection(phone)
            await send_message(
                from_phone,
                "Los POCs de Radar Xponencial están personalizados para clientes específicos 🎯\n\n"
                "Escribe el nombre de tu empresa para activar el demo con sus frameworks reales:\n\n"
                "• *argos*\n"
                "• *telecable*\n\n"
                "O escribe *retail* si prefieres el demo general de CPG.",
                from_number=to_number,
            )
            logger.info("poc_prompt_sent", phone=phone, impl=resolved_impl)
            twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
            return Response(content=twiml, media_type="application/xml")

        # Pending POC follow-up: user previously tapped POC and is expected to
        # reply with a company name. Step 1 at the top already handles the
        # happy path when they type "argos"/"telecable" (keyword switch fires),
        # so reaching this branch means either a defensive same-impl case or
        # the user typed something that isn't a recognized command.
        if is_demo_impl and pending_poc_active:
            from src.engine.supabase_client import (
                clear_pending_poc_selection as _clear_poc,
                upsert_user as _upsert_user,
                update_session_implementation_today as _update_session_impl,
                clear_session_files_today as _clear_files,
            )
            if body_lower in POC_COMPANY_KEYWORDS:
                # Defensive — Step 1 would normally handle this. Clear and fall through.
                await _clear_poc(phone)
                pending_poc_active = False
            elif body_lower in DEMO_ESCAPE_KEYWORDS:
                # User escaped with a known command; let the downstream handlers run.
                await _clear_poc(phone)
                pending_poc_active = False
            else:
                # Unknown text while pending POC → redirect to retail demo gracefully.
                await _clear_poc(phone)
                pending_poc_active = False
                target_impl_id = "laundry_care"
                try:
                    from src.engine.config_loader import get_implementation
                    target_config = await get_implementation(target_impl_id)
                    await _upsert_user(phone, target_impl_id)
                    await _update_session_impl(phone, target_impl_id)
                    await _clear_files(phone)
                    post_switch = (target_config.onboarding_config or {}).get(
                        "post_switch_message",
                        "Cambiado al *Demo Retail*. Enviame fotos y escribe *generar* cuando termines.",
                    )
                    await send_message(
                        from_phone,
                        "No reconocí ese cliente como un POC disponible 🤔\n\n"
                        "Te llevo al *Demo Retail general* para que veas cómo funciona Radar Xponencial. "
                        "Si querías otra empresa, escribe *argos* o *telecable* después.",
                        from_number=to_number,
                    )
                    await send_message(from_phone, post_switch, from_number=to_number)
                    logger.info("poc_wrong_name_redirected", phone=phone, wrote=body_lower[:30])
                except Exception as e:
                    logger.error("poc_redirect_failed", phone=phone, error=str(e))
                twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
                return Response(content=twiml, media_type="application/xml")

        # Pending location follow-up: user was asked for their location and the
        # next non-command text is saved as a free-form description.
        if is_demo_impl and pending_location_active:
            from src.engine.supabase_client import (
                clear_pending_location_request as _clear_loc,
                add_text_location_to_session,
                get_or_create_session as _get_session,
            )
            if body_lower in DEMO_ESCAPE_KEYWORDS or body_lower in POC_KEYWORDS or body_lower in POC_COMPANY_KEYWORDS:
                # Escape — user ignored the prompt, let the downstream handlers run.
                await _clear_loc(phone)
                pending_location_active = False
            else:
                # Treat as a location description
                import datetime as _dt
                sess = await _get_session(phone, _dt.date.today(), resolved_impl)
                await add_text_location_to_session(sess["id"], body)
                await _clear_loc(phone)
                pending_location_active = False
                await send_message(
                    from_phone,
                    f"Anotado 📍 _{body[:120]}_\n\n"
                    f"Sigue enviando material (fotos, audios, videos) o escribe *generar* cuando termines.",
                    from_number=to_number,
                )
                logger.info("text_location_captured", phone=phone, chars=len(body))
                twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
                return Response(content=twiml, media_type="application/xml")

        # Pending contact capture: if user previously wrote "contacto" and we're
        # still within the TTL window, treat this text as the lead payload.
        if user and user.get("pending_contact_request_at"):
            try:
                import datetime as _dt
                pending_at_raw = user["pending_contact_request_at"]
                pending_at = _dt.datetime.fromisoformat(pending_at_raw.replace("Z", "+00:00"))
                age_min = (_dt.datetime.now(_dt.UTC) - pending_at).total_seconds() / 60
            except Exception:
                age_min = 999
            if age_min < PENDING_CONTACT_TTL_MIN:
                from src.engine.supabase_client import save_demo_lead, clear_pending_contact_request
                from src.engine.phone_geo import detect_country
                country_tuple = detect_country(phone)
                country_name = country_tuple[1] if country_tuple else None
                await save_demo_lead(
                    phone=phone,
                    implementation=resolved_impl,
                    country=country_name,
                    payload=body,
                )
                await clear_pending_contact_request(phone)
                await send_message(
                    from_phone,
                    "¡Gracias! 🙌 Alguien del equipo de Radar Xponencial te va a contactar en menos de 24h hábiles.\n\n"
                    "Mientras tanto, si quieres seguir explorando escribe *otro* para probar el otro demo o envía más fotos para otro análisis.",
                    from_number=to_number,
                )
                logger.info("demo_lead_captured", phone=phone, impl=resolved_impl)
                twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
                return Response(content=twiml, media_type="application/xml")
            else:
                # Stale pending flag — clear silently and fall through to normal handling
                from src.engine.supabase_client import clear_pending_contact_request
                await clear_pending_contact_request(phone)

        # Demo CTA handlers: active only when current impl is in demo_mode
        if impl_config and impl_config.onboarding_config.get("demo_mode"):
            # "otro" — switch to the other demo (fresh session)
            if body_lower in CTA_OTRO_KEYWORDS:
                target_impl_id = OTHER_DEMO_MAP.get(resolved_impl)
                if target_impl_id:
                    try:
                        from src.engine.config_loader import get_implementation
                        from src.engine.supabase_client import (
                            upsert_user,
                            update_session_implementation_today,
                            clear_session_files_today,
                        )
                        target_config = await get_implementation(target_impl_id)
                        await upsert_user(phone, target_impl_id)
                        await update_session_implementation_today(phone, target_impl_id)
                        await clear_session_files_today(phone)
                        post_switch = target_config.onboarding_config.get(
                            "post_switch_message",
                            f"Cambiado a *{target_config.name}*. Envíame fotos y escribe *generar* cuando termines.",
                        )
                        await send_message(from_phone, post_switch, from_number=to_number)
                        logger.info("cta_otro_switched", phone=phone, from_impl=resolved_impl, to_impl=target_impl_id)
                    except Exception as e:
                        logger.error("cta_otro_failed", phone=phone, error=str(e))
                        await send_message(from_phone, "No pude cambiar de demo en este momento. Escribe *menu* para ver las opciones.", from_number=to_number)
                else:
                    await send_message(from_phone, "No hay otro demo disponible ahora mismo. Escribe *menu* para ver opciones.", from_number=to_number)
                twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
                return Response(content=twiml, media_type="application/xml")

            # "contacto" — prompt for contact info and set pending flag
            if body_lower in CTA_CONTACTO_KEYWORDS:
                from src.engine.supabase_client import set_pending_contact_request, upsert_user
                # Ensure user row exists first (pending flag needs a row)
                if not user:
                    await upsert_user(phone, resolved_impl or settings.default_implementation)
                await set_pending_contact_request(phone)
                await send_message(
                    from_phone,
                    "💬 ¡Perfecto! Déjanos tus datos en un solo mensaje para contactarte:\n\n"
                    "*Nombre*, *empresa*, y *email* o *LinkedIn*.\n\n"
                    "Ejemplo: _María López, Mondelez España, maria@mondelez.com_",
                    from_number=to_number,
                )
                logger.info("cta_contacto_prompted", phone=phone, impl=resolved_impl)
                twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
                return Response(content=twiml, media_type="application/xml")

        # Demo mode trigger: if impl is in demo_mode and user types a trigger keyword,
        # gather today's session files and generate a consolidated report.
        if (
            impl_config
            and impl_config.onboarding_config.get("demo_mode")
            and body_lower in DEMO_TRIGGER_KEYWORDS
        ):
            import datetime as _dt
            from src.engine.supabase_client import get_or_create_session
            # Silently clear any pending location — user is ready to generate
            if pending_location_active:
                try:
                    from src.engine.supabase_client import clear_pending_location_request
                    await clear_pending_location_request(phone)
                    pending_location_active = False
                except Exception:
                    pass
            session = await get_or_create_session(phone, _dt.date.today(), resolved_impl)
            await send_message(
                from_phone,
                "Generando análisis de todo lo que enviaste… 🔍\nTe envío el reporte en unos segundos.",
                from_number=to_number,
            )
            asyncio.create_task(
                _run_demo_batch_safe(
                    session_id=session["id"],
                    impl_config=impl_config,
                    phone=phone,
                    from_phone=from_phone,
                    to_number=to_number,
                )
            )
            logger.info("demo_batch_triggered", phone=phone, impl=impl_config.id, session_id=session["id"][:8])
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


async def _run_demo_analysis_safe(
    session_id: str,
    file_meta: dict,
    impl_config,
    phone: str,
    from_phone: str,
    to_number: str,
) -> None:
    """Run demo instant analysis in background and send the report via WhatsApp.

    Uses tiered Haiku vision + Haiku synthesis. ~10-20s total. Caught errors
    send a friendly fallback message and log the failure.
    """
    try:
        from src.engine.demo_analyzer import generate_single_photo_demo_report
        from src.engine.phone_geo import detect_country

        country_tuple = detect_country(phone)
        country_name = country_tuple[1] if country_tuple else None

        storage_path = file_meta.get("storage_path")
        if not storage_path:
            raise RuntimeError("missing_storage_path")

        report = await generate_single_photo_demo_report(
            storage_path=storage_path,
            impl_config=impl_config,
            country_name=country_name,
            audio_context=None,
            location_hint=None,
        )

        await send_message(from_phone, report, from_number=to_number)
        logger.info(
            "demo_analysis_delivered",
            phone=phone,
            impl=impl_config.id,
            session_id=session_id[:8],
            country=country_name,
        )
    except Exception as e:
        logger.error(
            "demo_analysis_failed",
            phone=phone,
            impl=getattr(impl_config, "id", "?"),
            session_id=session_id[:8],
            error=str(e)[:200],
        )
        try:
            await send_message(
                from_phone,
                "No pude analizar esta foto en este momento 😔. "
                "Intenta con otra imagen del punto de venta o publicidad. "
                "Si el problema persiste, escribe *menu* para ver otras opciones.",
                from_number=to_number,
            )
        except Exception:
            pass


async def _run_demo_batch_safe(
    session_id: str,
    impl_config,
    phone: str,
    from_phone: str,
    to_number: str,
) -> None:
    """Run consolidated demo batch analysis on all files in today's session.

    Triggered when user types a demo trigger keyword ("generar", "reporte", etc).
    Reads all session_files, runs parallel vision + audio transcription,
    synthesizes one WhatsApp report, and sends it back.
    """
    try:
        from src.engine.demo_analyzer import generate_demo_report
        from src.engine.phone_geo import detect_country, country_by_iso
        from src.engine.supabase_client import get_session_files

        files = await get_session_files(session_id)
        images = [f for f in files if f.get("type") == "image" and f.get("storage_path")]
        videos = [f for f in files if f.get("type") == "video" and f.get("storage_path")]
        audios = [f for f in files if f.get("type") == "audio" and f.get("storage_path")]
        locations = [f for f in files if f.get("type") == "location"]

        if not images and not videos:
            if audios:
                msg = (
                    "Recibí tu(s) audio(s) 🎤 pero para el análisis necesito al menos "
                    "una *foto* o *video* del punto de venta, publicidad o lo que quieras analizar.\n\n"
                    "Envía una imagen y luego escribe *generar*."
                )
            else:
                msg = (
                    "Aún no recibí ningún material 🤔\n\n"
                    "Envíame al menos una *foto* o *video* del lugar y luego escribe *generar*."
                )
            await send_message(from_phone, msg, from_number=to_number)
            logger.info(
                "demo_batch_no_visual",
                phone=phone,
                session_id=session_id[:8],
                audios=len(audios),
            )
            return

        # Use the most recently shared location as hint for the analysis
        location_hint: str | None = None
        if locations:
            last_loc = locations[-1]
            addr = (last_loc.get("address") or "").strip()
            label = (last_loc.get("label") or "").strip()
            if label and addr:
                location_hint = f"{label} — {addr}"
            elif addr or label:
                location_hint = addr or label
            elif last_loc.get("latitude") and last_loc.get("longitude"):
                location_hint = f"Lat {last_loc['latitude']}, Lng {last_loc['longitude']}"

        # Country resolution per impl config:
        #   auto  (default) → detect from phone prefix
        #   fixed           → always use onboarding_config.country_fixed_iso
        #   none            → skip country context in the prompt
        country_mode = impl_config.onboarding_config.get("country_mode", "auto")
        country_name: str | None = None
        if country_mode == "fixed":
            fixed_iso = impl_config.onboarding_config.get("country_fixed_iso")
            resolved = country_by_iso(fixed_iso)
            country_name = resolved[1] if resolved else None
        elif country_mode == "auto":
            country_tuple = detect_country(phone)
            country_name = country_tuple[1] if country_tuple else None
        # country_mode == "none" → country_name stays None

        report = await generate_demo_report(
            files=files,
            impl_config=impl_config,
            country_name=country_name,
            location_hint=location_hint,
            text_context=None,
        )

        await send_message(from_phone, report, from_number=to_number)
        logger.info(
            "demo_batch_delivered",
            phone=phone,
            impl=impl_config.id,
            session_id=session_id[:8],
            country=country_name,
            total_files=len(files),
            images=len(images),
        )

        # CTA footer — sent as separate message so it renders below the report
        if impl_config.onboarding_config.get("cta_footer_enabled", True):
            cta_footer = (
                "━━━━━━━━━━━━━━━━━━━━\n"
                "*¿Qué sigue?*\n\n"
                "📊 Escribe *otro* para probar el otro demo\n"
                "💬 Escribe *contacto* para dejar tus datos y conversar con nuestro equipo"
            )
            try:
                await send_message(from_phone, cta_footer, from_number=to_number)
            except Exception as e:
                logger.warning("cta_footer_send_failed", phone=phone, error=str(e))
    except Exception as e:
        logger.error(
            "demo_batch_failed",
            phone=phone,
            impl=getattr(impl_config, "id", "?"),
            session_id=session_id[:8],
            error=str(e)[:200],
        )
        try:
            await send_message(
                from_phone,
                "No pude generar el análisis en este momento 😔\n\n"
                "Intenta enviar las fotos de nuevo o escribe *menu* para ver otras opciones.",
                from_number=to_number,
            )
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
