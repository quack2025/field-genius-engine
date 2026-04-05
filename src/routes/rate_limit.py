"""Shared rate limiter — single instance used by main.py and all routes."""

from __future__ import annotations

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
    HAS_SLOWAPI = True
except ImportError:
    limiter = None  # type: ignore[assignment]
    HAS_SLOWAPI = False
