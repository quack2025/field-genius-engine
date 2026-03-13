"""Admin API — CRUD for implementations, visit types, users, and testing."""

from __future__ import annotations

import datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.config.settings import settings
from src.engine.supabase_client import get_client

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


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
async def list_implementations() -> dict:
    client = get_client()
    result = client.table("implementations").select("*").order("name").execute()
    return {"success": True, "data": result.data or [], "error": None}


@router.post("/implementations")
async def create_implementation(body: ImplementationCreate) -> dict:
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
async def get_implementation(impl_id: str) -> dict:
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
async def update_implementation(impl_id: str, body: ImplementationUpdate) -> dict:
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
async def delete_implementation(impl_id: str) -> dict:
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
async def list_visit_types(impl_id: str) -> dict:
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
async def create_visit_type(impl_id: str, body: VisitTypeCreate) -> dict:
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
async def update_visit_type(vt_id: str, body: VisitTypeUpdate) -> dict:
    client = get_client()
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
async def delete_visit_type(vt_id: str) -> dict:
    client = get_client()
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
async def list_users(impl_id: str) -> dict:
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
async def assign_user(impl_id: str, body: UserAssign) -> dict:
    client = get_client()
    row = {
        "phone": body.phone,
        "name": body.name,
        "role": body.role,
        "implementation": impl_id,
    }

    try:
        result = client.table("users").upsert(row, on_conflict="phone").execute()
        logger.info("user_assigned", phone=body.phone, implementation=impl_id)
        return {"success": True, "data": result.data[0], "error": None}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/implementations/{impl_id}/users/{phone}")
async def remove_user(impl_id: str, phone: str) -> dict:
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
async def get_stats(impl: str | None = None, days: int = 7) -> dict:
    client = get_client()
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

    # Sessions count
    query = client.table("sessions").select("id, status, date, implementation").gte("date", cutoff)
    if impl:
        query = query.eq("implementation", impl)
    sessions_result = query.execute()
    sessions = sessions_result.data or []

    # Visit reports count
    vr_query = client.table("visit_reports").select("id, implementation, confidence_score, status").gte("created_at", cutoff + "T00:00:00")
    if impl:
        vr_query = vr_query.eq("implementation", impl)
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
) -> dict:
    """List sessions with optional filters."""
    client = get_client()
    query = client.table("sessions").select("*").order("date", desc=True).order("created_at", desc=True)

    if impl:
        query = query.eq("implementation", impl)
    if phone:
        query = query.eq("user_phone", phone)
    if status:
        query = query.eq("status", status)
    if date_from:
        query = query.gte("date", date_from)
    if date_to:
        query = query.lte("date", date_to)

    query = query.range(offset, offset + limit - 1)
    result = query.execute()
    return {"success": True, "data": result.data or [], "error": None}


@router.get("/sessions/{session_id}")
async def get_session_detail(session_id: str) -> dict:
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
async def reload_config(impl_id: str | None = None) -> dict:
    from src.engine.config_loader import reload
    await reload(impl_id)
    return {
        "success": True,
        "data": {"reloaded": impl_id or "all"},
        "error": None,
    }


# ── Test Endpoints (Prompt Engineering) ───────────────────────────


@router.post("/test-vision-prompt")
async def test_vision_prompt(body: TestVisionRequest) -> dict:
    """Test a vision prompt against an image URL. Returns the AI description."""
    try:
        import anthropic
        from src.config.settings import settings

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        # Fetch image bytes
        import httpx
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.get(body.image_url)
            resp.raise_for_status()
            image_bytes = resp.content
            media_type = resp.headers.get("content-type", "image/jpeg")

        import base64
        b64 = base64.b64encode(image_bytes).decode()

        response = client.messages.create(
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


@router.post("/test-extraction")
async def test_extraction(body: TestExtractionRequest) -> dict:
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
