"""Admin API — CRUD for implementations, visit types, users, and testing."""

from __future__ import annotations

import datetime
from typing import Any

import ipaddress
from urllib.parse import urlparse

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.config.settings import settings
from src.engine.supabase_client import get_client, get_user_by_phone
from src.routes.auth import BackofficeUser, get_current_user, require_permission, require_superadmin
from src.routes.rate_limit import limiter

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _validate_date(value: str | None, field: str = "date") -> str | None:
    """Validate date string is YYYY-MM-DD format. Returns validated string or raises 400."""
    if not value:
        return None
    try:
        datetime.date.fromisoformat(value)
        return value
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid {field} format. Use YYYY-MM-DD.")


async def get_user_by_phone_or_none(phone: str) -> dict | None:
    """Safe wrapper for get_user_by_phone."""
    try:
        return await get_user_by_phone(phone)
    except Exception:
        return None


# ── Pydantic models ──────────────────────────────────────────────


class ImplementationCreate(BaseModel):
    id: str
    name: str
    industry: str | None = None
    country: str = "CO"
    language: str = "es"
    primary_color: str = "#003366"
    vision_system_prompt: str = ""
    segmentation_prompt_template: str = ""
    google_spreadsheet_id: str | None = None
    trigger_words: list[str] = ["reporte", "generar", "listo", "fin"]


class ImplementationUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    country: str | None = None
    language: str | None = None
    primary_color: str | None = None
    vision_system_prompt: str | None = None
    segmentation_prompt_template: str | None = None
    google_spreadsheet_id: str | None = None
    trigger_words: list[str] | None = None
    status: str | None = None


class VisitTypeCreate(BaseModel):
    slug: str
    display_name: str
    schema_json: dict[str, Any]
    sheets_tab: str | None = None
    confidence_threshold: float = 0.7
    sort_order: int = 0


class VisitTypeUpdate(BaseModel):
    slug: str | None = None
    display_name: str | None = None
    schema_json: dict[str, Any] | None = None
    sheets_tab: str | None = None
    confidence_threshold: float | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class UserAssign(BaseModel):
    phone: str
    name: str
    role: str = "executive"


class TestVisionRequest(BaseModel):
    image_url: str
    vision_prompt: str


class TestExtractionRequest(BaseModel):
    text: str
    schema_json: dict[str, Any]


# ── Implementations CRUD ─────────────────────────────────────────


@router.get("/implementations")
async def list_implementations(user: BackofficeUser = Depends(get_current_user)) -> dict:
    client = get_client()
    query = client.table("implementations").select("*").order("name")
    if not user.is_superadmin:
        query = query.in_("id", user.allowed_implementations)
    result = query.execute()
    return {"success": True, "data": result.data or [], "error": None}


@router.post("/implementations")
async def create_implementation(body: ImplementationCreate, user: BackofficeUser = Depends(require_permission("can_edit_frameworks"))) -> dict:
    client = get_client()
    row = body.model_dump()
    row["created_at"] = datetime.datetime.now(datetime.UTC).isoformat()
    row["updated_at"] = row["created_at"]

    try:
        result = client.table("implementations").insert(row).execute()
        logger.info("implementation_created", id=body.id)
        return {"success": True, "data": result.data[0], "error": None}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/implementations/{impl_id}")
