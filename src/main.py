"""Field Genius Engine — FastAPI entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.channels.whatsapp.webhook import router as webhook_router
from src.routes.simulate import router as simulate_router
from src.routes.admin import router as admin_router
from src.config.settings import settings
from src.utils.logger import setup_logging

setup_logging()

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
    title="Field Genius Engine",
    version="0.1.0",
    description="Multimodal capture → AI → structured reports",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://field-genius-backoffice.vercel.app",
        "https://xponencial.net",
        "https://www.xponencial.net",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)
app.include_router(simulate_router)
app.include_router(admin_router)


@app.on_event("startup")
async def startup() -> None:
    """Initialize Redis connection pool on startup (if configured)."""
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


@app.get("/health")
async def health() -> dict:
    from src.engine.worker import get_queue_stats
    queue = await get_queue_stats()
    return {
        "status": "ok",
        "implementation": "field-genius-engine",
        "version": "0.2.0",
        "queue": queue,
    }


@app.get("/api/test-db")
async def test_db() -> JSONResponse:
    """Query Supabase and return the first user from seed data."""
    try:
        from src.engine.supabase_client import list_users

        users = await list_users(limit=1)
        if not users:
            return JSONResponse(
                content={"success": True, "data": None, "error": "No users found — run seed.sql first"},
            )
        return JSONResponse(content={"success": True, "data": users[0], "error": None})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "data": None, "error": str(e)},
        )
