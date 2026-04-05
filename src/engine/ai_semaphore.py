"""Shared AI semaphore — limits concurrent AI API calls across all modules.

Prevents thundering herd on Anthropic/OpenAI APIs when many requests
trigger AI processing simultaneously.
"""

from __future__ import annotations

import asyncio

# Max concurrent AI API calls (Anthropic + OpenAI combined)
MAX_CONCURRENT_AI = 40

_semaphore: asyncio.Semaphore | None = None


def get_ai_semaphore() -> asyncio.Semaphore:
    """Get the shared AI semaphore (lazy init for event loop compatibility)."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_AI)
    return _semaphore