async def get_implementation(impl_id: str, user: BackofficeUser = Depends(get_current_user)) -> dict:
    if not user.has_impl_access(impl_id):
        raise HTTPException(status_code=403, detail="Access denied")
    client = get_client()
    result = (
        client.table("implementations")
        .select("*")
        .eq("id", impl_id)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        raise HTTPException(status_code=404, detail=f"Implementation '{impl_id}' not found")
    return {"success": True, "data": result.data, "error": None}


@router.put("/implementations/{impl_id}")
async def update_implementation(impl_id: str, body: ImplementationUpdate, user: BackofficeUser = Depends(require_permission("can_edit_frameworks"))) -> dict:
    if not user.has_impl_access(impl_id):
        raise HTTPException(status_code=403, detail="Access denied")
    client = get_client()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = datetime.datetime.now(datetime.UTC).isoformat()

    try:
        result = (
            client.table("implementations")
            .update(updates)
            .eq("id", impl_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail=f"Implementation '{impl_id}' not found")
        logger.info("implementation_updated", id=impl_id, fields=list(updates.keys()))
        return {"success": True, "data": result.data[0], "error": None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/implementations/{impl_id}")
async def delete_implementation(impl_id: str, user: BackofficeUser = Depends(require_superadmin())) -> dict:
    client = get_client()
    # Soft delete — set status to 'inactive'
    result = (
        client.table("implementations")
        .update({"status": "inactive", "updated_at": datetime.datetime.now(datetime.UTC).isoformat()})
        .eq("id", impl_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Implementation '{impl_id}' not found")
    logger.info("implementation_deactivated", id=impl_id)
    return {"success": True, "data": {"id": impl_id, "status": "inactive"}, "error": None}


# ── Visit Types CRUD ─────────────────────────────────────────────


@router.get("/implementations/{impl_id}/visit-types")
async def list_visit_types(impl_id: str, user: BackofficeUser = Depends(get_current_user)) -> dict:
    if not user.has_impl_access(impl_id):
        raise HTTPException(status_code=403, detail="Access denied")
    client = get_client()
    result = (
        client.table("visit_types")
        .select("*")
        .eq("implementation_id", impl_id)
        .order("sort_order")
        .execute()
    )
    return {"success": True, "data": result.data or [], "error": None}


@router.post("/implementations/{impl_id}/visit-types")
async def create_visit_type(impl_id: str, body: VisitTypeCreate, user: BackofficeUser = Depends(require_permission("can_edit_frameworks"))) -> dict:
    if not user.has_impl_access(impl_id):
        raise HTTPException(status_code=403, detail="Access denied")
    client = get_client()
    row = body.model_dump()
    row["implementation_id"] = impl_id

    try:
        result = client.table("visit_types").insert(row).execute()
        logger.info("visit_type_created", implementation=impl_id, slug=body.slug)
        return {"success": True, "data": result.data[0], "error": None}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/visit-types/{vt_id}")
async def update_visit_type(vt_id: str, body: VisitTypeUpdate, user: BackofficeUser = Depends(require_permission("can_edit_frameworks"))) -> dict:
    client = get_client()
    # Load visit type to check impl access
    existing = client.table("visit_types").select("implementation_id").eq("id", vt_id).maybe_single().execute()
    if not existing or not existing.data:
        raise HTTPException(status_code=404, detail=f"Visit type '{vt_id}' not found")
    if not user.has_impl_access(existing.data["implementation_id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        result = (
            client.table("visit_types")
            .update(updates)
            .eq("id", vt_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail=f"Visit type '{vt_id}' not found")
        logger.info("visit_type_updated", id=vt_id, fields=list(updates.keys()))
        return {"success": True, "data": result.data[0], "error": None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/visit-types/{vt_id}")
async def delete_visit_type(vt_id: str, user: BackofficeUser = Depends(require_permission("can_edit_frameworks"))) -> dict:
    client = get_client()
    # Load visit type to check impl access
    existing = client.table("visit_types").select("implementation_id").eq("id", vt_id).maybe_single().execute()
    if not existing or not existing.data:
        raise HTTPException(status_code=404, detail=f"Visit type '{vt_id}' not found")
    if not user.has_impl_access(existing.data["implementation_id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    result = (
        client.table("visit_types")
        .update({"is_active": False})
        .eq("id", vt_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Visit type '{vt_id}' not found")
    logger.info("visit_type_deactivated", id=vt_id)
    return {"success": True, "data": {"id": vt_id, "is_active": False}, "error": None}


# ── Users per Implementation ─────────────────────────────────────


@router.get("/implementations/{impl_id}/users")
async def list_users(impl_id: str, user: BackofficeUser = Depends(get_current_user)) -> dict:
    if not user.has_impl_access(impl_id):
        raise HTTPException(status_code=403, detail="Access denied")
    client = get_client()
    result = (
        client.table("users")
        .select("*")
        .eq("implementation", impl_id)
        .order("name")
        .execute()
    )
    return {"success": True, "data": result.data or [], "error": None}


@router.post("/implementations/{impl_id}/users")
async def assign_user(impl_id: str, body: UserAssign, user: BackofficeUser = Depends(require_permission("can_manage_users"))) -> dict:
    if not user.has_impl_access(impl_id):
        raise HTTPException(status_code=403, detail="Access denied")
    client = get_client()
    row = {
        "phone": body.phone,
        "name": body.name,
        "role": body.role,
        "implementation": impl_id,
        "implementation_id": impl_id,
    }

    try:
        result = client.table("users").upsert(row, on_conflict="phone").execute()
        logger.info("user_assigned", phone=body.phone, implementation=impl_id)
        return {"success": True, "data": result.data[0], "error": None}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class SwitchUserImplRequest(BaseModel):
    phone: str
    new_implementation: str


@router.post("/users/switch-implementation")
async def switch_user_implementation(body: SwitchUserImplRequest, user: BackofficeUser = Depends(require_permission("can_manage_users"))) -> dict:
    """Change the active implementation for a user (from backoffice)."""
    if not user.has_impl_access(body.new_implementation):
        raise HTTPException(status_code=403, detail="Access denied")
    client = get_client()

    # Verify implementation exists
    impl = client.table("implementations").select("id, name").eq("id", body.new_implementation).maybe_single().execute()
    if not impl or not impl.data:
        raise HTTPException(status_code=404, detail=f"Implementation '{body.new_implementation}' not found")

    # Update user
    result = client.table("users").update({
        "implementation": body.new_implementation,
        "implementation_id": body.new_implementation,
    }).eq("phone", body.phone).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail=f"User '{body.phone}' not found")

    logger.info("user_implementation_switched", phone=body.phone, new_impl=body.new_implementation)
    return {
        "success": True,
        "data": {
            "phone": body.phone,
            "implementation": body.new_implementation,
            "implementation_name": impl.data["name"],
        },
        "error": None,
    }


@router.delete("/implementations/{impl_id}/users/{phone}")
async def remove_user(impl_id: str, phone: str, user: BackofficeUser = Depends(require_permission("can_manage_users"))) -> dict:
    if not user.has_impl_access(impl_id):
        raise HTTPException(status_code=403, detail="Access denied")
    client = get_client()
    result = (
        client.table("users")
        .delete()
        .eq("phone", phone)
        .eq("implementation", impl_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=f"User '{phone}' not found in '{impl_id}'")
    logger.info("user_removed", phone=phone, implementation=impl_id)
    return {"success": True, "data": {"phone": phone, "removed": True}, "error": None}


# ── Stats ─────────────────────────────────────────────────────────


@router.get("/stats")
async def get_stats(impl: str | None = None, days: int = 7, user: BackofficeUser = Depends(get_current_user)) -> dict:
    client = get_client()
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

    # Sessions count
    query = client.table("sessions").select("id, status, date, implementation").gte("date", cutoff)
    if impl:
        query = query.eq("implementation", impl)
    elif not user.is_superadmin:
        query = query.in_("implementation", user.allowed_implementations)
    sessions_result = query.execute()
    sessions = sessions_result.data or []

    # Visit reports count
    vr_query = client.table("visit_reports").select("id, implementation, confidence_score, status").gte("created_at", cutoff + "T00:00:00")
    if impl:
        vr_query = vr_query.eq("implementation", impl)
    elif not user.is_superadmin:
        vr_query = vr_query.in_("implementation", user.allowed_implementations)
    reports_result = vr_query.execute()
    reports = reports_result.data or []

    return {
        "success": True,
        "data": {
            "period_days": days,
            "implementation_filter": impl,
            "sessions": {
                "total": len(sessions),
                "by_status": _count_by(sessions, "status"),
                "by_implementation": _count_by(sessions, "implementation"),
            },
            "reports": {
                "total": len(reports),
                "by_status": _count_by(reports, "status"),
                "avg_confidence": (
                    sum(r.get("confidence_score", 0) for r in reports) / len(reports)
                    if reports else 0
                ),
            },
        },
        "error": None,
    }


def _count_by(items: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        val = item.get(key, "unknown")
        counts[val] = counts.get(val, 0) + 1
    return counts


# ── Config Reload ─────────────────────────────────────────────────


# ── Sessions (read-only for backoffice) ──────────────────────────


@router.get("/sessions")
async def list_sessions(
    impl: str | None = None,
    phone: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: BackofficeUser = Depends(get_current_user),
) -> dict:
    """List sessions with optional filters."""
    client = get_client()
    query = client.table("sessions").select("*").order("date", desc=True).order("created_at", desc=True)

    if impl:
        query = query.eq("implementation", impl)
    elif not user.is_superadmin:
        query = query.in_("implementation", user.allowed_implementations)
    if phone:
        query = query.eq("user_phone", phone)
    if status:
        query = query.eq("status", status)
    if date_from:
        query = query.gte("date", date_from)
    if date_to:
        query = query.lte("date", date_to)

    # Get total count for pagination
    count_query = client.table("sessions").select("id", count="exact")
    if impl:
        count_query = count_query.eq("implementation", impl)
    elif not user.is_superadmin:
        count_query = count_query.in_("implementation", user.allowed_implementations)
    if phone:
        count_query = count_query.eq("user_phone", phone)
    if status:
        count_query = count_query.eq("status", status)
    if date_from:
        count_query = count_query.gte("date", date_from)
    if date_to:
        count_query = count_query.lte("date", date_to)
    count_result = count_query.execute()
    total = count_result.count or 0

    query = query.range(offset, offset + limit - 1)
    result = query.execute()
    data = result.data or []

    return {
        "success": True,
        "data": data,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        },
        "error": None,
    }


@router.get("/sessions/{session_id}")
async def get_session_detail(session_id: str, user: BackofficeUser = Depends(get_current_user)) -> dict:
    """Get full session detail including media URLs and visit reports."""
    client = get_client()

    # Fetch session
    session = (
        client.table("sessions")
        .select("*")
        .eq("id", session_id)
        .maybe_single()
        .execute()
    )
    if not session or not session.data:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    session_data = session.data

    # Generate signed URLs for media files (bucket is private)
    raw_files = session_data.get("raw_files") or []
    paths_to_sign = [f["storage_path"] for f in raw_files if f.get("storage_path")]
    if paths_to_sign:
        try:
            signed = client.storage.from_("media").create_signed_urls(
                paths_to_sign, expires_in=3600  # 1 hour
            )
            url_map = {item["path"]: item["signedURL"] for item in signed}
            for f in raw_files:
                sp = f.get("storage_path")
                if sp and sp in url_map:
                    f["public_url"] = url_map[sp]
        except Exception as e:
            logger.warning("signed_url_generation_failed", error=str(e))
            # Fallback: try public URL pattern (works if bucket is public)
            for f in raw_files:
                sp = f.get("storage_path")
                if sp:
                    f["public_url"] = f"{settings.supabase_url}/storage/v1/object/public/media/{sp}"

    # Fetch visit reports for this session
    reports = (
        client.table("visit_reports")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    session_data["visit_reports"] = reports.data or []

    return {"success": True, "data": session_data, "error": None}


@router.post("/reload-config")
async def reload_config(impl_id: str | None = None, user: BackofficeUser = Depends(get_current_user)) -> dict:
    from src.engine.config_loader import reload
    await reload(impl_id)
    return {
        "success": True,
        "data": {"reloaded": impl_id or "all"},
        "error": None,
    }


# ── Test Endpoints (Prompt Engineering) ───────────────────────────


@router.post("/test-vision-prompt")
@limiter.limit("10/minute")
async def test_vision_prompt(request: Request, body: TestVisionRequest, user: BackofficeUser = Depends(require_permission("can_edit_prompts"))) -> dict:
    """Test a vision prompt against an image URL. Returns the AI description."""
    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=60.0)

        # SSRF protection: only allow HTTPS from public hosts
        parsed_url = urlparse(body.image_url)
        if parsed_url.scheme != "https":
            raise HTTPException(status_code=400, detail="Only HTTPS URLs allowed")
        blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "metadata.google.internal", "169.254.169.254"}
        if parsed_url.hostname in blocked_hosts:
            raise HTTPException(status_code=400, detail="Internal URLs not allowed")
        try:
            ip = ipaddress.ip_address(parsed_url.hostname or "")
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise HTTPException(status_code=400, detail="Private/internal URLs not allowed")
        except ValueError:
            # hostname is a domain — resolve and check IP
            import socket
            try:
                resolved = socket.getaddrinfo(parsed_url.hostname, 443)
                for _, _, _, _, sockaddr in resolved:
                    resolved_ip = ipaddress.ip_address(sockaddr[0])
                    if resolved_ip.is_private or resolved_ip.is_loopback or resolved_ip.is_link_local or resolved_ip.is_reserved:
                        raise HTTPException(status_code=400, detail="URL resolves to internal address")
            except socket.gaierror:
                raise HTTPException(status_code=400, detail="Cannot resolve hostname")

        # Fetch image bytes — no redirects to prevent SSRF via redirect
        import httpx
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.get(body.image_url, follow_redirects=False)
            resp.raise_for_status()
            image_bytes = resp.content
            media_type = resp.headers.get("content-type", "image/jpeg")

        import base64
        b64 = base64.b64encode(image_bytes).decode()

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=body.vision_prompt,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                    {"type": "text", "text": "Analiza esta imagen."},
                ],
            }],
        )

        return {
            "success": True,
            "data": {"description": response.content[0].text},
            "error": None,
        }

    except Exception as e:
        logger.error("test_vision_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


class BulkImportRequest(BaseModel):
    implementation_id: str
    users: list[dict[str, Any]]  # [{phone, name, role?, country?, group_slug?}]


@router.post("/bulk-import-users")
async def bulk_import_users(body: BulkImportRequest, user: BackofficeUser = Depends(require_permission("can_bulk_import"))) -> dict:
    """Bulk import users from a list (CSV-parsed on frontend).

    Each user dict: { phone, name, role?, country?, group_slug? }
    Upserts by phone — updates existing, creates new.
    """
    client = get_client()
    created = 0
    updated = 0
    errors: list[str] = []

    # Pre-load groups for this implementation
    groups_result = (
        client.table("user_groups")
        .select("id, slug")
        .eq("implementation_id", body.implementation_id)
        .execute()
    )
    group_map = {g["slug"]: g["id"] for g in (groups_result.data or [])}

    for i, u in enumerate(body.users):
        phone = u.get("phone", "").strip()
        name = u.get("name", "").strip()
        if not phone or not name:
            errors.append(f"Row {i+1}: missing phone or name")
            continue

        # Normalize phone (ensure +)
        if not phone.startswith("+"):
            phone = f"+{phone}"

        group_id = None
        group_slug = u.get("group_slug", "").strip()
        if group_slug and group_slug in group_map:
            group_id = group_map[group_slug]

        row = {
            "phone": phone,
            "name": name,
            "implementation": body.implementation_id,
            "implementation_id": body.implementation_id,
            "role": u.get("role", "field_agent").strip(),
            "country": u.get("country", "").strip(),
        }
        if group_id:
            row["group_id"] = group_id

        try:
            # Check if exists
            existing = client.table("users").select("id").eq("phone", phone).maybe_single().execute()
            if existing and existing.data:
                client.table("users").update(row).eq("phone", phone).execute()
                updated += 1
            else:
                client.table("users").insert(row).execute()
                created += 1
        except Exception as e:
            errors.append(f"Row {i+1} ({phone}): {str(e)[:100]}")

    return {
        "success": len(errors) == 0,
        "data": {
            "created": created,
            "updated": updated,
            "errors": errors,
            "total_processed": created + updated,
        },
        "error": f"{len(errors)} errors" if errors else None,
    }


@router.post("/trigger-pipeline/{session_id}")
@limiter.limit("5/minute")
async def trigger_pipeline(request: Request, session_id: str, user: BackofficeUser = Depends(get_current_user)) -> dict:
    """Manually trigger the pipeline for a session. Resets status to accumulating first."""
    try:
        client = get_client()

        # Reset session status to allow re-processing
        client.table("sessions").update({
            "status": "accumulating",
            "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }).eq("id", session_id).execute()

        from src.engine.pipeline import process_session
        from src.engine.supabase_client import update_session_status
        await update_session_status(session_id, "segmenting")

        result = await process_session(session_id)

        return {
            "success": result.status != "failed",
            "data": {
                "status": result.status,
                "visits": len(result.extractions),
                "reports": result.report_ids,
                "sheets_tabs": result.sheets_tabs,
                "elapsed_ms": result.elapsed_ms,
                "error": result.error,
            },
            "error": result.error,
        }

    except Exception as e:
        logger.error("trigger_pipeline_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-extraction")
@limiter.limit("10/minute")
async def test_extraction(request: Request, body: TestExtractionRequest, user: BackofficeUser = Depends(require_permission("can_edit_prompts"))) -> dict:
    """Test an extraction schema against sample text. Returns structured JSON."""
    try:
        from src.engine.schema_builder import build_system_prompt

        system_prompt = build_system_prompt(body.schema_json)

        import anthropic
        from src.config.settings import settings

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": body.text}],
        )

        import json
        raw = response.content[0].text
        # Try to parse as JSON
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None

        return {
            "success": True,
            "data": {"raw": raw, "parsed": parsed},
            "error": None,
        }

    except Exception as e:
        logger.error("test_extraction_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


class GenerateReportRequest(BaseModel):
    session_id: str
    report_type: str  # 'tactical' | 'strategic' | 'innovation' | 'all'


@router.post("/generate-report")
@limiter.limit("20/minute")
async def generate_report_endpoint(request: Request, body: GenerateReportRequest, user: BackofficeUser = Depends(require_permission("can_generate_reports"))) -> dict:
    """Generate one or all report types for a session.

    Uses pre-processed transcriptions and image descriptions from raw_files.
    No pipeline execution needed — works directly on accumulated media data.
    """
    try:
        client = get_client()

        # Load session with all data
        session_result = (
            client.table("sessions")
            .select("*")
            .eq("id", body.session_id)
            .maybe_single()
            .execute()
        )
        if not session_result or not session_result.data:
            raise HTTPException(status_code=404, detail=f"Session '{body.session_id}' not found")

        session = session_result.data

        # Load implementation config
        impl_id = session.get("implementation", settings.default_implementation)
        from src.engine.config_loader import get_implementation
        impl_config = await get_implementation(impl_id)

        if not impl_config.analysis_framework:
            raise HTTPException(
                status_code=400,
                detail=f"Implementation '{impl_id}' has no analysis_framework configured",
            )

        af = impl_config.analysis_framework
        frameworks = af.get("frameworks", {})

        # Legacy support: if no "frameworks" key, treat the whole thing as a single framework
        if not frameworks and af.get("dimensions"):
            frameworks = {"strategic": af}

        if not frameworks:
            raise HTTPException(status_code=400, detail="No frameworks configured in analysis_framework")

        from src.engine.analyzer import generate_report, generate_all_reports, extract_facts, _build_observations_context

        # Resolve country context from session or user
        user_country = session.get("country", "")
        if not user_country:
            user = await get_user_by_phone_or_none(session.get("user_phone", ""))
            user_country = user.get("country", impl_config.country) if user else impl_config.country
        cc = impl_config.get_country_context(user_country)

        if body.report_type == "all":
            results = await generate_all_reports(session, frameworks, impl_config.name, country_context=cc)
            # Save each to DB + extract facts for aggregation
            saved = {}
            obs_text = _build_observations_context(session)
            for rtype, markdown in results.items():
                if markdown:
                    saved[rtype] = await _save_report(client, body.session_id, impl_id, rtype, markdown)
                    # Extract structured facts in background
                    fact_result = await extract_facts(markdown, obs_text, rtype, session)
                    if fact_result:
                        try:
                            client.table("session_facts").upsert({
                                "session_id": body.session_id,
                                "implementation_id": impl_id,
                                "framework": rtype,
                                "facts": fact_result["facts"],
                                "key_quotes": fact_result["key_quotes"],
                                "fact_count": fact_result["fact_count"],
                            }).execute()
                        except Exception as e:
                            logger.warning("save_facts_failed", error=str(e))

            return {
                "success": True,
                "data": {
                    "session_id": body.session_id,
                    "reports": {
                        rtype: {
                            "report_id": saved.get(rtype),
                            "chars": len(md) if md else 0,
                            "markdown": md,
                        }
                        for rtype, md in results.items()
                    },
                },
                "error": None,
            }
        else:
            if body.report_type not in frameworks:
                available = list(frameworks.keys())
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown report type '{body.report_type}'. Available: {available}",
                )

            markdown = await generate_report(
                session=session,
                report_type=body.report_type,
                framework_config=frameworks[body.report_type],
                implementation_name=impl_config.name,
                country_context=cc,
            )

            report_id = None
            if markdown:
                report_id = await _save_report(client, body.session_id, impl_id, body.report_type, markdown)
                # Extract facts for aggregation
                obs_text = _build_observations_context(session)
                fact_result = await extract_facts(markdown, obs_text, body.report_type, session)
                if fact_result:
                    try:
                        client.table("session_facts").upsert({
                            "session_id": body.session_id,
                            "implementation_id": impl_id,
                            "framework": body.report_type,
                            "facts": fact_result["facts"],
                            "key_quotes": fact_result["key_quotes"],
                            "fact_count": fact_result["fact_count"],
                        }).execute()
                    except Exception as e:
                        logger.warning("save_facts_failed", error=str(e))

            return {
                "success": markdown is not None,
                "data": {
                    "session_id": body.session_id,
                    "report_type": body.report_type,
                    "report_id": report_id,
                    "chars": len(markdown) if markdown else 0,
                    "markdown": markdown,
                },
                "error": None if markdown else "Report generation failed",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("generate_report_failed", session_id=body.session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


async def _save_report(
    client: Any, session_id: str, impl_id: str, report_type: str, markdown: str
) -> str | None:
    """Save a generated report to the consolidated_reports table."""
    try:
        result = client.table("consolidated_reports").insert({
            "implementation_id": impl_id,
            "title": f"{report_type} — {session_id[:8]}",
            "framework": report_type,
            "visit_report_ids": [],
            "filters": {"session_id": session_id},
            "analysis_markdown": markdown,
            "status": "completed",
        }).execute()
        return result.data[0]["id"] if result.data else None
    except Exception as e:
        logger.warning("save_report_failed", error=str(e))
        return None


class ConsolidateRequest(BaseModel):
    implementation_id: str
    title: str = "Reporte Consolidado"
    report_ids: list[str] | None = None  # None = all reports with analysis
    date_from: str | None = None
    date_to: str | None = None


@router.post("/consolidate-analysis")
@limiter.limit("5/minute")
async def consolidate_analysis(request: Request, body: ConsolidateRequest, user: BackofficeUser = Depends(require_permission("can_generate_reports"))) -> dict:
    """Consolidate multiple per-visit analyses into a unified strategic report.

    If report_ids is provided, consolidates those specific reports.
    Otherwise, consolidates all reports with strategic_analysis for the implementation,
    optionally filtered by date range.
    """
    try:
        client = get_client()

        # Load implementation config to get framework
        from src.engine.config_loader import get_implementation
        impl_config = await get_implementation(body.implementation_id)
        if not impl_config.analysis_framework:
            raise HTTPException(
                status_code=400,
                detail=f"Implementation '{body.implementation_id}' has no analysis_framework configured",
            )

        # Query visit reports with strategic analysis
        query = (
            client.table("visit_reports")
            .select("id, visit_type, inferred_location, strategic_analysis, created_at, session_id")
            .eq("implementation", body.implementation_id)
            .not_.is_("strategic_analysis", "null")
        )

        if body.report_ids:
            query = query.in_("id", body.report_ids)
        if body.date_from:
            query = query.gte("created_at", body.date_from)
        if body.date_to:
            query = query.lte("created_at", body.date_to)

        result = query.order("created_at").execute()
        reports = result.data or []

        if not reports:
            return {
                "success": False,
                "data": None,
                "error": "No reports with strategic analysis found for the given criteria",
            }

        # Get executive names from sessions
        session_ids = list({r["session_id"] for r in reports})
        sessions_result = (
            client.table("sessions")
            .select("id, user_name")
            .in_("id", session_ids)
            .execute()
        )
        session_map = {s["id"]: s.get("user_name", "") for s in (sessions_result.data or [])}

        # Build visit_analyses for consolidation
        visit_analyses = []
        for r in reports:
            visit_analyses.append({
                "location": r["inferred_location"],
                "visit_type": r["visit_type"],
                "analysis_markdown": r["strategic_analysis"],
                "date": r["created_at"][:10],
                "executive": session_map.get(r["session_id"], ""),
            })

        # Run consolidation
        from src.engine.analyzer import consolidate_analyses
        consolidated_md = await consolidate_analyses(
            visit_analyses=visit_analyses,
            framework=impl_config.analysis_framework,
            implementation_name=impl_config.name,
        )

        if not consolidated_md:
            raise HTTPException(status_code=500, detail="Consolidation analysis failed")

        # Save consolidated report to DB
        report_ids_list = [r["id"] for r in reports]
        insert_data = {
            "implementation_id": body.implementation_id,
            "title": body.title,
            "framework": impl_config.analysis_framework.get("id", "babson_pentagon"),
            "visit_report_ids": report_ids_list,
            "filters": {
                "date_from": body.date_from,
                "date_to": body.date_to,
            },
            "analysis_markdown": consolidated_md,
            "status": "completed",
        }

        try:
            save_result = client.table("consolidated_reports").insert(insert_data).execute()
            consolidated_id = save_result.data[0]["id"] if save_result.data else None
        except Exception:
            consolidated_id = None
            logger.warning("consolidated_report_save_failed_table_may_not_exist")

        return {
            "success": True,
            "data": {
                "id": consolidated_id,
                "visits_analyzed": len(visit_analyses),
                "report_ids": report_ids_list,
                "markdown": consolidated_md,
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("consolidate_analysis_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ── User Groups ─────────────────────────────────────────────────────


class UserGroupCreate(BaseModel):
    name: str
    slug: str
    zone: str | None = None
    tags: list[str] = []


@router.get("/user-groups")
async def list_user_groups(impl: str | None = None, user: BackofficeUser = Depends(get_current_user)) -> dict:
    client = get_client()
    query = client.table("user_groups").select("*").order("name")
    if impl:
        query = query.eq("implementation_id", impl)
    result = query.execute()
    return {"success": True, "data": result.data or [], "error": None}


@router.post("/implementations/{impl_id}/user-groups")
async def create_user_group(impl_id: str, body: UserGroupCreate, user: BackofficeUser = Depends(require_permission("can_manage_groups"))) -> dict:
    client = get_client()
    result = client.table("user_groups").insert({
        "implementation_id": impl_id,
        "name": body.name,
        "slug": body.slug,
        "zone": body.zone,
        "tags": body.tags,
    }).execute()
    return {"success": True, "data": result.data[0] if result.data else None, "error": None}


@router.put("/user-groups/{group_id}")
async def update_user_group(group_id: str, body: UserGroupCreate, user: BackofficeUser = Depends(require_permission("can_manage_groups"))) -> dict:
    client = get_client()
    result = client.table("user_groups").update({
        "name": body.name,
        "slug": body.slug,
        "zone": body.zone,
        "tags": body.tags,
    }).eq("id", group_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Group '{group_id}' not found")
    return {"success": True, "data": result.data[0], "error": None}


class GroupMemberRequest(BaseModel):
    phone: str


@router.post("/user-groups/{group_id}/members")
async def add_group_member(group_id: str, body: GroupMemberRequest, user: BackofficeUser = Depends(require_permission("can_manage_groups"))) -> dict:
    client = get_client()
    result = client.table("users").update({
        "group_id": group_id,
    }).eq("phone", body.phone).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail=f"User '{body.phone}' not found")
    return {"success": True, "data": result.data[0], "error": None}


@router.delete("/user-groups/{group_id}/members/{phone}")
async def remove_group_member(group_id: str, phone: str, user: BackofficeUser = Depends(require_permission("can_manage_groups"))) -> dict:
    client = get_client()
    client.table("users").update({"group_id": None}).eq("phone", phone).eq("group_id", group_id).execute()
    return {"success": True, "data": {"removed": True}, "error": None}


# ── Multi-Level Report Generation ───────────────────────────────────


class GroupReportRequest(BaseModel):
    group_id: str
    framework: str
    date_from: str | None = None
    date_to: str | None = None


@router.post("/generate-group-report")
@limiter.limit("10/minute")
async def generate_group_report_endpoint(request: Request, body: GroupReportRequest, user: BackofficeUser = Depends(require_permission("can_generate_reports"))) -> dict:
    """Generate a report aggregating all sessions from a user group."""
    try:
        client = get_client()

        # Load group
        group = client.table("user_groups").select("*").eq("id", body.group_id).maybe_single().execute()
        if not group or not group.data:
            raise HTTPException(status_code=404, detail="Group not found")
        group_data = group.data

        # Load implementation
        from src.engine.config_loader import get_implementation
        impl_config = await get_implementation(group_data["implementation_id"])
        frameworks = impl_config.analysis_framework.get("frameworks", {}) if impl_config.analysis_framework else {}
        if body.framework not in frameworks:
            raise HTTPException(status_code=400, detail=f"Framework '{body.framework}' not found")

        # Get sessions for this group's users
        users = client.table("users").select("phone").eq("group_id", body.group_id).execute()
        phones = [u["phone"] for u in (users.data or [])]
        if not phones:
            return {"success": False, "data": None, "error": "No users in this group"}

        # Query session_facts for these users' sessions
        session_query = client.table("sessions").select("id, user_phone, user_name, date").in_("user_phone", phones)
        if body.date_from:
            session_query = session_query.gte("date", body.date_from)
        if body.date_to:
            session_query = session_query.lte("date", body.date_to)
        sessions = session_query.execute()
        session_ids = [s["id"] for s in (sessions.data or [])]
        session_map = {s["id"]: s for s in (sessions.data or [])}

        if not session_ids:
            return {"success": False, "data": None, "error": "No sessions found for this group in date range"}

        # Check for existing facts
        facts_result = (
            client.table("session_facts")
            .select("*")
            .in_("session_id", session_ids)
            .eq("framework", body.framework)
            .execute()
        )
        facts_rows = facts_result.data or []

        # Sessions without facts — generate individual reports + extract facts
        factified_session_ids = {f["session_id"] for f in facts_rows}
        missing_sessions = [sid for sid in session_ids if sid not in factified_session_ids]

        if missing_sessions:
            logger.info("generating_missing_facts", count=len(missing_sessions), framework=body.framework)
            from src.engine.analyzer import generate_report, extract_facts, _build_observations_context

            for sid in missing_sessions[:20]:  # Cap at 20 to avoid timeout
                session_data = client.table("sessions").select("*").eq("id", sid).maybe_single().execute()
                if not session_data or not session_data.data:
                    continue
                sess = session_data.data
                obs = _build_observations_context(sess)
                if not obs.strip():
                    continue

                # Generate individual report
                md = await generate_report(sess, body.framework, frameworks[body.framework], impl_config.name)
                if not md:
                    continue

                # Extract facts
                fact_result = await extract_facts(md, obs, body.framework, sess)
                if fact_result:
                    try:
                        client.table("session_facts").upsert({
                            "session_id": sid,
                            "implementation_id": group_data["implementation_id"],
                            "framework": body.framework,
                            "facts": fact_result["facts"],
                            "key_quotes": fact_result["key_quotes"],
                            "fact_count": fact_result["fact_count"],
                        }).execute()
                        # Add to facts_rows for the group report
                        row = {
                            "facts": fact_result["facts"],
                            "key_quotes": fact_result["key_quotes"],
                            "user_name": session_map.get(sid, {}).get("user_name", ""),
                        }
                        facts_rows.append(row)
                    except Exception as e:
                        logger.warning("save_facts_failed", session_id=sid, error=str(e))

        # Enrich facts_rows with user_name
        for row in facts_rows:
            if "user_name" not in row:
                sid = row.get("session_id", "")
                row["user_name"] = session_map.get(sid, {}).get("user_name", "")

        if not facts_rows:
            return {"success": False, "data": None, "error": "No facts could be extracted from sessions"}

        # Generate group report
        date_range = f"{body.date_from or 'inicio'} a {body.date_to or 'hoy'}"
        from src.engine.analyzer import generate_group_report
        markdown = await generate_group_report(
            facts_rows=facts_rows,
            framework_id=body.framework,
            framework_config=frameworks[body.framework],
            group_name=group_data["name"],
            date_range=date_range,
            implementation_name=impl_config.name,
        )

        # Save to consolidated_reports
        report_id = None
        if markdown:
            report_id = await _save_report(
                client, body.group_id, group_data["implementation_id"],
                f"group_{body.framework}", markdown,
            )

        return {
            "success": markdown is not None,
            "data": {
                "group_id": body.group_id,
                "group_name": group_data["name"],
                "framework": body.framework,
                "sessions_analyzed": len(facts_rows),
                "report_id": report_id,
                "chars": len(markdown) if markdown else 0,
                "markdown": markdown,
            },
            "error": None if markdown else "Group report generation failed",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("generate_group_report_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


class ProjectReportRequest(BaseModel):
    implementation_id: str
    framework: str
    date_from: str | None = None
    date_to: str | None = None


@router.post("/generate-project-report")
@limiter.limit("5/minute")
async def generate_project_report_endpoint(request: Request, body: ProjectReportRequest, user: BackofficeUser = Depends(require_permission("can_generate_reports"))) -> dict:
    """Generate a project-wide report aggregating all sessions."""
    try:
        client = get_client()

        from src.engine.config_loader import get_implementation
        impl_config = await get_implementation(body.implementation_id)
        frameworks = impl_config.analysis_framework.get("frameworks", {}) if impl_config.analysis_framework else {}
        if body.framework not in frameworks:
            raise HTTPException(status_code=400, detail=f"Framework '{body.framework}' not found")

        # Get ALL session_facts for this implementation + framework
        query = (
            client.table("session_facts")
            .select("*")
            .eq("implementation_id", body.implementation_id)
            .eq("framework", body.framework)
        )
        if body.date_from:
            query = query.gte("created_at", body.date_from)
        if body.date_to:
            query = query.lte("created_at", body.date_to)
        facts_result = query.execute()
        all_facts = facts_result.data or []

        if not all_facts:
            return {"success": False, "data": None, "error": "No facts found. Generate individual reports first."}

        # Group facts by user_group (or "Sin grupo" for ungrouped)
        # Get session → group mapping
        session_ids = [f["session_id"] for f in all_facts]
        sessions = (
            client.table("sessions")
            .select("id, user_phone, user_name, group_id")
            .in_("id", session_ids)
            .execute()
        )
        session_map = {s["id"]: s for s in (sessions.data or [])}

        # Get group names
        groups = client.table("user_groups").select("id, name").eq("implementation_id", body.implementation_id).execute()
        group_names = {g["id"]: g["name"] for g in (groups.data or [])}

        # Bucket facts by group
        grouped: dict[str, list[dict]] = {}
        for fact in all_facts:
            sess = session_map.get(fact["session_id"], {})
            gid = sess.get("group_id") or "ungrouped"
            gname = group_names.get(gid, "Sin grupo asignado")
            fact["user_name"] = sess.get("user_name", "")
            if gname not in grouped:
                grouped[gname] = []
            grouped[gname].append(fact)

        # Generate mini group reports for each bucket
        from src.engine.analyzer import generate_group_report as gen_grp
        group_summaries = []
        date_range = f"{body.date_from or 'inicio'} a {body.date_to or 'hoy'}"

        for gname, gfacts in grouped.items():
            grp_md = await gen_grp(
                facts_rows=gfacts,
                framework_id=body.framework,
                framework_config=frameworks[body.framework],
                group_name=gname,
                date_range=date_range,
                implementation_name=impl_config.name,
            )
            if grp_md:
                group_summaries.append({
                    "group_name": gname,
                    "report_markdown": grp_md,
                    "session_count": len(gfacts),
                })

        if not group_summaries:
            return {"success": False, "data": None, "error": "Could not generate group-level summaries"}

        # Generate project-level report
        from src.engine.analyzer import generate_project_report
        markdown = await generate_project_report(
            group_reports=group_summaries,
            framework_id=body.framework,
            framework_config=frameworks[body.framework],
            implementation_name=impl_config.name,
            date_range=date_range,
            total_sessions=len(all_facts),
        )

        report_id = None
        if markdown:
            report_id = await _save_report(
                client, body.implementation_id, body.implementation_id,
                f"project_{body.framework}", markdown,
            )

        return {
            "success": markdown is not None,
            "data": {
                "implementation_id": body.implementation_id,
                "framework": body.framework,
                "groups_analyzed": len(group_summaries),
                "total_sessions": len(all_facts),
                "report_id": report_id,
                "chars": len(markdown) if markdown else 0,
                "markdown": markdown,
            },
            "error": None if markdown else "Project report generation failed",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("generate_project_report_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ── Report Persistence & Export ──────────────────────────────────────


@router.get("/reports")
async def list_reports(
    session_id: str | None = None,
    implementation_id: str | None = None,
    framework: str | None = None,
    limit: int = 50,
    user: BackofficeUser = Depends(get_current_user),
) -> dict:
    """List saved reports from consolidated_reports. Supports filtering."""
    try:
        client = get_client()
        query = (
            client.table("consolidated_reports")
            .select("id, implementation_id, title, framework, filters, status, created_at, analysis_markdown")
            .eq("status", "completed")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if session_id:
            query = query.contains("filters", {"session_id": session_id})
        if implementation_id:
            query = query.eq("implementation_id", implementation_id)
        if framework:
            query = query.eq("framework", framework)

        result = query.execute()
        return {"success": True, "data": result.data or [], "error": None}
    except Exception as e:
        logger.error("list_reports_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{report_id}")
async def get_report(report_id: str, user: BackofficeUser = Depends(get_current_user)) -> dict:
    """Get a single saved report by ID."""
    client = get_client()
    result = (
        client.table("consolidated_reports")
        .select("*")
        .eq("id", report_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"success": True, "data": result.data, "error": None}


class ExportGammaRequest(BaseModel):
    report_id: str | None = None
    markdown: str | None = None
    title: str = "Reporte de Campo"


@router.post("/export-gamma")
@limiter.limit("10/minute")
async def export_gamma(request: Request, body: ExportGammaRequest, user: BackofficeUser = Depends(get_current_user)) -> dict:
    """Export a report to Gamma presentation.

    Accepts either a report_id (loads from DB) or raw markdown.
    Returns a structured prompt for Gamma and attempts API creation if key is configured.
    """
    try:
        markdown = body.markdown
        title = body.title

        if body.report_id and not markdown:
            client = get_client()
            result = (
                client.table("consolidated_reports")
                .select("analysis_markdown, title, framework, implementation_id")
                .eq("id", body.report_id)
                .maybe_single()
                .execute()
            )
            if not result.data:
                raise HTTPException(status_code=404, detail="Report not found")
            markdown = result.data["analysis_markdown"]
            title = result.data.get("title") or title

        if not markdown:
            raise HTTPException(status_code=400, detail="Either report_id or markdown is required")

        # Build Gamma-optimized content: clean markdown → structured slides
        gamma_content = _build_gamma_content(markdown, title)

        response_data: dict[str, Any] = {
            "mode": "prompt",
            "gamma_content": gamma_content,
            "title": title,
            "url": None,
        }

        # Try Gamma API if key is available
        if settings.gamma_api_key:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=60) as http_client:
                    resp = await http_client.post(
                        "https://gamma.app/api/v1/presentations",
                        headers={
                            "Authorization": f"Bearer {settings.gamma_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={"content": gamma_content, "title": title},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        response_data["mode"] = "api"
                        response_data["url"] = data.get("url", data.get("presentation_url"))
            except Exception as e:
                logger.warning("gamma_api_failed", error=str(e))

        return {"success": True, "data": response_data, "error": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("export_gamma_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


def _build_gamma_content(markdown: str, title: str) -> str:
    """Convert report markdown into Gamma-optimized slide content."""
    lines = markdown.strip().split("\n")
    slides: list[str] = []

    # Title slide
    slides.append(f"# {title}\n*Generado por Field Genius Engine — Genius Labs AI*\n")

    current_section = ""
    current_body: list[str] = []

    for line in lines:
        if line.startswith("# ") and not current_section:
            # Skip the original H1 (already in title slide)
            continue
        elif line.startswith("## "):
            # Flush previous section
            if current_section:
                slides.append(f"## {current_section}\n" + "\n".join(current_body))
            current_section = line[3:].strip()
            current_body = []
        else:
            current_body.append(line)

    # Flush last section
    if current_section:
        slides.append(f"## {current_section}\n" + "\n".join(current_body))

    # Closing slide
    slides.append("## Proximos pasos\n\nRevisar hallazgos y definir plan de accion.\n\n---\n*Field Genius Engine — Genius Labs AI*")

    return "\n\n---\n\n".join(slides)


class ExportSheetsRequest(BaseModel):
    implementation_id: str
    date_from: str | None = None
    date_to: str | None = None
    include_facts: bool = True
    include_compliance: bool = True


@router.post("/export-sheets")
@limiter.limit("5/minute")
async def export_sheets(request: Request, body: ExportSheetsRequest, user: BackofficeUser = Depends(require_permission("can_generate_reports"))) -> dict:
    """Export structured data and facts to Google Sheets.

    Creates/updates tabs:
    - "Hechos Estructurados": facts from session_facts (entities, prices, alerts)
    - "Compliance": user activity summary (sessions per user, dates, file counts)
    """
    try:
        client = get_client()

        # Verify Google Sheets config
        if not settings.google_service_account_email or not settings.google_private_key:
            raise HTTPException(status_code=400, detail="Google Sheets credentials not configured")

        # Get implementation's spreadsheet ID
        impl_result = (
            client.table("implementations")
            .select("id, name, google_spreadsheet_id")
            .eq("id", body.implementation_id)
            .maybe_single()
            .execute()
        )
        if not impl_result.data:
            raise HTTPException(status_code=404, detail="Implementation not found")

        spreadsheet_id = impl_result.data.get("google_spreadsheet_id") or settings.google_spreadsheet_id
        if not spreadsheet_id:
            raise HTTPException(status_code=400, detail="No Google Spreadsheet ID configured for this implementation")

        import gspread
        from google.oauth2.service_account import Credentials

        creds_info = {
            "type": "service_account",
            "client_email": settings.google_service_account_email,
            "private_key": settings.google_private_key.replace("\\n", "\n"),
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        creds = Credentials.from_service_account_info(creds_info, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
        ])
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(spreadsheet_id)

        tabs_written: list[str] = []

        # ── Tab 1: Structured Facts ──
        if body.include_facts:
            facts_query = (
                client.table("session_facts")
                .select("*, sessions!inner(user_name, user_phone, date, country)")
                .eq("implementation_id", body.implementation_id)
            )
            if body.date_from:
                facts_query = facts_query.gte("created_at", body.date_from)
            if body.date_to:
                facts_query = facts_query.lte("created_at", body.date_to)

            facts_result = facts_query.execute()
            facts_rows = facts_result.data or []

            if facts_rows:
                facts_data = _build_facts_sheet(facts_rows)
                _write_sheet_tab(spreadsheet, "Hechos Estructurados", facts_data)
                tabs_written.append(f"Hechos Estructurados ({len(facts_rows)} registros)")

        # ── Tab 2: Compliance ──
        if body.include_compliance:
            compliance_data = await _get_compliance_data(client, body.implementation_id, body.date_from, body.date_to)
            if compliance_data:
                _write_sheet_tab(spreadsheet, "Compliance", compliance_data)
                tabs_written.append(f"Compliance ({len(compliance_data) - 1} usuarios)")

        return {
            "success": True,
            "data": {
                "spreadsheet_id": spreadsheet_id,
                "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
                "tabs_written": tabs_written,
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("export_sheets_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


def _build_facts_sheet(facts_rows: list[dict]) -> list[list[str]]:
    """Convert session_facts into flat rows for Sheets."""
    headers = [
        "Fecha", "Ejecutivo", "Telefono", "Pais", "Framework",
        "Entidad", "Tipo Entidad", "Menciones", "Contexto",
        "Precio Item", "Precio Valor", "Moneda", "Promocion",
        "Alerta Tipo", "Alerta Severidad", "Alerta Descripcion",
        "Sentimiento Pos", "Sentimiento Neg", "Sentimiento Neutral",
    ]
    rows: list[list[str]] = [headers]

    for fact_row in facts_rows:
        session = fact_row.get("sessions", {})
        facts = fact_row.get("facts") or {}
        base = [
            session.get("date", ""),
            session.get("user_name", ""),
            session.get("user_phone", ""),
            session.get("country", ""),
            fact_row.get("framework", ""),
        ]

        entities = facts.get("entities_mentioned", [])
        prices = facts.get("prices_detected", [])
        alerts = facts.get("alerts", [])
        sentiment = facts.get("sentiment", {})

        max_rows = max(len(entities), len(prices), len(alerts), 1)

        for i in range(max_rows):
            row = list(base)
            # Entity
            if i < len(entities):
                e = entities[i]
                row.extend([e.get("name", ""), e.get("type", ""), str(e.get("count", "")), e.get("context", "")])
            else:
                row.extend(["", "", "", ""])
            # Price
            if i < len(prices):
                p = prices[i]
                row.extend([p.get("item", ""), str(p.get("price", "")), p.get("currency", ""), str(p.get("is_promotion", ""))])
            else:
                row.extend(["", "", "", ""])
            # Alert
            if i < len(alerts):
                a = alerts[i]
                row.extend([a.get("type", ""), a.get("severity", ""), a.get("description", "")])
            else:
                row.extend(["", "", ""])
            # Sentiment (only first row)
            if i == 0:
                row.extend([str(sentiment.get("positive", "")), str(sentiment.get("negative", "")), str(sentiment.get("neutral", ""))])
            else:
                row.extend(["", "", ""])

            rows.append(row)

    return rows


async def _get_compliance_data(
    client: Any, implementation_id: str, date_from: str | None, date_to: str | None
) -> list[list[str]]:
    """Build compliance matrix: which users sent data and which didn't."""
    # Get all registered users for this implementation
    users_result = (
        client.table("users")
        .select("phone, name, role, created_at")
        .eq("implementation", implementation_id)
        .execute()
    )
    all_users = {u["phone"]: u for u in (users_result.data or [])}

    # Get sessions grouped by user
    sessions_query = (
        client.table("sessions")
        .select("user_phone, user_name, date, status, raw_files")
        .eq("implementation", implementation_id)
    )
    if date_from:
        sessions_query = sessions_query.gte("date", date_from)
    if date_to:
        sessions_query = sessions_query.lte("date", date_to)

    sessions_result = sessions_query.order("date").execute()
    sessions = sessions_result.data or []

    # Aggregate per user
    user_stats: dict[str, dict[str, Any]] = {}
    for s in sessions:
        phone = s.get("user_phone", "")
        if phone not in user_stats:
            user_stats[phone] = {
                "name": s.get("user_name", all_users.get(phone, {}).get("name", "")),
                "sessions": 0,
                "files": 0,
                "images": 0,
                "audio": 0,
                "completed": 0,
                "first_date": s.get("date"),
                "last_date": s.get("date"),
                "dates": set(),
            }
        stats = user_stats[phone]
        stats["sessions"] += 1
        stats["last_date"] = s.get("date")
        stats["dates"].add(s.get("date", ""))
        if s.get("status") == "completed":
            stats["completed"] += 1
        for f in (s.get("raw_files") or []):
            stats["files"] += 1
            if f.get("type") == "image":
                stats["images"] += 1
            elif f.get("type") == "audio":
                stats["audio"] += 1

    # Build output: include users with NO sessions too
    headers = [
        "Ejecutivo", "Telefono", "Rol", "Sesiones", "Completadas",
        "Archivos", "Imagenes", "Audios", "Dias Activos",
        "Primera Sesion", "Ultima Sesion", "Estado",
    ]
    rows: list[list[str]] = [headers]

    # Active users (have sessions)
    for phone, stats in sorted(user_stats.items(), key=lambda x: x[1]["sessions"], reverse=True):
        role = all_users.get(phone, {}).get("role", "")
        rows.append([
            stats["name"],
            phone,
            role,
            str(stats["sessions"]),
            str(stats["completed"]),
            str(stats["files"]),
            str(stats["images"]),
            str(stats["audio"]),
            str(len(stats["dates"])),
            stats["first_date"] or "",
            stats["last_date"] or "",
            "Activo",
        ])

    # Inactive users (registered but no sessions in range)
    for phone, u in all_users.items():
        if phone not in user_stats:
            rows.append([
                u.get("name", ""),
                phone,
                u.get("role", ""),
                "0", "0", "0", "0", "0", "0", "", "",
                "Sin actividad",
            ])

    return rows


def _write_sheet_tab(spreadsheet: Any, tab_name: str, data: list[list[str]]) -> None:
    """Write data to a Google Sheets tab, creating it if needed."""
    try:
        worksheet = spreadsheet.worksheet(tab_name)
        worksheet.clear()
    except Exception:
        worksheet = spreadsheet.add_worksheet(title=tab_name, rows=len(data) + 10, cols=len(data[0]) + 2)

    worksheet.update(range_name="A1", values=data, value_input_option="USER_ENTERED")


# ── Compliance Endpoint ────────────────────────────────────────────


@router.get("/compliance")
async def get_compliance(
    implementation_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
    user: BackofficeUser = Depends(get_current_user),
) -> dict:
    """Get user compliance data: who sent sessions, who didn't, activity metrics."""
    try:
        client = get_client()
        compliance_rows = await _get_compliance_data(client, implementation_id, date_from, date_to)

        # Parse headers + rows into list of dicts for frontend
        if len(compliance_rows) < 2:
            return {"success": True, "data": {"users": [], "summary": {"total": 0, "active": 0, "inactive": 0}}, "error": None}

        headers = compliance_rows[0]
        users = []
        active = 0
        inactive = 0
        for row in compliance_rows[1:]:
            user_dict = dict(zip(headers, row))
            users.append(user_dict)
            if user_dict.get("Estado") == "Activo":
                active += 1
            else:
                inactive += 1

        return {
            "success": True,
            "data": {
                "users": users,
                "summary": {
                    "total": active + inactive,
                    "active": active,
                    "inactive": inactive,
                    "compliance_rate": round(active / (active + inactive) * 100, 1) if (active + inactive) > 0 else 0,
                },
            },
            "error": None,
        }
    except Exception as e:
        logger.error("get_compliance_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ── Backoffice User Management ─────────────────────────────────────


class BackofficeUserCreate(BaseModel):
    email: str
    name: str
    role: str = "admin"  # superadmin, admin, analyst, viewer
    allowed_implementations: list[str] = []
    permissions: dict[str, bool] = {}


@router.get("/backoffice-users")
async def list_backoffice_users_endpoint(user: BackofficeUser = Depends(require_superadmin())) -> dict:
    """List all backoffice users. Superadmin only."""
    from src.routes.auth import list_backoffice_users
    users = await list_backoffice_users()
    return {"success": True, "data": users, "error": None}


@router.post("/backoffice-users")
async def create_backoffice_user_endpoint(body: BackofficeUserCreate, user: BackofficeUser = Depends(require_superadmin())) -> dict:
    """Create or update a backoffice user. Creates auth.users record if needed."""
    try:
        from src.routes.auth import create_backoffice_user
        user = await create_backoffice_user(
            email=body.email,
            name=body.name,
            role=body.role,
            allowed_implementations=body.allowed_implementations,
            permissions=body.permissions,
        )
        return {"success": True, "data": user, "error": None}
    except Exception as e:
        logger.error("create_backoffice_user_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/backoffice-users/{user_id}")
async def update_backoffice_user_endpoint(user_id: str, body: dict[str, Any], user: BackofficeUser = Depends(require_superadmin())) -> dict:
    """Update a backoffice user's role, permissions, or allowed implementations."""
    client = get_client()
    allowed_fields = {"role", "name", "allowed_implementations", "permissions", "is_active"}
    updates = {k: v for k, v in body.items() if k in allowed_fields}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    client.table("backoffice_users").update(updates).eq("id", user_id).execute()
    result = client.table("backoffice_users").select("*").eq("id", user_id).maybe_single().execute()
    return {"success": True, "data": result.data, "error": None}


@router.get("/my-profile")
async def get_my_profile(request: Request) -> dict:
    """Get the current user's backoffice profile (role, permissions, implementations)."""
    try:
        from src.routes.auth import get_current_user
        user = await get_current_user(request)
        from src.routes.auth import ROLE_PERMISSIONS
        effective_perms = ROLE_PERMISSIONS.get(user.role, {}).copy()
        effective_perms.update(user.permissions)

        return {
            "success": True,
            "data": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "is_superadmin": user.is_superadmin,
                "allowed_implementations": user.allowed_implementations,
                "permissions": effective_perms,
            },
            "error": None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Authentication required")


# ── Retention & Usage ──────────────────────────────────────────────


@router.post("/run-retention")
async def run_retention_endpoint(user: BackofficeUser = Depends(require_superadmin()),
    retention_days: int = 90,
    dry_run: bool = True,
) -> dict:
    """Run media retention cleanup. Default is dry_run=True (preview only)."""
    from src.engine.retention import run_retention
    result = await run_retention(retention_days=retention_days, dry_run=dry_run)
    return {"success": True, "data": result, "error": None}


@router.get("/usage")
async def get_usage(impl: str | None = None, user: BackofficeUser = Depends(get_current_user)) -> dict:
    """Get usage stats for billing/monitoring. Computed live from DB."""
    client = get_client()

    # Current month
    now = datetime.datetime.now(datetime.UTC)
    current_month = now.strftime("%Y-%m")
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    implementations: list[str] = []
    if impl:
        implementations = [impl]
    else:
        result = client.table("implementations").select("id").eq("status", "active").execute()
        implementations = [r["id"] for r in (result.data or [])]

    usage_data = []
    for impl_id in implementations:
        # Sessions this month
        sessions = (
            client.table("sessions")
            .select("id, raw_files, user_phone, status")
            .eq("implementation", impl_id)
            .gte("created_at", month_start)
            .execute()
        )
        session_list = sessions.data or []

        # Count files by type
        total_files = 0
        images = 0
        audio = 0
        video = 0
        text = 0
        total_bytes = 0
        active_phones: set[str] = set()

        for s in session_list:
            active_phones.add(s.get("user_phone", ""))
            for f in (s.get("raw_files") or []):
                total_files += 1
                total_bytes += f.get("size_bytes", 0)
                ft = f.get("type", "")
                if ft == "image":
                    images += 1
                elif ft == "audio":
                    audio += 1
                elif ft == "video":
                    video += 1
                elif ft == "text":
                    text += 1

        # Reports this month
        reports = (
            client.table("session_facts")
            .select("id", count="exact")
            .eq("implementation_id", impl_id)
            .gte("created_at", month_start)
            .execute()
        )
        report_count = reports.count or 0

        usage_data.append({
            "implementation_id": impl_id,
            "month": current_month,
            "active_users": len(active_phones),
            "total_sessions": len(session_list),
            "total_files": total_files,
            "images": images,
            "audio": audio,
            "video": video,
            "text": text,
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 1),
            "reports_generated": report_count,
        })

    # Queue stats
    from src.engine.worker import get_queue_stats
    queue = await get_queue_stats()

    return {
        "success": True,
        "data": {
            "month": current_month,
            "implementations": usage_data,
            "queue": queue,
        },
        "error": None,
    }


# ── Digest (Cron) ──────────────────────────────────────────────────


@router.post("/send-digest")
async def send_digest(
    implementation_id: str | None = None,
    user: BackofficeUser = Depends(require_permission("can_generate_reports")),
) -> dict:
    """Send daily digest email for one or all implementations.

    Call manually from backoffice or via Railway cron.
    Only sends to implementations with digest.enabled=true and digest.emails configured.
    """
    from src.engine.digest import run_digest_for_implementation
    client = get_client()

    if implementation_id:
        impl_ids = [implementation_id]
    else:
        result = client.table("implementations").select("id").eq("status", "active").execute()
        impl_ids = [r["id"] for r in (result.data or [])]

    results = []
    for impl_id in impl_ids:
        try:
            r = await run_digest_for_implementation(impl_id)
            results.append(r)
        except Exception as e:
            logger.error("digest_failed", implementation=impl_id, error=str(e))
            results.append({"implementation_id": impl_id, "status": "error", "error": str(e)[:100]})

    return {"success": True, "data": {"digests": results}, "error": None}


@router.post("/test-digest")
async def test_digest(
    implementation_id: str,
    email: str,
    user: BackofficeUser = Depends(require_superadmin()),
) -> dict:
    """Generate and send a test digest to a specific email. Superadmin only."""
    from src.engine.digest import generate_digest, build_digest_html, send_digest_email

    data = await generate_digest(implementation_id)
    if not data:
        return {"success": False, "data": None, "error": "No activity today for this implementation"}

    html = build_digest_html(data)
    subject = f"[TEST] Resumen del dia — {data['implementation_name']} | {data['date']}"
    sent = await send_digest_email([email], subject, html)

    return {
        "success": sent,
        "data": {"preview": data, "sent_to": email} if sent else None,
        "error": None if sent else "Email sending failed — check RESEND_API_KEY",
    }
