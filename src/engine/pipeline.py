"""Pipeline orchestrator — runs the full analysis pipeline for a session."""

from __future__ import annotations

import asyncio
import datetime
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from src.engine.segmenter import segment_session, SegmentationResult
from src.engine.extractor import extract_visit, ExtractedVisit
from src.engine.supabase_client import (
    get_session,
    update_session_status,
    save_visit_report,
    get_client,
)

logger = structlog.get_logger(__name__)


@dataclass
class PipelineResult:
    """Full pipeline result."""
    session_id: str
    segmentation: SegmentationResult | None = None
    extractions: list[ExtractedVisit] = field(default_factory=list)
    report_ids: list[str] = field(default_factory=list)
    status: str = "completed"  # completed | needs_clarification | failed
    error: str | None = None
    elapsed_ms: int = 0
    pdf_url: str | None = None
    gamma_result: dict[str, Any] | None = None
    sheets_tabs: list[str] = field(default_factory=list)


async def _fire_and_forget_sheets(
    report_data: dict[str, Any],
    session: dict[str, Any],
    implementation: str,
) -> str | None:
    """Write to Google Sheets — fire-and-forget."""
    try:
        from src.outputs.sheets import write_visit_report
        return await write_visit_report(report_data, session, implementation)
    except Exception as e:
        logger.error("pipeline_sheets_failed", error=str(e))
        return None


async def _fire_and_forget_gamma(
    report_data_list: list[dict[str, Any]],
    session: dict[str, Any],
) -> dict[str, Any] | None:
    """Create Gamma presentation — fire-and-forget."""
    try:
        from src.outputs.gamma import create_presentation
        return await create_presentation(report_data_list, session)
    except Exception as e:
        logger.error("pipeline_gamma_failed", error=str(e))
        return None


