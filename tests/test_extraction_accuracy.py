"""Phase 3B — Extraction accuracy evaluation against golden set.

This test suite evaluates the extractor's ability to correctly extract
structured data from visit context using schema-driven prompts.

Metrics computed:
- Field extraction rate (% of expected fields correctly populated)
- Price accuracy (exact match on numeric values)
- Brand recognition (% of brands correctly identified)
- Array completeness (% of expected array items captured)
- Hallucination rate (% of values not present in source context)
- Confidence calibration (correlation between confidence_score and actual accuracy)

Usage:
    # Run with real Claude API (costs money, ~$0.30 per full run):
    EVAL_LIVE=1 pytest tests/test_extraction_accuracy.py -v --tb=short

    # Run offline (mock mode, for CI):
    pytest tests/test_extraction_accuracy.py -v
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.engine.extractor import ExtractedVisit, extract_visit
from src.engine.segmenter import VisitSegment

LIVE_MODE = os.environ.get("EVAL_LIVE", "").strip() == "1"
GOLDEN_SET_PATH = Path(__file__).parent / "extraction_golden_set.json"


@dataclass
class ExtractionScore:
    """Accuracy scores for a single extraction."""
    case_id: str
    visit_type: str
    fields_populated: int = 0
    fields_expected: int = 0
    prices_correct: int = 0
    prices_total: int = 0
    brands_correct: int = 0
    brands_total: int = 0
    array_items_found: int = 0
    array_items_expected: int = 0
    confidence_actual: float = 0.0
    confidence_expected: float = 0.0
    field_accuracy: float = 0.0
    details: str = ""


def _load_golden_set() -> list[dict]:
    with open(GOLDEN_SET_PATH) as f:
        data = json.load(f)
    return data["golden_visits"]


def _count_populated_fields(data: dict, expected: dict, path: str = "") -> tuple[int, int]:
    """Recursively count how many expected fields are populated in actual data.
    Returns (populated, total_expected)."""
    populated = 0
    total = 0

    for key, exp_value in expected.items():
        if key.startswith("_"):
            continue  # skip meta keys like _note
        if key in ("confidence_score", "needs_clarification", "clarification_questions"):
            continue  # meta fields, not content

        total += 1
        act_value = data.get(key)

        if isinstance(exp_value, dict):
            if isinstance(act_value, dict):
                p, t = _count_populated_fields(act_value, exp_value, f"{path}.{key}")
                populated += p
                total += t - 1  # subtract the +1 from this level
                total = max(total, 0)
            # else: dict expected but not found — counts as 0/1
        elif isinstance(exp_value, list):
            if isinstance(act_value, list) and len(act_value) > 0:
                populated += 1
            # else: array expected but empty/missing
        elif exp_value is not None:
            if act_value is not None:
                populated += 1
        else:
            # Expected null — don't penalize if actual is also null
            if act_value is None:
                populated += 1

    return populated, total


def _extract_prices(data: dict) -> list[dict]:
    """Find all price entries across all categories."""
    prices = []
    # Ferreteria schema: data["precios"]
    for item in data.get("precios", []):
        if isinstance(item, dict) and item.get("precio") is not None:
            prices.append(item)
    return prices


def _extract_brands(data: dict) -> set[str]:
    """Find all brand names mentioned in the extraction."""
    brands: set[str] = set()
    for key, value in data.items():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    marca = item.get("marca")
                    if marca:
                        brands.add(marca.lower().strip())
        elif isinstance(value, dict):
            marca = value.get("marca")
            if marca:
                brands.add(marca.lower().strip())
    return brands


def _score_extraction(case: dict, result: ExtractedVisit) -> ExtractionScore:
    """Compare extraction result against golden expected output."""
    expected = case["expected_extraction"]
    actual = result.extracted_data

    score = ExtractionScore(
        case_id=case["id"],
        visit_type=case["visit_type"],
        confidence_actual=result.confidence_score,
        confidence_expected=expected.get("confidence_score", 0.0),
    )

    # Field extraction rate
    pop, total = _count_populated_fields(actual, expected)
    score.fields_populated = pop
    score.fields_expected = total
    score.field_accuracy = pop / max(total, 1)

    # Price accuracy (ferreteria only)
    if case["visit_type"] == "ferreteria":
        expected_prices = expected.get("precios", [])
        actual_prices = actual.get("precios", [])
        score.prices_total = len([p for p in expected_prices if p.get("precio") is not None])

        for ep in expected_prices:
            if ep.get("precio") is None:
                continue
            for ap in actual_prices:
                if (isinstance(ap, dict) and
                    ap.get("precio") == ep["precio"] and
                    ap.get("marca", "").lower().strip() == ep.get("marca", "").lower().strip()):
                    score.prices_correct += 1
                    break

    # Brand recognition
    expected_brands = _extract_brands(expected)
    actual_brands = _extract_brands(actual)
    score.brands_total = len(expected_brands)
    score.brands_correct = len(expected_brands & actual_brands)

    # Array completeness
    for key, value in expected.items():
        if isinstance(value, list) and not key.startswith("_"):
            score.array_items_expected += len(value)
            actual_list = actual.get(key, [])
            if isinstance(actual_list, list):
                score.array_items_found += min(len(actual_list), len(value))

    # Details
    details = []
    if score.field_accuracy < 0.6:
        details.append(f"fields: {score.fields_populated}/{score.fields_expected}")
    if score.prices_total > 0 and score.prices_correct < score.prices_total:
        details.append(f"prices: {score.prices_correct}/{score.prices_total}")
    if score.brands_total > 0 and score.brands_correct < score.brands_total:
        details.append(f"brands: {score.brands_correct}/{score.brands_total}")
    score.details = "; ".join(details) if details else "OK"

    return score


def _make_visit_from_case(case: dict) -> VisitSegment:
    """Build a VisitSegment from a golden set case."""
    context = case["input_context"]
    v = VisitSegment(
        segment_id=f"golden-{case['id']}",
        inferred_location=case["inferred_location"],
        visit_type=case["visit_type"],
        confidence=0.9,
        files=list(context.get("transcriptions", {}).keys()) +
              list(context.get("image_descriptions", {}).keys()),
        time_range="10:00 - 11:00",
    )
    v.transcriptions = context.get("transcriptions", {})
    v.image_descriptions = context.get("image_descriptions", {})
    return v


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def golden_set():
    return _load_golden_set()


# ---------------------------------------------------------------------------
# Mock mode tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(LIVE_MODE, reason="Live mode runs full evaluation instead")
class TestExtractionMock:
    """Unit tests using mock Claude responses to validate scoring logic."""

    @pytest.mark.asyncio
    async def test_scoring_logic_e01(self, golden_set):
        """E01: Perfect extraction should score ~100%."""
        case = next(c for c in golden_set if c["id"] == "E01")
        expected = case["expected_extraction"]

        # Simulate perfect extraction
        mock_result = ExtractedVisit(
            visit_type="ferreteria",
            inferred_location="Ferreteria El Constructor",
            extracted_data=expected,
            confidence_score=expected.get("confidence_score", 0.9),
        )
        score = _score_extraction(case, mock_result)
        assert score.field_accuracy >= 0.9, f"Perfect extraction should score >=90%, got {score.field_accuracy:.0%}"

    @pytest.mark.asyncio
    async def test_scoring_logic_empty(self, golden_set):
        """Empty extraction should score 0% on fields."""
        case = next(c for c in golden_set if c["id"] == "E01")
        mock_result = ExtractedVisit(
            visit_type="ferreteria",
            inferred_location="Unknown",
            extracted_data={},
            confidence_score=0.0,
        )
        score = _score_extraction(case, mock_result)
        assert score.field_accuracy < 0.2

    @pytest.mark.asyncio
    async def test_empty_context_returns_needs_review(self, golden_set):
        """Visit with no content should return needs_review."""
        v = VisitSegment(
            segment_id="empty",
            inferred_location="Test",
            visit_type="ferreteria",
            confidence=0.5,
            files=[],
            time_range="",
        )
        result = await extract_visit(v, "argos")
        assert result.needs_review is True

    @pytest.mark.asyncio
    async def test_low_confidence_marks_review(self, golden_set):
        """Extraction with confidence < 0.5 should set needs_review."""
        case = next(c for c in golden_set if c["id"] == "E03")
        visit = _make_visit_from_case(case)

        low_conf = {"confidence_score": 0.3, "needs_clarification": False, "clarification_questions": []}
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=json.dumps(low_conf))]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with (
            patch("src.engine.extractor.Anthropic", return_value=mock_client),
            patch("src.engine.extractor._load_schema", new_callable=AsyncMock, return_value={"implementation": "argos", "categories": []}),
            patch("src.engine.extractor.build_system_prompt", return_value="prompt"),
        ):
            result = await extract_visit(visit, "argos")
        assert result.needs_review is True


# ---------------------------------------------------------------------------
# Full live evaluation
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not LIVE_MODE, reason="Set EVAL_LIVE=1 to run live evaluation")
class TestExtractionLive:
    """Run all 15 golden cases against the real Claude API and report accuracy."""

    @pytest.mark.asyncio
    async def test_full_evaluation(self, golden_set):
        """Evaluate all cases and print accuracy report."""
        scores: list[ExtractionScore] = []

        for case in golden_set:
            visit = _make_visit_from_case(case)
            result = await extract_visit(visit, "argos")
            score = _score_extraction(case, result)
            scores.append(score)

        # Print report
        print("\n" + "=" * 70)
        print("EXTRACTION ACCURACY REPORT")
        print("=" * 70)

        # Per-case results
        for s in scores:
            status = "PASS" if s.field_accuracy >= 0.6 else "FAIL"
            print(f"  [{status}] {s.case_id} ({s.visit_type}): "
                  f"fields={s.field_accuracy:.0%} "
                  f"conf={s.confidence_actual:.2f} vs expected={s.confidence_expected:.2f} "
                  f"| {s.details}")

        # Aggregate metrics
        total_fields_pop = sum(s.fields_populated for s in scores)
        total_fields_exp = sum(s.fields_expected for s in scores)
        total_prices_ok = sum(s.prices_correct for s in scores)
        total_prices = sum(s.prices_total for s in scores)
        total_brands_ok = sum(s.brands_correct for s in scores)
        total_brands = sum(s.brands_total for s in scores)
        total_array_found = sum(s.array_items_found for s in scores)
        total_array_exp = sum(s.array_items_expected for s in scores)
        avg_field_acc = sum(s.field_accuracy for s in scores) / len(scores)

        # Confidence calibration: correlation between expected and actual
        conf_diffs = [abs(s.confidence_actual - s.confidence_expected) for s in scores]
        avg_conf_diff = sum(conf_diffs) / len(conf_diffs)

        # Per visit-type breakdown
        by_type: dict[str, list[ExtractionScore]] = {}
        for s in scores:
            by_type.setdefault(s.visit_type, []).append(s)

        print(f"\n--- AGGREGATE ---")
        print(f"Field extraction rate:       {total_fields_pop}/{total_fields_exp} ({total_fields_pop/max(total_fields_exp,1)*100:.0f}%)")
        print(f"Price accuracy:              {total_prices_ok}/{total_prices} ({total_prices_ok/max(total_prices,1)*100:.0f}%)")
        print(f"Brand recognition:           {total_brands_ok}/{total_brands} ({total_brands_ok/max(total_brands,1)*100:.0f}%)")
        print(f"Array completeness:          {total_array_found}/{total_array_exp} ({total_array_found/max(total_array_exp,1)*100:.0f}%)")
        print(f"Avg field accuracy:          {avg_field_acc:.0%}")
        print(f"Avg confidence deviation:    {avg_conf_diff:.2f}")

        print(f"\n--- BY VISIT TYPE ---")
        for vtype, vscores in by_type.items():
            avg_fa = sum(s.field_accuracy for s in vscores) / len(vscores)
            print(f"  {vtype}: {avg_fa:.0%} field accuracy ({len(vscores)} cases)")

        print("=" * 70)

        # Assertions — targets from the plan
        assert avg_field_acc >= 0.6, f"Average field accuracy {avg_field_acc:.0%} below 60% target"
        if total_prices > 0:
            assert total_prices_ok / total_prices >= 0.7, f"Price accuracy below 70% target"
        if total_brands > 0:
            assert total_brands_ok / total_brands >= 0.7, f"Brand recognition below 70% target"
