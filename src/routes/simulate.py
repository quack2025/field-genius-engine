"""Simulate endpoint — test the ingestion pipeline without Twilio."""

from __future__ import annotations

import datetime
from typing import Any

import structlog
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from src.channels.whatsapp.session_manager import handle_media, handle_text
from src.engine.media_downloader import store_bytes
from src.engine.supabase_client import get_or_create_session, get_session

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["simulate"])


@router.post("/simulate")
async def simulate(
    phone: str = Form(..., description="Phone number, e.g. +573001234567"),
    body: str = Form("", description="Text message body"),
    file: UploadFile | None = File(None, description="Media file (image, audio, video)"),
) -> JSONResponse:
    """Simulate a WhatsApp message for local testing.

    Usage:
    - Text only: phone=+573001234567, body="Hola"
    - Media: phone=+573001234567, file=<upload>
    - Trigger: phone=+573001234567, body="reporte"
    """
    logger.info("simulate_request", phone=phone, body=body[:50] if body else "", has_file=file is not None)

    today = datetime.date.today()
    session = await get_or_create_session(phone, today)

    response_data: dict[str, Any] = {
        "session_id": session["id"],
        "phone": phone,
    }

    # Handle file upload
    if file is not None:
        file_bytes = await file.read()
        content_type = file.content_type or "application/octet-stream"

        file_meta = await store_bytes(
            file_bytes=file_bytes,
            content_type=content_type,
            session_id=session["id"],
            filename=file.filename,
        )

        await handle_media(phone, file_meta)
        response_data["action"] = "media_received"
        response_data["file"] = file_meta
        response_data["reply"] = "Recibido"

    # Handle text
    elif body:
        result = await handle_text(phone, body)
        response_data["action"] = result["action"]
        response_data["reply"] = result["message"]

        # If trigger → run the pipeline
        if result["action"] == "trigger":
            from src.engine.pipeline import process_session
            pipeline_result = await process_session(session["id"])
            response_data["pipeline"] = {
                "status": pipeline_result.status,
                "visits": len(pipeline_result.extractions),
                "report_ids": pipeline_result.report_ids,
                "elapsed_ms": pipeline_result.elapsed_ms,
                "error": pipeline_result.error,
                "pdf_url": pipeline_result.pdf_url,
                "sheets_tabs": pipeline_result.sheets_tabs,
                "gamma": pipeline_result.gamma_result,
            }
            if pipeline_result.segmentation:
                response_data["segmentation"] = pipeline_result.segmentation.raw_json
            if pipeline_result.extractions:
                response_data["extractions"] = [
                    {
                        "visit_type": e.visit_type,
                        "location": e.inferred_location,
                        "confidence": e.confidence_score,
                        "data": e.extracted_data,
                    }
                    for e in pipeline_result.extractions
                ]

    else:
        return JSONResponse(
            status_code=400,
            content={"success": False, "data": None, "error": "Provide either body or file"},
        )

    # Fetch updated session
    updated_session = await get_session(session["id"])
    response_data["session"] = updated_session

    return JSONResponse(content={"success": True, "data": response_data, "error": None})


@router.get("/sessions/{phone}")
async def get_sessions_by_phone(phone: str) -> JSONResponse:
    """Get today's session for a phone number."""
    today = datetime.date.today()
    session = await get_or_create_session(phone, today)
    return JSONResponse(content={"success": True, "data": session, "error": None})
