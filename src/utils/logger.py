"""Structured logging via structlog — JSON in production, colored in dev."""

import os
import re
import structlog


def mask_phone(phone: str) -> str:
    """Mask a phone number for PII-safe logging: +57***4567."""
    if not phone:
        return ""
    # Strip whatsapp: prefix
    clean = phone.replace("whatsapp:", "")
    # Keep country code (first 3 chars) + last 4 digits
    if len(clean) > 7:
        return clean[:3] + "***" + clean[-4:]
    return "***" + clean[-4:] if len(clean) > 4 else "****"


def _mask_phone_processor(logger: object, method_name: str, event_dict: dict) -> dict:
    """Structlog processor that auto-masks phone fields in log entries."""
    phone_fields = ("phone", "to_phone", "from_phone", "user_phone", "to")
    for field in phone_fields:
        if field in event_dict and isinstance(event_dict[field], str):
            event_dict[field] = mask_phone(event_dict[field])
    return event_dict


def setup_logging() -> None:
    """Configure structlog. JSON for production, console for development."""
    env = os.environ.get("ENVIRONMENT", "production").lower()
    is_dev = env in ("development", "dev", "local")

    if is_dev:
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _mask_phone_processor,  # Auto-mask PII in phone fields
            structlog.processors.StackInfoRenderer(),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
