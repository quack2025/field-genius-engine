"""Phase 3A — Segmentation accuracy evaluation against ground truth test cases.

This test suite evaluates the segmenter's ability to correctly identify visits
from a consolidated context (transcriptions + image descriptions).
It does NOT call real AI APIs — it mocks transcription/vision and only tests
the Claude segmentation call with simulated pre-processed context.

Metrics computed:
- Visit count accuracy (exact match)
- Visit type accuracy (% correct)
- File assignment accuracy (% correctly assigned)
- Clarification trigger accuracy (correct yes/no)
- False split rate (single visits incorrectly split)
- False merge rate (distinct visits incorrectly merged)

Usage:
    # Run with real Claude API (costs money, ~$0.50 per full run):
    EVAL_LIVE=1 pytest tests/test_segmentation_accuracy.py -v --tb=short

    # Run offline (mock mode, for CI):
    pytest tests/test_segmentation_accuracy.py -v
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.engine.segmenter import SegmentationResult, segment_session

LIVE_MODE = os.environ.get("EVAL_LIVE", "").strip() == "1"
TEST_CASES_PATH = Path(__file__).parent / "segmentation_test_cases.json"


@dataclass
class SegmentationScore:
    """Aggregated accuracy scores."""
    case_id: str
    visit_count_correct: bool = False
    visit_types_correct: int = 0
    visit_types_total: int = 0
    files_correct: int = 0
    files_total: int = 0
    clarification_correct: bool = False
    is_false_split: bool = False
    is_false_merge: bool = False
    details: str = ""


def _load_test_cases() -> list[dict]:
    with open(TEST_CASES_PATH) as f:
        data = json.load(f)
    return data["test_cases"]


def _build_mock_context(case: dict) -> str:
    """Build the consolidated context that the segmenter would normally build
    from transcriptions and image descriptions."""
    parts: list[str] = []
    for fname, text in case.get("simulated_transcriptions", {}).items():
        ts = ""
        for f in case.get("raw_files", []):
            if f.get("filename") == fname:
                ts = f.get("timestamp", "")
                break
        parts.append(f"[Audio: {fname} | {ts}]\n{text}\n")

    for fname, desc in case.get("simulated_image_descriptions", {}).items():
        ts = ""
        for f in case.get("raw_files", []):
            if f.get("filename") == fname:
                ts = f.get("timestamp", "")
                break
        parts.append(f"[Imagen: {fname} | {ts}]\n{desc}\n")

    return "\n".join(parts)


def _score_result(case: dict, result: SegmentationResult) -> SegmentationScore:
    """Compare actual segmentation result against expected ground truth."""
    expected = case["expected"]
    score = SegmentationScore(case_id=case["id"])

    # Visit count
    expected_count = expected["visit_count"]
    actual_count = len(result.visits)
    score.visit_count_correct = actual_count == expected_count

    # Clarification
    expected_clar = expected.get("needs_clarification", False)
    score.clarification_correct = result.needs_clarification == expected_clar

    # Visit type & file assignment (match by best overlap)
    expected_visits = expected.get("visits", [])
    score.visit_types_total = len(expected_visits)
    score.files_total = sum(len(v.get("files", [])) for v in expected_visits)

    matched_actual = set()
    for ev in expected_visits:
        best_match = None
        best_overlap = 0
        for i, av in enumerate(result.visits):
            if i in matched_actual:
                continue
            overlap = len(set(ev["files"]) & set(av.files))
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = i
        if best_match is not None:
            matched_actual.add(best_match)
            av = result.visits[best_match]
            # Type accuracy
            if av.visit_type == ev["visit_type"]:
                score.visit_types_correct += 1
            # File accuracy
            score.files_correct += len(set(ev["files"]) & set(av.files))

    # False split: expected 1 visit but got >1
    if expected_count == 1 and actual_count > 1:
        score.is_false_split = True

    # False merge: expected >1 visits but got fewer
    if expected_count > 1 and actual_count < expected_count:
        score.is_false_merge = True

    details = []
    if not score.visit_count_correct:
        details.append(f"count: expected={expected_count} got={actual_count}")
    if score.visit_types_correct < score.visit_types_total:
        details.append(f"types: {score.visit_types_correct}/{score.visit_types_total}")
    if score.files_correct < score.files_total:
        details.append(f"files: {score.files_correct}/{score.files_total}")
    score.details = "; ".join(details) if details else "OK"

    return score


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_cases():
    return _load_test_cases()


# ---------------------------------------------------------------------------
# Individual case tests (mock mode)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(LIVE_MODE, reason="Live mode runs full evaluation instead")
class TestSegmentationMock:
    """Unit tests using mock Claude responses to validate scoring logic."""

    @pytest.mark.asyncio
    async def test_empty_session_s08(self, test_cases):
        """S08: Empty session should return needs_clarification."""
        case = next(c for c in test_cases if c["id"] == "S08")
        session = {"id": "test-s08", "raw_files": case["raw_files"]}
        result = await segment_session(session, "argos")

        assert result.needs_clarification is True
        assert len(result.visits) == 0

    @pytest.mark.asyncio
    async def test_single_visit_s01(self, test_cases):
        """S01: Single ferreteria should produce 1 visit."""
        case = next(c for c in test_cases if c["id"] == "S01")
        session = {"id": "test-s01", "raw_files": case["raw_files"]}

        mock_response = json.dumps({
            "sessions": [{
                "id": "session-1",
                "inferred_location": "Ferreteria El Constructor, Laureles",
                "visit_type": "ferreteria",
                "confidence": 0.92,
                "files": ["img_001.jpg", "img_002.jpg", "audio_01.ogg"],
                "time_range": "10:15 - 10:20",
            }],
            "unassigned_files": [],
            "needs_clarification": False,
            "clarification_message": "",
        })

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=mock_response)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with (
            patch("src.engine.segmenter.transcribe", new_callable=AsyncMock,
                  return_value=case["simulated_transcriptions"].get("audio_01.ogg", "")),
            patch("src.engine.segmenter.analyze_from_storage", new_callable=AsyncMock,
                  side_effect=lambda path, **kw: case["simulated_image_descriptions"].get(
                      path.split("/")[-1], "")),
            patch("src.engine.segmenter.Anthropic", return_value=mock_client),
        ):
            result = await segment_session(session, "argos")

        score = _score_result(case, result)
        assert score.visit_count_correct
        assert score.visit_types_correct == 1
        assert score.clarification_correct


# ---------------------------------------------------------------------------
# Full evaluation (live mode)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not LIVE_MODE, reason="Set EVAL_LIVE=1 to run live evaluation")
class TestSegmentationLive:
    """Run all 10 test cases against the real Claude API and report accuracy."""

    @pytest.mark.asyncio
    async def test_full_evaluation(self, test_cases):
        """Evaluate all cases and print accuracy report."""
        scores: list[SegmentationScore] = []

        for case in test_cases:
            if case["id"] == "S08":
                # Empty session — no mock needed
                session = {"id": f"test-{case['id']}", "raw_files": []}
                result = await segment_session(session, "argos")
            else:
                # Build pre-processed context and mock transcription/vision
                session = {"id": f"test-{case['id']}", "raw_files": case["raw_files"]}

                async def mock_transcribe(path, case=case):
                    fname = path.split("/")[-1]
                    return case.get("simulated_transcriptions", {}).get(fname, "")

                async def mock_vision(path, **kw):
                    fname = path.split("/")[-1]
                    return case.get("simulated_image_descriptions", {}).get(fname, "")

                with (
                    patch("src.engine.segmenter.transcribe", side_effect=mock_transcribe),
                    patch("src.engine.segmenter.analyze_from_storage", side_effect=mock_vision),
                    patch("src.engine.segmenter.process_video", new_callable=AsyncMock,
                          return_value=MagicMock(audio_bytes=None, frames=[])),
                ):
                    result = await segment_session(session, "argos")

            score = _score_result(case, result)
            scores.append(score)

        # Print report
        print("\n" + "=" * 70)
        print("SEGMENTATION ACCURACY REPORT")
        print("=" * 70)

        total_count_correct = sum(1 for s in scores if s.visit_count_correct)
        total_types_correct = sum(s.visit_types_correct for s in scores)
        total_types_total = sum(s.visit_types_total for s in scores)
        total_files_correct = sum(s.files_correct for s in scores)
        total_files_total = sum(s.files_total for s in scores)
        total_clar_correct = sum(1 for s in scores if s.clarification_correct)
        false_splits = sum(1 for s in scores if s.is_false_split)
        false_merges = sum(1 for s in scores if s.is_false_merge)

        for s in scores:
            status = "PASS" if s.visit_count_correct and s.clarification_correct else "FAIL"
            print(f"  [{status}] {s.case_id}: {s.details}")

        print(f"\nVisit count accuracy:        {total_count_correct}/{len(scores)} ({total_count_correct/len(scores)*100:.0f}%)")
        print(f"Visit type accuracy:         {total_types_correct}/{total_types_total} ({total_types_correct/max(total_types_total,1)*100:.0f}%)")
        print(f"File assignment accuracy:    {total_files_correct}/{total_files_total} ({total_files_correct/max(total_files_total,1)*100:.0f}%)")
        print(f"Clarification accuracy:      {total_clar_correct}/{len(scores)} ({total_clar_correct/len(scores)*100:.0f}%)")
        print(f"False split rate:            {false_splits}/{len(scores)}")
        print(f"False merge rate:            {false_merges}/{len(scores)}")
        print("=" * 70)

        # Assertions — targets from the plan
        assert total_count_correct / len(scores) >= 0.7, f"Visit count accuracy {total_count_correct}/{len(scores)} below 70% target"
        assert total_files_correct / max(total_files_total, 1) >= 0.7, f"File assignment accuracy below 70% target"
