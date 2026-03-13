"""Field Genius Engine — FastAPI entry point."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.channels.whatsapp.webhook import router as webhook_router
from src.routes.simulate import router as simulate_router
from src.routes.admin import router as admin_router
from src.utils.logger import setup_logging

setup_logging()

app = FastAPI(
    title="Field Genius Engine",
    version="0.1.0",
    description="Multimodal capture → AI → structured reports",
)
app.include_router(webhook_router)
app.include_router(simulate_router)
app.include_router(admin_router)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "implementation": "field-genius-engine",
        "version": "0.1.0",
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
