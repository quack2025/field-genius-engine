"""Tests for src.engine.pipeline — process_session and resume_after_clarification."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.engine.segmenter import SegmentationResult, VisitSegment
from src.engine.extractor import ExtractedVisit
from src.engine.pipeline import PipelineResult, process_session, resume_after_clarification


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_session(
    session_id: str = "sess-001",
    raw_files: list | None = None,
    segments: dict | None = None,
    status: str = "accumulating",
) -> dict:
    """Build a minimal session dict matching the Supabase row shape."""
    return {
        "id": session_id,
        "user_phone": "+573001234567",
        "user_name": "Test User",
        "date": "2026-03-12",
        "status": status,
        "raw_files": raw_files or [],
        "segments": segments,
        "implementation": "argos",
    }


def _make_visit_segment(
    segment_id: str = "seg-1",
    visit_type: str = "ferreteria",
    files: list[str] | None = None,
) -> VisitSegment:
    return VisitSegment(
        segment_id=segment_id,
        inferred_location="Ferreteria El Constructor",
        visit_type=visit_type,
        confidence=0.92,
        files=files or ["img_001.jpg", "audio_01.ogg"],
        time_range="10:15 - 10:52",
        transcriptions={"audio_01.ogg": "Cemento Argos 50kg a 32000 pesos"},
        image_descriptions={"img_001.jpg": "Estante con bolsas de cemento Argos"},
    )


def _make_extraction(visit_type: str = "ferreteria") -> ExtractedVisit:
    return ExtractedVisit(
        visit_type=visit_type,
        inferred_location="Ferreteria El Constructor",
        extracted_data={
            "precios": [{"producto": "Cemento Gris 50kg", "marca": "Argos", "precio": 32000}],
            "confidence_score": 0.88,
        },
        confidence_score=0.88,
        needs_review=False,
        elapsed_ms=450,
    )


# ---------------------------------------------------------------------------
# Helpers to set up common mocks
# ---------------------------------------------------------------------------

def _patch_supabase_client():
    """Return a mock that satisfies get_client().table(...).update(...).eq(...).execute()."""
    mock_client = MagicMock()
    mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = None
    return mock_client


# ---------------------------------------------------------------------------
# Test 1: Empty session (no raw_files) -> segmentation produces empty context
#          -> pipeline returns needs_clarification from segmenter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_empty_session():
    """Session with no files: segmenter returns needs_clarification, pipeline pauses."""
    session = _make_session(raw_files=[])
    empty_segmentation = SegmentationResult(
        visits=[],
        needs_clarification=True,
        clarification_message="No pude procesar ningun archivo de la sesion.",
        elapsed_ms=50,
    )

    with (
        patch("src.engine.pipeline.get_session", new_callable=AsyncMock, return_value=session),
        patch("src.engine.pipeline.update_session_status", new_callable=AsyncMock),
        patch("src.engine.pipeline.segment_session", new_callable=AsyncMock, return_value=empty_segmentation),
        patch("src.engine.pipeline.get_client", return_value=_patch_supabase_client()),
        patch("src.channels.whatsapp.sender.send_message", new_callable=AsyncMock),
    ):
        result = await process_session("sess-001")

    assert isinstance(result, PipelineResult)
    assert result.status == "needs_clarification"
    assert result.extractions == []
    assert result.report_ids == []


# ---------------------------------------------------------------------------
# Test 2: Single visit — full happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_single_visit():
    """One visit segmented, extraction succeeds, report saved."""
    session = _make_session(
        raw_files=[
            {"filename": "img_001.jpg", "type": "image", "storage_path": "media/img_001.jpg"},
            {"filename": "audio_01.ogg", "type": "audio", "storage_path": "media/audio_01.ogg"},
        ],
    )
    visit = _make_visit_segment()
    segmentation = SegmentationResult(
        visits=[visit],
        needs_clarification=False,
        raw_json={"sessions": [{"id": "seg-1", "files": visit.files}]},
        elapsed_ms=800,
    )
    extraction = _make_extraction()

    with (
        patch("src.engine.pipeline.get_session", new_callable=AsyncMock, return_value=session),
        patch("src.engine.pipeline.update_session_status", new_callable=AsyncMock) as mock_status,
        patch("src.engine.pipeline.segment_session", new_callable=AsyncMock, return_value=segmentation),
        patch("src.engine.pipeline.extract_visit", new_callable=AsyncMock, return_value=extraction),
        patch("src.engine.pipeline.save_visit_report", new_callable=AsyncMock, return_value="report-001"),
        patch("src.engine.pipeline.get_client", return_value=_patch_supabase_client()),
        patch("src.engine.pipeline._fire_and_forget_sheets", new_callable=AsyncMock, return_value="Ferreterias"),
        patch("src.engine.pipeline._send_whatsapp_delivery", new_callable=AsyncMock),
    ):
        result = await process_session("sess-001")

    assert result.status == "completed"
    assert len(result.extractions) == 1
    assert result.extractions[0].confidence_score == 0.88
    assert result.report_ids == ["report-001"]
    assert result.sheets_tabs == ["Ferreterias"]

    # Verify status transitions: segmenting -> processing -> completed
    status_calls = [call.args[1] for call in mock_status.call_args_list]
    assert "segmenting" in status_calls
    assert "processing" in status_calls
    assert "completed" in status_calls


# ---------------------------------------------------------------------------
# Test 3: Segmentation needs clarification -> pipeline pauses
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_needs_clarification():
    """Segmentation flags needs_clarification -> pipeline pauses without extraction."""
    session = _make_session(
        raw_files=[
            {"filename": "img_001.jpg", "type": "image", "storage_path": "media/img_001.jpg"},
        ],
    )
    segmentation = SegmentationResult(
        visits=[
            _make_visit_segment(segment_id="seg-1", files=["img_001.jpg"]),
        ],
        needs_clarification=True,
        clarification_message="La foto img_004.jpg no la pude ubicar. Es de El Constructor o de la obra?",
        raw_json={"sessions": [], "needs_clarification": True},
        elapsed_ms=600,
    )

    with (
        patch("src.engine.pipeline.get_session", new_callable=AsyncMock, return_value=session),
        patch("src.engine.pipeline.update_session_status", new_callable=AsyncMock) as mock_status,
        patch("src.engine.pipeline.segment_session", new_callable=AsyncMock, return_value=segmentation),
        patch("src.engine.pipeline.get_client", return_value=_patch_supabase_client()),
        patch("src.channels.whatsapp.sender.send_message", new_callable=AsyncMock) as mock_wa,
    ):
        result = await process_session("sess-001")

    assert result.status == "needs_clarification"
    assert result.extractions == []
    assert result.report_ids == []

    # Verify WhatsApp clarification message was sent
    mock_wa.assert_awaited_once()
    sent_text = mock_wa.call_args.args[1]
    assert "pregunta" in sent_text.lower() or "img_004" in sent_text

    # Status should be set to needs_clarification
    status_calls = [call.args[1] for call in mock_status.call_args_list]
    assert "needs_clarification" in status_calls
    # Should NOT have reached "processing" or "completed"
    assert "completed" not in status_calls


# ---------------------------------------------------------------------------
# Test 4: Resume after clarification — Phase 2 runs with saved segments
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resume_after_clarification():
    """Saved segments exist in session; resume runs extraction and saves reports."""
    saved_segments = {
        "sessions": [
            {
                "id": "seg-1",
                "inferred_location": "Ferreteria El Constructor",
                "visit_type": "ferreteria",
                "confidence": 0.92,
                "files": ["img_001.jpg", "audio_01.ogg"],
                "time_range": "10:15 - 10:52",
            }
        ],
        "needs_clarification": False,
    }
    session = _make_session(
        raw_files=[
            {"filename": "img_001.jpg", "type": "image", "storage_path": "media/img_001.jpg"},
            {"filename": "audio_01.ogg", "type": "audio", "storage_path": "media/audio_01.ogg"},
        ],
        segments=saved_segments,
        status="needs_clarification",
    )
    extraction = _make_extraction()

    with (
        patch("src.engine.pipeline.get_session", new_callable=AsyncMock, return_value=session),
        patch("src.engine.pipeline.update_session_status", new_callable=AsyncMock) as mock_status,
        patch("src.engine.pipeline.extract_visit", new_callable=AsyncMock, return_value=extraction),
        patch("src.engine.pipeline.save_visit_report", new_callable=AsyncMock, return_value="report-002"),
        patch("src.engine.pipeline._fire_and_forget_sheets", new_callable=AsyncMock, return_value=None),
        patch("src.engine.pipeline._send_whatsapp_delivery", new_callable=AsyncMock),
        patch("src.engine.vision.analyze_from_storage", new_callable=AsyncMock, return_value="Estante con cemento"),
    ):
        result = await resume_after_clarification("sess-001", "Si, todo es de El Constructor")

    assert result.status == "completed"
    assert len(result.extractions) == 1
    assert result.report_ids == ["report-002"]

    # Verify status went to processing -> completed
    status_calls = [call.args[1] for call in mock_status.call_args_list]
    assert "processing" in status_calls
    assert "completed" in status_calls


# ---------------------------------------------------------------------------
# Test 5: Resume with no saved segments -> fails gracefully
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resume_no_segments_fails():
    """Resume without saved segments returns failed status."""
    session = _make_session(segments=None)

    with (
        patch("src.engine.pipeline.get_session", new_callable=AsyncMock, return_value=session),
        patch("src.engine.pipeline.update_session_status", new_callable=AsyncMock),
    ):
        result = await resume_after_clarification("sess-001", "context")

    assert result.status == "failed"
    assert "No saved segments" in result.error


# ---------------------------------------------------------------------------
# Test 6: Session not found -> fails gracefully
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_session_not_found():
    """Non-existent session returns failed status without crashing."""
    with patch("src.engine.pipeline.get_session", new_callable=AsyncMock, return_value=None):
        result = await process_session("nonexistent-id")

    assert result.status == "failed"
    assert "not found" in result.error
