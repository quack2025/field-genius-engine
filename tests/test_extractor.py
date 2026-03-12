"""Tests for src.engine.extractor — extract_visit and ExtractedVisit dataclass."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.engine.segmenter import VisitSegment
from src.engine.extractor import ExtractedVisit, extract_visit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_visit(
    visit_type: str = "ferreteria",
    has_content: bool = True,
) -> VisitSegment:
    v = VisitSegment(
        segment_id="seg-1",
        inferred_location="Ferreteria El Constructor",
        visit_type=visit_type,
        confidence=0.92,
        files=["img_001.jpg", "audio_01.ogg"],
        time_range="10:15 - 10:52",
    )
    if has_content:
        v.transcriptions = {"audio_01.ogg": "Cemento Argos 50kg a 32000 pesos"}
        v.image_descriptions = {"img_001.jpg": "Estante con bolsas de cemento Argos"}
    return v


EXTRACTION_JSON = json.dumps({
    "precios": [{"producto": "Cemento Gris 50kg", "marca": "Argos", "precio": 32000}],
    "share_of_shelf": {"argos_facing": "alto"},
    "confidence_score": 0.88,
    "needs_clarification": False,
    "clarification_questions": [],
})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_visit_success():
    """Happy path: extraction returns structured data with confidence score."""
    visit = _make_visit()

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=EXTRACTION_JSON)]

    mock_anthropic_instance = MagicMock()
    mock_anthropic_instance.messages.create.return_value = mock_message

    with (
        patch("src.engine.extractor.Anthropic", return_value=mock_anthropic_instance),
        patch("src.engine.extractor._load_schema", return_value={"implementation": "argos"}),
        patch("src.engine.extractor.build_system_prompt", return_value="System prompt"),
    ):
        result = await extract_visit(visit, "argos")

    assert isinstance(result, ExtractedVisit)
    assert result.confidence_score == 0.88
    assert result.needs_review is False
    assert result.visit_type == "ferreteria"
    assert "precios" in result.extracted_data


@pytest.mark.asyncio
async def test_extract_visit_empty_context():
    """Visit with no transcriptions or images returns needs_review."""
    visit = _make_visit(has_content=False)

    result = await extract_visit(visit, "argos")

    assert result.needs_review is True
    assert result.extracted_data == {}


@pytest.mark.asyncio
async def test_extract_visit_low_confidence():
    """Low confidence score triggers needs_review."""
    visit = _make_visit()

    low_conf_json = json.dumps({
        "precios": [],
        "confidence_score": 0.3,
        "needs_clarification": False,
        "clarification_questions": [],
    })

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=low_conf_json)]

    mock_anthropic_instance = MagicMock()
    mock_anthropic_instance.messages.create.return_value = mock_message

    with (
        patch("src.engine.extractor.Anthropic", return_value=mock_anthropic_instance),
        patch("src.engine.extractor._load_schema", return_value={}),
        patch("src.engine.extractor.build_system_prompt", return_value="System prompt"),
    ):
        result = await extract_visit(visit, "argos")

    assert result.confidence_score == 0.3
    assert result.needs_review is True  # confidence < 0.5


@pytest.mark.asyncio
async def test_extract_visit_claude_failure():
    """Claude API error returns needs_review with empty data."""
    visit = _make_visit()

    mock_anthropic_instance = MagicMock()
    mock_anthropic_instance.messages.create.side_effect = Exception("API rate limit")

    with (
        patch("src.engine.extractor.Anthropic", return_value=mock_anthropic_instance),
        patch("src.engine.extractor._load_schema", return_value={}),
        patch("src.engine.extractor.build_system_prompt", return_value="System prompt"),
    ):
        result = await extract_visit(visit, "argos")

    assert result.needs_review is True
    assert result.extracted_data == {}


def test_extracted_visit_dataclass_defaults():
    """ExtractedVisit defaults are correct."""
    e = ExtractedVisit(visit_type="ferreteria", inferred_location="Test")
    assert e.extracted_data == {}
    assert e.confidence_score == 0.0
    assert e.needs_review is False
    assert e.clarification_questions == []
