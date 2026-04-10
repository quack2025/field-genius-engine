"""Job queue worker — rate-limited pre-processing of media files.

Uses arq (async Redis queue) to process files in background with backpressure.
If the queue fills up, files wait and get processed in batches a few minutes later.

Architecture:
  WhatsApp webhook → enqueue_preprocess() → Redis queue
  Worker process → consume at safe rate → Vision AI / Whisper → update raw_files

The worker runs embedded in the same FastAPI process (via startup event).
For higher scale, run as a separate process: `arq src.engine.worker.WorkerSettings`
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from arq import create_pool
from arq.connections import RedisSettings, ArqRedis

from src.config.settings import settings

logger = structlog.get_logger(__name__)

# Connection pool singleton
_pool: ArqRedis | None = None

# Concurrency control — limits how many AI calls run simultaneously
_semaphore: asyncio.Semaphore | None = None
MAX_CONCURRENT = 40  # Anthropic Tier 3 = 50 concurrent, leave headroom


def _get_redis_settings() -> RedisSettings | None:
    """Parse REDIS_URL into arq RedisSettings."""
    url = settings.redis_url
    if not url:
        return None
    # arq accepts RedisSettings or a redis URL
    # Parse: redis://default:password@host:port
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return RedisSettings(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            password=parsed.password or None,
            database=0,
        )
    except Exception as e:
        logger.error("redis_url_parse_failed", url=url[:30], error=str(e))
        return None


async def get_pool() -> ArqRedis | None:
    """Get or create the arq Redis connection pool."""
    global _pool
    if _pool is not None:
        return _pool

    redis_settings = _get_redis_settings()
    if not redis_settings:
        logger.warning("redis_not_configured_using_inline_processing")
        return None

    try:
        _pool = await create_pool(redis_settings)
        logger.info("arq_pool_created", host=redis_settings.host)
        return _pool
    except Exception as e:
        logger.error("arq_pool_failed", error=str(e))
        return None


async def enqueue_preprocess(
    session_id: str,
    file_meta: dict[str, Any],
    implementation: str = "",
) -> bool:
    """Enqueue a file for background pre-processing.

    Returns True if enqueued to Redis, False if falling back to inline processing.
    """
    pool = await get_pool()

    if pool is None:
        # Fallback: process inline (old behavior)
        from src.engine.preprocessor import preprocess_file
        asyncio.create_task(preprocess_file(session_id, file_meta, implementation))
        return False

    try:
        await pool.enqueue_job(
            "process_file",
            session_id=session_id,
            file_meta=file_meta,
            implementation=implementation,
            _queue_name="preprocess",
        )
        logger.info(
            "job_enqueued",
            session_id=session_id,
            filename=file_meta.get("filename"),
            queue="preprocess",
        )
        return True
    except Exception as e:
        logger.error("enqueue_failed", error=str(e))
        # Fallback to inline
        from src.engine.preprocessor import preprocess_file
        asyncio.create_task(preprocess_file(session_id, file_meta, implementation))
        return False


async def process_file(
    ctx: dict,
    session_id: str,
    file_meta: dict[str, Any],
    implementation: str = "",
) -> str:
    """arq worker function — processes a single file with rate limiting.

    The semaphore ensures we never exceed MAX_CONCURRENT AI API calls,
    even if hundreds of jobs are queued.
    """
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    filename = file_meta.get("filename", "?")
    file_type = file_meta.get("type", "unknown")

    start = time.time()
    logger.info("worker_processing", filename=filename, type=file_type, session_id=session_id[:8])

    async with _semaphore:
        from src.engine.preprocessor import preprocess_file
        await preprocess_file(session_id, file_meta, implementation)

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info("worker_done", filename=filename, elapsed_ms=elapsed_ms)

    return f"ok:{filename}:{elapsed_ms}ms"


async def _on_job_failure(ctx: dict, error: BaseException) -> None:
    """Called when a job fails after all retries. Saves to dead letter queue."""
    import json as _json
    job_id = ctx.get("job_id", "unknown")
    func_name = ctx.get("job_function_name", "unknown")
    args = ctx.get("job_args")

    logger.error("job_permanently_failed", job_id=job_id, function=func_name, error=str(error), error_type=type(error).__name__)
    try:
        from src.engine.supabase_client import get_client
        client = get_client()
        args_json = None
        if args:
            try:
                args_json = _json.loads(_json.dumps(args, default=str))
            except Exception:
                args_json = {"raw": str(args)[:500]}

        client.table("failed_jobs").insert({
            "job_id": str(job_id),
            "function_name": func_name,
            "args_json": args_json,
            "error": str(error)[:500],
            "error_type": type(error).__name__,
            "retries": ctx.get("job_try", 0),
        }).execute()
    except Exception:
        pass  # Best effort — don't crash the worker


async def get_queue_stats() -> dict[str, Any]:
    """Get queue statistics for monitoring."""
    pool = await get_pool()
    if not pool:
        return {"status": "no_redis", "queued": 0, "processing": 0}

    try:
        # arq stores jobs in Redis sorted sets
        queued = await pool.zcard(b"arq:queue:preprocess")  # type: ignore
        results = await pool.zcard(b"arq:results:preprocess")  # type: ignore
        return {
            "status": "connected",
            "queued": queued,
            "completed": results,
            "max_concurrent": MAX_CONCURRENT,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ── arq Worker Settings ──────────────────────────────────────────
# Used when running the worker as a standalone process:
#   arq src.engine.worker.WorkerSettings


class WorkerSettings:
    """arq worker configuration."""
    functions = [process_file]
    queue_name = "preprocess"
    max_jobs = MAX_CONCURRENT
    job_timeout = 300  # 5 min max per file (video can be slow)
    health_check_interval = 30
    retry_jobs = True
    max_tries = 3

    @staticmethod
    def redis_settings() -> RedisSettings:
        s = _get_redis_settings()
        if s is None:
            raise RuntimeError("REDIS_URL not configured")
        return s

    on_startup = None
    on_shutdown = None
