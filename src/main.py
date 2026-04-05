"""Field Genius Engine — FastAPI entry point."""

import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    HAS_SLOWAPI = True
except ImportError:
    HAS_SLOWAPI = False

from src.channels.whatsapp.webhook import router as webhook_router
from src.routes.simulate import router as simulate_router
from src.routes.admin import router as admin_router
from src.config.settings import settings
from src.utils.logger import setup_logging

setup_logging()

# Rate limiter — uses client IP by default
if HAS_SLOWAPI:
    limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
else:
    limiter = None

# Fail-fast: warn about missing critical secrets at startup
_missing = []
if not settings.anthropic_api_key:
    _missing.append("ANTHROPIC_API_KEY")
if not settings.openai_api_key:
    _missing.append("OPENAI_API_KEY")
if not settings.supabase_service_role_key:
    _missing.append("SUPABASE_SERVICE_ROLE_KEY")
if _missing:
    import sys
    print(f"FATAL: Missing required env vars: {', '.join(_missing)}", file=sys.stderr)
    sys.exit(1)

app = FastAPI(
    title="Field Genius Engine API",
    version="1.0.0",
    description="""Field Intelligence Platform — captures field photos, audio, and video via WhatsApp,
processes them with AI (Claude Vision + Whisper), and generates strategic reports.

## Authentication
All `/api/admin/*` endpoints require a Supabase JWT token in the `Authorization: Bearer <token>` header.
Obtain a token by signing in via the backoffice at `field-genius-backoffice.vercel.app`.

## Rate Limits
- Global: 120 requests/minute per IP
- AI-invoking endpoints: 5-20 requests/minute (see endpoint descriptions)
- Rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## Versioning
Routes are available at both `/api/admin/*` (current) and `/v1/api/admin/*` (versioned).
New integrations should use the `/v1/` prefix.
""",
    openapi_tags=[
        {"name": "admin", "description": "Backoffice administration — implementations, users, sessions, reports"},
        {"name": "webhook", "description": "WhatsApp webhook for Twilio"},
    ],
    docs_url="/docs",
    redoc_url="/redoc",
)
if HAS_SLOWAPI and limiter:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Standardized error responses
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from src.routes.errors import http_exception_handler, validation_exception_handler, generic_exception_handler
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Add X-Request-Id to every response + bind to structlog for correlation."""
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4())[:8])
        import structlog
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
)

app.include_router(webhook_router)

# V1 API — versioned routes
app.include_router(admin_router, prefix="/v1")  # /v1/api/admin/*

# Backwards compat — also mount at root (will deprecate)
app.include_router(admin_router)  # /api/admin/*

# Simulate router only in development (not production)
_is_dev = settings.environment.lower() in ("development", "dev", "local")
if _is_dev:
    app.include_router(simulate_router)


@app.on_event("startup")
async def startup() -> None:
    """Initialize thread pool + Redis connection pool on startup."""
    # Increase thread pool for async-wrapped sync calls (Supabase, etc.)
    import asyncio
    import concurrent.futures
    loop = asyncio.get_event_loop()
    loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=100))

    if settings.redis_url:
        try:
            from src.engine.worker import get_pool
            pool = await get_pool()
            if pool:
                import structlog
                structlog.get_logger().info("redis_connected", url=settings.redis_url[:30])
        except Exception as e:
            import structlog
            structlog.get_logger().warning("redis_startup_failed_continuing_without", error=str(e))


@app.on_event("shutdown")
async def shutdown() -> None:
    """Graceful shutdown: close Redis pool."""
    try:
        from src.engine.worker import _pool
        if _pool:
            await _pool.close()
            import structlog
            structlog.get_logger().info("redis_pool_closed")
    except Exception:
        pass


@app.get("/health")
async def health() -> dict:
    """Basic health check — always returns quickly."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/deep")
async def health_deep() -> dict:
    """Deep health check — verifies all dependencies."""
    checks: dict[str, str] = {}

    # Redis
    try:
        from src.engine.worker import get_queue_stats
        queue = await get_queue_stats()
        checks["redis"] = queue.get("status", "unknown")
    except Exception:
        checks["redis"] = "error"

    # Supabase
    try:
        from src.engine.supabase_client import list_users
        await list_users(limit=1)
        checks["supabase"] = "ok"
    except Exception:
        checks["supabase"] = "error"

    # Anthropic API key
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=5.0)
        await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=5,
            messages=[{"role": "user", "content": "ping"}],
        )
        checks["anthropic"] = "ok"
    except Exception:
        checks["anthropic"] = "error"

    # OpenAI (check key format only — no API call to save cost)
    checks["openai"] = "ok" if settings.openai_api_key.startswith("sk-") else "missing"

    # Twilio
    checks["twilio"] = "ok" if settings.twilio_auth_token else "missing"

    all_ok = all(v == "ok" for v in checks.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "version": "1.0.0",
        "checks": checks,
    }


if _is_dev:
    @app.get("/api/test-db")
    async def test_db() -> JSONResponse:
        """Query Supabase and return the first user from seed data. Dev only."""
        try:
            from src.engine.supabase_client import list_users
            users = await list_users(limit=1)
            if not users:
                return JSONResponse(content={"success": True, "data": None, "error": "No users found"})
            return JSONResponse(content={"success": True, "data": users[0], "error": None})
        except Exception as e:
            return JSONResponse(status_code=500, content={"success": False, "data": None, "error": "DB check failed"})
