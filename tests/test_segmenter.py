"""Tests for src.engine.segmenter — segment_session and VisitSegment dataclass."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.engine.segmenter import (
    SegmentationResult,
    VisitSegment,
    segment_session,
    _find_timestamp,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_session(raw_files: list | None = None) -> dict:
    return {
        "id": "sess-001",
        "user_phone": "+573001234567",
        "raw_files": raw_files or [],
    }


CLAUDE_SINGLE_VISIT_JSON = json.dumps({
    "sessions": [
        {
            "id": "session-1",
            "inferred_location": "Ferreteria El Constructor",
            "visit_type": "ferreteria",
            "confidence": 0.92,
            "files": ["img_001.jpg", "audio_01.ogg"],
            "time_range": "10:15 - 10:52",
        }
    ],
    "unassigned_files": [],
    "needs_clarification": False,
    "clarification_message": "",
})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_segment_empty_session():
    """Session with no processable files returns needs_clarification."""
    session = _make_session(raw_files=[])

    result = await segment_session(session)

    assert isinstance(result, SegmentationResult)
    assert result.needs_clarification is True
    assert result.visits == []


@pytest.mark.asyncio
async def test_segment_single_audio_visit():
    """One audio file transcribed, Claude returns single visit."""
    session = _make_session(raw_files=[
        {"filename": "audio_01.ogg", "type": "audio", "storage_path": "media/audio_01.ogg", "timestamp": "10:15"},
    ])

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=CLAUDE_SINGLE_VISIT_JSON)]

    mock_anthropic_instance = MagicMock()
    mock_anthropic_instance.messages.create.return_value = mock_message

    with (
        patch("src.engine.segmenter.transcribe", new_callable=AsyncMock, return_value="Cemento Argos a 32mil"),
        patch("src.engine.segmenter.Anthropic", return_value=mock_anthropic_instance),
    ):
        result = await segment_session(session)

    assert result.needs_clarification is False
    assert len(result.visits) == 1
    assert result.visits[0].visit_type == "ferreteria"
    assert result.visits[0].inferred_location == "Ferreteria El Constructor"
    assert "audio_01.ogg" in result.visits[0].transcriptions


@pytest.mark.asyncio
async def test_segment_image_only():
    """One image file analyzed, Claude returns single visit."""
    session = _make_session(raw_files=[
        {"filename": "img_001.jpg", "type": "image", "storage_path": "media/img_001.jpg", "timestamp": "10:20"},
    ])

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=CLAUDE_SINGLE_VISIT_JSON)]

    mock_anthropic_instance = MagicMock()
    mock_anthropic_instance.messages.create.return_value = mock_message

    with (
        patch("src.engine.segmenter.analyze_from_storage", new_callable=AsyncMock, return_value="Estante de cemento"),
        patch("src.engine.segmenter.Anthropic", return_value=mock_anthropic_instance),
    ):
        result = await segment_session(session)

    assert len(result.visits) == 1
    assert "img_001.jpg" in result.visits[0].image_descriptions


def test_find_timestamp():
    """_find_timestamp returns correct timestamp for a filename."""
    files = [
        {"filename": "a.jpg", "timestamp": "09:00"},
        {"filename": "b.ogg", "timestamp": "10:30"},
    ]
    assert _find_timestamp(files, "b.ogg") == "10:30"
    assert _find_timestamp(files, "missing.txt") == ""


def test_visit_segment_dataclass():
    """VisitSegment defaults are correct."""
    v = VisitSegment(
        segment_id="s1",
        inferred_location="Test",
        visit_type="ferreteria",
        confidence=0.9,
        files=["a.jpg"],
        time_range="10:00 - 11:00",
    )
    assert v.transcriptions == {}
    assert v.image_descriptions == {}
    assert v.text_notes == []


def test_segmentation_result_dataclass():
    """SegmentationResult defaults are correct."""
    r = SegmentationResult()
    assert r.visits == []
    assert r.needs_clarification is False
    assert r.elapsed_ms == 0
