"""Supabase service — async functions for sessions, reports, and users."""

from __future__ import annotations

import datetime
from typing import Any

import structlog
from supabase import create_client, Client

from src.config.settings import settings

logger = structlog.get_logger(__name__)

_client: Client | None = None


def get_client() -> Client:
    """Return a singleton Supabase client using service_role_key for full access."""
    global _client
    if _client is None:
        # Use service_role_key to bypass RLS (backend service, not user-facing)
        key = settings.supabase_service_role_key or settings.supabase_anon_key
        _client = create_client(settings.supabase_url, key)
        logger.info("supabase_client_initialized", url=settings.supabase_url)
    return _client


async def get_user_by_phone(phone: str) -> dict[str, Any] | None:
    """Look up a user by WhatsApp phone number."""
    logger.info("get_user_by_phone", phone=phone)
    client = get_client()
    result = client.table("users").select("*").eq("phone", phone).maybe_single().execute()
    return result.data


async def get_or_create_session(
    phone: str, date: datetime.date
) -> dict[str, Any]:
    """Get existing session for user+date or create a new one."""
    logger.info("get_or_create_session", phone=phone, date=str(date))
    client = get_client()

    # Try to find existing session
    result = (
        client.table("sessions")
        .select("*")
        .eq("user_phone", phone)
        .eq("date", str(date))
        .maybe_single()
        .execute()
    )
    if result and result.data:
        return result.data

    # Look up user name
    user = await get_user_by_phone(phone)
    user_name = user["name"] if user else phone

    # Create new session
    new_session = {
        "user_phone": phone,
        "user_name": user_name,
        "date": str(date),
        "status": "accumulating",
        "raw_files": [],
    }
    result = client.table("sessions").insert(new_session).execute()
    logger.info("session_created", session_id=result.data[0]["id"])
    return result.data[0]


async def add_file_to_session(session_id: str, file_metadata: dict[str, Any]) -> None:
    """Append a file entry to a session's raw_files array."""
    logger.info("add_file_to_session", session_id=session_id)
    client = get_client()

    # Fetch current files
    session = (
        client.table("sessions").select("raw_files").eq("id", session_id).single().execute()
    )
    files: list[dict[str, Any]] = session.data["raw_files"] or []
    files.append(file_metadata)

    client.table("sessions").update(
        {"raw_files": files, "updated_at": datetime.datetime.now(datetime.UTC).isoformat()}
    ).eq("id", session_id).execute()


async def get_session(session_id: str) -> dict[str, Any] | None:
    """Get a session by ID."""
    logger.info("get_session", session_id=session_id)
    client = get_client()
    result = client.table("sessions").select("*").eq("id", session_id).maybe_single().execute()
    return result.data


async def update_session_status(session_id: str, status: str) -> None:
    """Update session status."""
    logger.info("update_session_status", session_id=session_id, status=status)
    client = get_client()
    client.table("sessions").update(
        {"status": status, "updated_at": datetime.datetime.now(datetime.UTC).isoformat()}
    ).eq("id", session_id).execute()


async def save_visit_report(report: dict[str, Any]) -> str:
    """Insert a visit report and return its ID."""
    logger.info("save_visit_report", session_id=report.get("session_id"))
    client = get_client()
    result = client.table("visit_reports").insert(report).execute()
    report_id: str = result.data[0]["id"]
    logger.info("visit_report_saved", report_id=report_id)
    return report_id


async def list_users(limit: int = 10) -> list[dict[str, Any]]:
    """List users (for health check / test)."""
    client = get_client()
    result = client.table("users").select("*").limit(limit).execute()
    return result.data or []
