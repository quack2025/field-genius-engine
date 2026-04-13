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
    phone: str, date: datetime.date, implementation_override: str | None = None,
) -> dict[str, Any]:
    """Get existing session for user+date or create a new one.

    Args:
        implementation_override: If set, forces this implementation instead of user's default.
            Used when the webhook resolves implementation from the incoming Twilio number.
    """
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
    impl_id = implementation_override or (
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
    """Add a file to session — writes to session_files table (normalized) + raw_files (compat)."""
    logger.info("add_file_to_session", session_id=session_id)

    import json

    def _sync():
        client = get_client()

        # Write to normalized session_files table (O(1) insert)
        row = {
            "session_id": session_id,
            "filename": file_metadata.get("filename"),
            "storage_path": file_metadata.get("storage_path"),
            "type": file_metadata.get("type", "unknown"),
            "content_type": file_metadata.get("content_type"),
            "size_bytes": file_metadata.get("size_bytes", 0),
            "public_url": file_metadata.get("public_url"),
            "latitude": file_metadata.get("latitude"),
            "longitude": file_metadata.get("longitude"),
            "address": file_metadata.get("address"),
            "label": file_metadata.get("label"),
        }
        ts = file_metadata.get("timestamp")
        if ts:
            row["timestamp"] = ts
        try:
            client.table("session_files").insert(row).execute()
        except Exception as e:
            logger.warning("session_files_insert_failed", error=str(e))

        # Also append to raw_files JSONB for backward compatibility
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
    """Update fields on a file — writes to session_files table + raw_files (compat)."""
    import json

    def _sync():
        client = get_client()

        # Update normalized table (O(1) — single row update by filename)
        try:
            client.table("session_files").update(updates).eq(
                "session_id", session_id
            ).eq("filename", filename).execute()
        except Exception as e:
            logger.warning("session_files_update_failed", error=str(e))

        # Also update raw_files JSONB for backward compatibility
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


async def get_session_files(session_id: str) -> list[dict[str, Any]]:
    """Get files for a session — reads from session_files table, falls back to raw_files JSONB."""
    def _sync():
        client = get_client()
        # Try normalized table first
        result = (
            client.table("session_files")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
        )
        if result and result.data:
            return result.data
        # Fallback to JSONB
        session = client.table("sessions").select("raw_files").eq("id", session_id).maybe_single().execute()
        if session is None or not getattr(session, "data", None):
            return []
        return (session.data or {}).get("raw_files") or []

    try:
        return await _run(_sync)
    except Exception as e:
        logger.warning("get_session_files_failed_using_jsonb", session_id=session_id, error=str(e))
        # Last resort fallback
        def _fallback():
            client = get_client()
            session = client.table("sessions").select("raw_files").eq("id", session_id).maybe_single().execute()
            if session is None or not getattr(session, "data", None):
                return []
            return (session.data or {}).get("raw_files") or []
        return await _run(_fallback)


async def get_session(session_id: str) -> dict[str, Any] | None:
    """Get a session by ID."""
    logger.info("get_session", session_id=session_id)
    def _sync():
        client = get_client()
        result = client.table("sessions").select("*").eq("id", session_id).maybe_single().execute()
        if result is None:
            return None
        return getattr(result, "data", None)
    return await _run(_sync)


async def upsert_user(
    phone: str,
    implementation: str,
    name: str | None = None,
    role: str = "field_agent",
) -> dict[str, Any]:
    """Create or update a user row. Used when a visitor chooses a demo via keyword
    so their implementation choice persists across messages.

    Returns the resulting user dict.
    """
    def _sync():
        client = get_client()
        # Check if user exists
        existing = client.table("users").select("*").eq("phone", phone).maybe_single().execute()
        if existing and getattr(existing, "data", None):
            # Update only the implementation (and name if provided)
            updates: dict[str, Any] = {"implementation": implementation}
            if name:
                updates["name"] = name
            result = client.table("users").update(updates).eq("phone", phone).execute()
            return (result.data or [existing.data])[0] if result.data else existing.data
        # Insert new user
        new_user = {
            "phone": phone,
            "name": name or phone,
            "implementation": implementation,
            "role": role,
        }
        result = client.table("users").insert(new_user).execute()
        return result.data[0] if result.data else new_user
    return await _run(_sync)


async def clear_session_files_today(phone: str) -> int:
    """Delete all session_files and empty raw_files for today's session.

    Used when a user switches demos mid-session — each demo should start fresh
    instead of mixing files from different analysis contexts.

    Returns the number of rows deleted from session_files.
    """
    def _sync() -> int:
        client = get_client()
        today = datetime.date.today().isoformat()
        # Find today's session
        session_result = (
            client.table("sessions")
            .select("id")
            .eq("user_phone", phone)
            .eq("date", today)
            .maybe_single()
            .execute()
        )
        if session_result is None or not getattr(session_result, "data", None):
            return 0
        session_id = session_result.data["id"]

        # Delete from normalized session_files table
        deleted = client.table("session_files").delete().eq("session_id", session_id).execute()
        deleted_count = len(deleted.data) if deleted.data else 0

        # Empty the raw_files JSONB column for backward compat
        client.table("sessions").update({
            "raw_files": [],
            "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }).eq("id", session_id).execute()

        return deleted_count

    try:
        count = await _run(_sync)
        logger.info("session_files_cleared", phone=phone, deleted=count)
        return count
    except Exception as e:
        logger.warning("session_files_clear_failed", phone=phone, error=str(e))
        return 0


async def update_session_implementation_today(phone: str, impl_id: str) -> None:
    """Update today's session implementation for a phone (if a session exists).

    Idempotent. Used when a user switches demos via keyword — any files already
    received today get re-categorized under the new implementation.
    """
    def _sync():
        client = get_client()
        today = datetime.date.today().isoformat()
        client.table("sessions").update({
            "implementation": impl_id,
            "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }).eq("user_phone", phone).eq("date", today).execute()
    try:
        await _run(_sync)
        logger.info("session_impl_updated_today", phone=phone, impl=impl_id)
    except Exception as e:
        logger.warning("session_impl_update_failed", phone=phone, error=str(e))


async def get_implementation_by_whatsapp_number(whatsapp_number: str) -> str | None:
    """Resolve implementation ID from the Twilio WhatsApp number (To field).

    Returns implementation_id or None if no match found.
    """
    def _sync():
        client = get_client()
        try:
            result = (
                client.table("implementations")
                .select("id")
                .eq("whatsapp_number", whatsapp_number)
                .eq("status", "active")
                .maybe_single()
                .execute()
            )
        except Exception as e:
            logger.warning("impl_by_number_query_failed", error=str(e))
            return None
        # supabase-py returns None (not an object) when no rows match maybe_single()
        if result is None or not getattr(result, "data", None):
            return None
        return result.data.get("id")
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


async def set_pending_poc_selection(phone: str) -> None:
    """Mark a user as waiting to provide a POC company name (for demo POC gating)."""
    def _sync():
        client = get_client()
        client.table("users").update({
            "pending_poc_selection_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }).eq("phone", phone).execute()
    try:
        await _run(_sync)
    except Exception as e:
        logger.warning("set_pending_poc_failed", phone=phone, error=str(e))


async def clear_pending_poc_selection(phone: str) -> None:
    """Clear the pending POC selection flag. Idempotent."""
    def _sync():
        client = get_client()
        client.table("users").update({
            "pending_poc_selection_at": None,
        }).eq("phone", phone).execute()
    try:
        await _run(_sync)
    except Exception as e:
        logger.warning("clear_pending_poc_failed", phone=phone, error=str(e))


async def set_pending_location_request(phone: str) -> None:
    """Mark a user as having been prompted for location in the current demo session."""
    def _sync():
        client = get_client()
        client.table("users").update({
            "pending_location_request_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }).eq("phone", phone).execute()
    try:
        await _run(_sync)
    except Exception as e:
        logger.warning("set_pending_location_failed", phone=phone, error=str(e))


async def clear_pending_location_request(phone: str) -> None:
    """Clear the pending location request flag. Idempotent."""
    def _sync():
        client = get_client()
        client.table("users").update({
            "pending_location_request_at": None,
        }).eq("phone", phone).execute()
    try:
        await _run(_sync)
    except Exception as e:
        logger.warning("clear_pending_location_failed", phone=phone, error=str(e))


async def add_text_location_to_session(session_id: str, address_text: str) -> None:
    """Insert a textual location row into session_files (type=location, no lat/lng).

    Used when the user answers the location prompt with a description like
    "Mercadona Madrid centro" instead of sharing their GPS coordinates.
    """
    loc_meta = {
        "filename": None,
        "storage_path": None,
        "type": "location",
        "content_type": "text/plain",
        "address": address_text[:500],
        "label": None,
        "latitude": None,
        "longitude": None,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    def _sync():
        client = get_client()
        row = {
            "session_id": session_id,
            "filename": None,
            "storage_path": None,
            "type": "location",
            "content_type": "text/plain",
            "size_bytes": 0,
            "public_url": None,
            "latitude": None,
            "longitude": None,
            "address": loc_meta["address"],
            "label": None,
        }
        try:
            client.table("session_files").insert(row).execute()
        except Exception as e:
            logger.warning("text_location_insert_failed", error=str(e))
    await _run(_sync)
    logger.info("text_location_added", session_id=session_id, chars=len(address_text))


async def set_pending_contact_request(phone: str) -> None:
    """Mark a user as waiting to provide contact info (for demo CTA flow)."""
    def _sync():
        client = get_client()
        client.table("users").update({
            "pending_contact_request_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }).eq("phone", phone).execute()
    try:
        await _run(_sync)
    except Exception as e:
        logger.warning("set_pending_contact_failed", phone=phone, error=str(e))


async def clear_pending_contact_request(phone: str) -> None:
    """Clear the pending contact flag after lead has been captured."""
    def _sync():
        client = get_client()
        client.table("users").update({
            "pending_contact_request_at": None,
        }).eq("phone", phone).execute()
    try:
        await _run(_sync)
    except Exception as e:
        logger.warning("clear_pending_contact_failed", phone=phone, error=str(e))


async def save_demo_lead(
    phone: str,
    implementation: str | None,
    country: str | None,
    payload: str,
) -> str | None:
    """Insert a demo lead row. Returns the inserted row id or None on failure."""
    def _sync():
        client = get_client()
        row = {
            "phone": phone,
            "implementation": implementation,
            "country": country,
            "payload": payload[:2000],  # Cap to keep DB sane
            "source": "whatsapp_demo",
            "status": "new",
        }
        result = client.table("demo_leads").insert(row).execute()
        return result.data[0]["id"] if result.data else None
    try:
        lead_id = await _run(_sync)
        logger.info("demo_lead_saved", phone=phone, impl=implementation, lead_id=lead_id)
        return lead_id
    except Exception as e:
        logger.error("demo_lead_save_failed", phone=phone, error=str(e))
        return None


async def list_users(limit: int = 10) -> list[dict[str, Any]]:
    """List users (for health check / test)."""
    def _sync():
        client = get_client()
        result = client.table("users").select("*").limit(limit).execute()
        return result.data or []
    return await _run(_sync)
