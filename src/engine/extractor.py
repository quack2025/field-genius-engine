"""Extractor — Phase 2: structured data extraction per visit using schema-driven prompts."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import structlog
from anthropic import Anthropic

from src.config.settings import settings
from src.engine.schema_builder import build_system_prompt
from src.engine.segmenter import VisitSegment

logger = structlog.get_logger(__name__)


@dataclass
class ExtractedVisit:
    """Result of extraction for a single visit."""
    visit_type: str
    inferred_location: str
    extracted_data: dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0
    needs_review: bool = False
    needs_clarification: bool = False
    clarification_questions: list[str] = field(default_factory=list)
    elapsed_ms: int = 0


async def _load_schema(visit_type: str, implementation: str = "") -> dict[str, Any]:
    """Load the JSON schema for a visit type via ConfigLoader (DB-first, file-fallback)."""
    from src.engine.config_loader import get_visit_type_schema
    return await get_visit_type_schema(implementation, visit_type)


async def extract_visit(
    visit: VisitSegment,
    implementation: str = "",
) -> ExtractedVisit:
    """Extract structured data from a visit segment using the appropriate schema.

    Steps:
    1. Load schema for visit_type
    2. Generate system prompt via schema_builder
    3. Build visit context from transcriptions + image descriptions
    4. Call Claude Haiku for fast extraction
    5. Parse and validate JSON response
    """
    start = time.time()
    logger.info(
        "extractor_start",
        visit_type=visit.visit_type,
        location=visit.inferred_location,
        files=len(visit.files),
    )

    # Step 1: Load schema
    schema = await _load_schema(visit.visit_type, implementation)

    # Step 2: Generate system prompt
    system_prompt = build_system_prompt(schema)

    # Step 3: Build visit context
    context_parts: list[str] = []

    if visit.transcriptions:
        context_parts.append("## Transcripciones de audio")
        for fname, text in visit.transcriptions.items():
            context_parts.append(f"**{fname}:** {text}")

    if visit.image_descriptions:
        context_parts.append("\n## Observaciones de fotos")
        for fname, desc in visit.image_descriptions.items():
            context_parts.append(f"**{fname}:** {desc}")

    if visit.text_notes:
        context_parts.append("\n## Notas de texto")
        for note in visit.text_notes:
            context_parts.append(f"- {note}")

    visit_context = "\n".join(context_parts)

    if not visit_context.strip():
        logger.warning("extractor_empty_context", visit_type=visit.visit_type)
        return ExtractedVisit(
            visit_type=visit.visit_type,
            inferred_location=visit.inferred_location,
            needs_review=True,
            elapsed_ms=int((time.time() - start) * 1000),
        )

    # Step 4: Call Claude Haiku
    user_message = f"""Ubicación inferida: {visit.inferred_location}
Tipo de visita: {visit.visit_type}
Archivos analizados: {', '.join(visit.files)}

{visit_context}"""

    extracted_data = await _call_claude_extraction(system_prompt, user_message)

    # Step 5: Validate
    if extracted_data is None:
        return ExtractedVisit(
            visit_type=visit.visit_type,
            inferred_location=visit.inferred_location,
            needs_review=True,
            elapsed_ms=int((time.time() - start) * 1000),
        )

    confidence = extracted_data.get("confidence_score", 0.0)
    needs_clarification = extracted_data.get("needs_clarification", False)
    clarification_qs = extracted_data.get("clarification_questions", [])

    elapsed_ms = int((time.time() - start) * 1000)

    result = ExtractedVisit(
        visit_type=visit.visit_type,
        inferred_location=visit.inferred_location,
        extracted_data=extracted_data,
        confidence_score=confidence,
        needs_review=confidence < 0.5,
        needs_clarification=needs_clarification,
        clarification_questions=clarification_qs,
        elapsed_ms=elapsed_ms,
    )

    logger.info(
        "extractor_complete",
        visit_type=visit.visit_type,
        confidence=confidence,
        needs_review=result.needs_review,
        elapsed_ms=elapsed_ms,
    )

    return result


async def _call_claude_extraction(
    system_prompt: str,
    user_message: str,
    retry: bool = True,
) -> dict[str, Any] | None:
    """Call Claude Haiku for extraction and parse JSON response. Retry once on failure."""
    try:
        client = Anthropic(api_key=settings.anthropic_api_key, timeout=90.0)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        response_text = message.content[0].text.strip()

        # Parse JSON — handle markdown wrapping
        json_text = response_text
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()

        return json.loads(json_text)

    except json.JSONDecodeError:
        if retry:
            logger.warning("extractor_json_retry", response=response_text[:200])
            # Retry with explicit correction instruction
            correction_msg = (
                f"{user_message}\n\n"
                "IMPORTANTE: Tu respuesta anterior no fue JSON válido. "
                "Responde ÚNICAMENTE con el JSON, sin texto adicional ni markdown."
            )
            return await _call_claude_extraction(system_prompt, correction_msg, retry=False)
        else:
            logger.error("extractor_json_failed_final", response=response_text[:200])
            return None

    except Exception as e:
        logger.error("extractor_claude_failed", error=str(e))
        return None
