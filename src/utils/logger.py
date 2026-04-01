"""Structured logging via structlog — JSON in production, colored in dev."""

import os
import structlog


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
            structlog.processors.StackInfoRenderer(),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