async def _generate_and_upload_pdf(
    report_data_list: list[dict[str, Any]],
    session: dict[str, Any],
) -> str | None:
    """Generate PDF and upload to Supabase Storage. Returns public URL or None."""
    try:
        from src.utils.pdf import generate_report_pdf

        pdf_bytes = await generate_report_pdf(report_data_list, session)
        if not pdf_bytes:
            return None

        # Upload to Supabase Storage
        client = get_client()
        session_id = session["id"]
        date_str = session.get("date", str(datetime.date.today()))
        filename = f"reports/{session_id}/reporte_{date_str}.pdf"

        client.storage.from_("media").upload(
            filename,
            pdf_bytes,
            {"content-type": "application/pdf"},
        )

        # Get public URL
        url = client.storage.from_("media").get_public_url(filename)
        logger.info("pdf_uploaded", url=url, size_kb=len(pdf_bytes) // 1024)
        return url

    except Exception as e:
        logger.error("pipeline_pdf_failed", error=str(e))
        return None


async def _send_whatsapp_delivery(
    phone: str,
    report_data_list: list[dict[str, Any]],
    session: dict[str, Any],
    pdf_url: str | None,
) -> None:
    """Send WhatsApp summary + PDF to the executive."""
    try:
        from src.utils.pdf import build_whatsapp_summary
        from src.channels.whatsapp.sender import send_message, send_media

        summary = build_whatsapp_summary(report_data_list, session)

        if pdf_url:
            await send_media(phone, summary, pdf_url)
        else:
            await send_message(phone, summary)

        logger.info("whatsapp_delivery_sent", phone=phone, has_pdf=pdf_url is not None)

    except Exception as e:
        logger.error("whatsapp_delivery_failed", phone=phone, error=str(e))


async def process_session(session_id: str) -> PipelineResult:
    """Orchestrate the full analysis pipeline.

    Steps:
    1. Load session from Supabase
    2. Phase 1: Segmentation (identify visits)
    3. If needs_clarification -> pause and notify user
    4. Phase 2: Extraction (extract data per visit)
    5. Save visit_reports to Supabase
    6. Outputs: Sheets (fire-and-forget), PDF, Gamma (fire-and-forget), WhatsApp delivery
    7. Update session status
    """
    start = time.time()
    logger.info("pipeline_start", session_id=session_id)

    result = PipelineResult(session_id=session_id)

    try:
        # Step 1: Load session
        session = await get_session(session_id)
        if not session:
            result.status = "failed"
            result.error = f"Session {session_id} not found"
            logger.error("pipeline_session_not_found", session_id=session_id)
            return result

        raw_files = session.get("raw_files", [])
        logger.info("pipeline_session_loaded", files=len(raw_files), phone=session["user_phone"])

        # Step 2: Phase 1 — Segmentation
        await update_session_status(session_id, "segmenting")
        logger.info("pipeline_phase1_start")

        segmentation = await segment_session(session)
        result.segmentation = segmentation

        logger.info(
            "pipeline_phase1_complete",
            visits=len(segmentation.visits),
            needs_clarification=segmentation.needs_clarification,
            elapsed_ms=segmentation.elapsed_ms,
        )

        # Save segmentation result to session
        client = get_client()
        client.table("sessions").update({
            "segments": segmentation.raw_json,
            "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }).eq("id", session_id).execute()

        # Step 3: Check if clarification needed
        if segmentation.needs_clarification:
            await update_session_status(session_id, "needs_clarification")
            result.status = "needs_clarification"
            result.elapsed_ms = int((time.time() - start) * 1000)

            # Send clarification question to user via WhatsApp
            phone = session.get("user_phone", "")
            if phone and segmentation.clarification_message:
                from src.channels.whatsapp.sender import send_message
                await send_message(
                    phone,
                    f"Tengo una pregunta antes de generar tu reporte:\n\n{segmentation.clarification_message}",
                )

            logger.info(
                "pipeline_needs_clarification",
                message=segmentation.clarification_message,
            )
            return result

        # Step 4: Phase 2 — Extraction per visit
        await update_session_status(session_id, "processing")
        logger.info("pipeline_phase2_start", visits=len(segmentation.visits))

        implementation = session.get("implementation", "argos")
        report_data_list: list[dict[str, Any]] = []

        for i, visit in enumerate(segmentation.visits):
            logger.info(
                "pipeline_extracting_visit",
                visit_num=i + 1,
                visit_type=visit.visit_type,
                location=visit.inferred_location,
            )

            extraction = await extract_visit(visit, implementation)
            result.extractions.append(extraction)

            # Save visit report to Supabase
            report_data = {
                "session_id": session_id,
                "implementation": implementation,
                "visit_type": extraction.visit_type,
                "inferred_location": extraction.inferred_location,
                "extracted_data": extraction.extracted_data,
                "confidence_score": extraction.confidence_score,
                "status": "needs_review" if extraction.needs_review else "completed",
                "processing_time_ms": extraction.elapsed_ms,
            }
            report_id = await save_visit_report(report_data)
            result.report_ids.append(report_id)
            report_data["id"] = report_id
            report_data_list.append(report_data)

            logger.info(
                "pipeline_visit_saved",
                visit_num=i + 1,
                report_id=report_id,
                confidence=extraction.confidence_score,
            )

        # Step 5: Outputs — Sheets only (PDF/Gamma temporarily disabled)
        # Note: stay in 'processing' status (generating_outputs not in DB CHECK constraint)
        logger.info("pipeline_outputs_start", reports=len(report_data_list))

        # Launch Sheets writes
        sheets_tasks = [
            _fire_and_forget_sheets(rd, session, implementation)
            for rd in report_data_list
        ]
        sheets_results = await asyncio.gather(*sheets_tasks, return_exceptions=True)

        # Collect Sheets results
        for sr in sheets_results:
            if isinstance(sr, str):
                result.sheets_tabs.append(sr)

        # PDF and Gamma temporarily disabled — uncomment when ready:
        # gamma_task = _fire_and_forget_gamma(report_data_list, session)
        # pdf_task = _generate_and_upload_pdf(report_data_list, session)

        logger.info(
            "pipeline_outputs_complete",
            sheets_tabs=result.sheets_tabs,
        )

        # Step 6: WhatsApp delivery — text summary only (no PDF for now)
        phone = session.get("user_phone", "")
        if phone:
            await _send_whatsapp_delivery(phone, report_data_list, session, None)

        # Step 7: Mark session complete
        await update_session_status(session_id, "completed")
        result.status = "completed"
        result.elapsed_ms = int((time.time() - start) * 1000)

        logger.info(
            "pipeline_complete",
            session_id=session_id,
            visits_processed=len(result.extractions),
            reports_saved=len(result.report_ids),
            sheets_tabs=result.sheets_tabs,
            has_pdf=pdf_url is not None,
            elapsed_ms=result.elapsed_ms,
        )

        return result

    except Exception as e:
        result.status = "failed"
        result.error = str(e)
        result.elapsed_ms = int((time.time() - start) * 1000)

        await update_session_status(session_id, "failed")
        logger.error("pipeline_failed", session_id=session_id, error=str(e), elapsed_ms=result.elapsed_ms)

        return result
