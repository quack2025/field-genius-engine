"""Supabase service — async functions for sessions, reports, and users.

Note: supabase-py is synchronous. All DB calls are wrapped in asyncio.to_thread()
to prevent blocking the FastAPI event loop under concurrent load.
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Any, TypeVar, Callable

import structlog
from supabase import create_client, Client

from src.config.settings import settings

logger = structlog.get_logger(__name__)

T = TypeVar("T")


async def _run(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a synchronous function in a thread pool to avoid blocking the event loop."""
    return await asyncio.to_thread(func, *args, **kwargs)

_client: Client | None = None


def get_client() -> Client:
    """Return a singleton Supabase client using service_role_key for full access."""
    global _client
    if _client is None:
        # Use service_role_key to bypass RLS (backend service, not user-facing)
        if not settings.supabase_service_role_key:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required — anon key is not safe for backend")
        _client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        logger.info("supabase_client_initialized", url=settings.supabase_url)
    return _client


async def get_user_by_phone(phone: str) -> dict[str, Any] | None:
    """Look up a user by WhatsApp phone number."""
    logger.info("get_user_by_phone", phone=phone)
    def _sync():
        client = get_client()
        result = client.table("users").select("*").eq("phone", phone).maybe_single().execute()
        return result.data if result else None
    return await _run(_sync)


async def get_or_create_session(
    phone: str, date: datetime.date
) -> dict[str, Any]:
    """Get existing session for user+date or create a new one."""
    logger.info("get_or_create_session", phone=phone, date=str(date))

    def _find():
        client = get_client()
        result = (
            client.table("sessions")
            .select("*")
            .eq("user_phone", phone)
            .eq("date", str(date))
            .maybe_single()
            .execute()
        )
        return result.data if result else None

    existing = await _run(_find)
    if existing:
        return existing

    # Look up user name and implementation
    user = await get_user_by_phone(phone)
    user_name = user["name"] if user else phone
    impl_id = (
        user.get("implementation", settings.default_implementation)
        if user
        else settings.default_implementation
    )
    user_country = user.get("country", "") if user else ""
    user_role = user.get("role", "field_agent") if user else "field_agent"

    new_session = {
        "user_phone": phone,
        "user_name": user_name,
        "date": str(date),
        "status": "accumulating",
        "raw_files": [],
        "implementation": impl_id,
        "country": user_country,
        "user_role": user_role,
    }

    def _insert():
        client = get_client()
        result = client.table("sessions").insert(new_session).execute()
        return result.data[0]

    session = await _run(_insert)
    logger.info("session_created", session_id=session["id"])
    return session


async def add_file_to_session(session_id: str, file_metadata: dict[str, Any]) -> None:
    """Append a file entry to a session's raw_files array (atomic)."""
    logger.info("add_file_to_session", session_id=session_id)

    import json

    def _sync():
        client = get_client()
        try:
            client.rpc("append_file_to_session", {
                "p_session_id": session_id,
                "p_file_meta": json.dumps(file_metadata),
            }).execute()
        except Exception:
            logger.warning("atomic_append_fallback", session_id=session_id)
            session = client.table("sessions").select("raw_files").eq("id", session_id).single().execute()
            files: list[dict[str, Any]] = session.data["raw_files"] or []
            files.append(file_metadata)
            client.table("sessions").update(
                {"raw_files": files, "updated_at": datetime.datetime.now(datetime.UTC).isoformat()}
            ).eq("id", session_id).execute()

    await _run(_sync)


async def update_file_in_session(
    session_id: str, filename: str, updates: dict[str, Any]
) -> None:
    """Update fields on a specific file entry in raw_files (atomic)."""
    import json

    def _sync():
        client = get_client()
        try:
            client.rpc("update_file_in_session", {
                "p_session_id": session_id,
                "p_filename": filename,
                "p_updates": json.dumps(updates),
            }).execute()
        except Exception:
            logger.warning("atomic_update_fallback", session_id=session_id)
            session = client.table("sessions").select("raw_files").eq("id", session_id).single().execute()
            files: list[dict[str, Any]] = session.data["raw_files"] or []
            for f in files:
                if f.get("filename") == filename:
                    f.update(updates)
                    break
            client.table("sessions").update(
                {"raw_files": files, "updated_at": datetime.datetime.now(datetime.UTC).isoformat()}
            ).eq("id", session_id).execute()

    await _run(_sync)


async def get_session(session_id: str) -> dict[str, Any] | None:
    """Get a session by ID."""
    logger.info("get_session", session_id=session_id)
    def _sync():
        client = get_client()
        result = client.table("sessions").select("*").eq("id", session_id).maybe_single().execute()
        return result.data
    return await _run(_sync)


async def update_session_status(session_id: str, status: str) -> None:
    """Update session status."""
    logger.info("update_session_status", session_id=session_id, status=status)
    def _sync():
        client = get_client()
        client.table("sessions").update(
            {"status": status, "updated_at": datetime.datetime.now(datetime.UTC).isoformat()}
        ).eq("id", session_id).execute()
    await _run(_sync)


async def save_visit_report(report: dict[str, Any]) -> str:
    """Insert a visit report and return its ID."""
    logger.info("save_visit_report", session_id=report.get("session_id"))
    def _sync():
        client = get_client()
        result = client.table("visit_reports").insert(report).execute()
        return result.data[0]["id"]
    report_id: str = await _run(_sync)
    logger.info("visit_report_saved", report_id=report_id)
    return report_id


async def update_user_implementation(phone: str, impl_id: str) -> None:
    """Change the active implementation for a user."""
    def _sync():
        client = get_client()
        client.table("users").update({
            "implementation": impl_id,
            "implementation_id": impl_id,
        }).eq("phone", phone).execute()
    await _run(_sync)
    logger.info("user_implementation_updated", phone=phone, implementation=impl_id)


async def list_active_implementations() -> list[dict[str, Any]]:
    """List all active implementations (for project menu)."""
    def _sync():
        client = get_client()
        result = (
            client.table("implementations")
            .select("id, name, industry")
            .eq("status", "active")
            .order("name")
            .execute()
        )
        return result.data or []
    return await _run(_sync)


async def list_users(limit: int = 10) -> list[dict[str, Any]]:
    """List users (for health check / test)."""
    def _sync():
        client = get_client()
        result = client.table("users").select("*").limit(limit).execute()
        return result.data or []
    return await _run(_sync)
