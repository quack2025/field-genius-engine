"""Analyzer — generates reports from captured field data using configurable frameworks.

Supports multiple report types (tactical, strategic, innovation) per implementation.
Each framework has its own system_prompt and sections that produce a structured markdown report.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from anthropic import AsyncAnthropic

from src.config.settings import settings

logger = structlog.get_logger(__name__)


def _build_observations_context(session: dict[str, Any]) -> str:
    """Build consolidated context from all media in a session.

    Merges pre-processed transcriptions, image descriptions, text notes,
    and location data from raw_files into a single text block.
    """
    raw_files: list[dict[str, Any]] = session.get("raw_files", [])
    parts: list[str] = []

    for f in sorted(raw_files, key=lambda x: x.get("timestamp", "")):
        ftype = f.get("type", "unknown")
        fname = f.get("filename", "")
        ts = f.get("timestamp", "")
        ts_short = ts[11:16] if len(ts) > 16 else ts  # HH:MM

        if ftype == "image":
            desc = f.get("image_description", "")
            if desc:
                parts.append(f"[Foto: {fname} | {ts_short}]\n{desc}")
            else:
                parts.append(f"[Foto: {fname} | {ts_short}] (sin descripcion)")

        elif ftype == "audio":
            text = f.get("transcription", "")
            if text:
                parts.append(f"[Audio: {fname} | {ts_short}]\n{text}")

        elif ftype == "video":
            text = f.get("transcription", "")
            desc = f.get("image_description", "")
            video_parts = []
            if text:
                video_parts.append(f"Transcripcion: {text}")
            if desc:
                video_parts.append(f"Frame: {desc}")
            if video_parts:
                parts.append(f"[Video: {fname} | {ts_short}]\n" + "\n".join(video_parts))

        elif ftype == "text":
            body = f.get("body", "")
            if body:
                parts.append(f"[Nota de texto | {ts_short}]\n{body}")

        elif ftype == "location":
            lat = f.get("latitude", "")
            lng = f.get("longitude", "")
            addr = f.get("address", "")
            label = f.get("label", "")
            loc = f"Lat: {lat}, Lng: {lng}"
            if addr:
                loc += f", {addr}"
            if label:
                loc += f" ({label})"
            parts.append(f"[Ubicacion GPS | {ts_short}]\n{loc}")

    return "\n\n".join(parts)


async def generate_report(
    session: dict[str, Any],
    report_type: str,
    framework_config: dict[str, Any],
    implementation_name: str = "",
) -> str | None:
    """Generate a report for a session using a specific framework type.

    Args:
        session: Full session dict with raw_files (including pre-processed descriptions)
        report_type: 'tactical' | 'strategic' | 'innovation'
        framework_config: The specific framework dict (from analysis_framework.frameworks[type])
        implementation_name: Client name for context

    Returns:
        Markdown report string, or None on failure.
    """
    start = time.time()
    framework_name = framework_config.get("name", report_type)
    model = framework_config.get("model", "claude-sonnet-4-20250514")
    system_prompt = framework_config.get("system_prompt", "")
    sections = framework_config.get("sections", [])

    # Also support legacy "dimensions" key (Babson format)
    if not sections:
        sections = framework_config.get("dimensions", [])

    logger.info(
        "report_generation_start",
        report_type=report_type,
        framework=framework_name,
        session_id=session.get("id"),
        sections=len(sections),
    )

    # Build observation context from all media
    observations_text = _build_observations_context(session)

    if not observations_text.strip():
        logger.warning("report_no_observations", session_id=session.get("id"))
        return None

    # Build section instructions
    section_instructions = []
    for sec in sections:
        section_instructions.append(f"## {sec.get('label', sec.get('id', ''))}\n{sec.get('prompt', '')}")
    sections_block = "\n\n".join(section_instructions)

    # Build the full prompt
    user_phone = session.get("user_phone", "")
    user_name = session.get("user_name", "")
    session_date = session.get("date", "")
    file_count = len(session.get("raw_files", []))

    prompt = f"""CONTEXTO DE LA SESION
- Operacion: {implementation_name}
- Ejecutivo: {user_name} ({user_phone})
- Fecha: {session_date}
- Archivos capturados: {file_count}

OBSERVACIONES DE CAMPO (descripcion de cada foto, transcripcion de audios, notas de texto):

{observations_text}

INSTRUCCIONES

Genera un reporte profesional de tipo "{framework_name}" basado en las observaciones de campo.
Para cada seccion, se especifico: cita evidencia concreta de las fotos y audios.
No seas generico — este reporte debe ser accionable.

{sections_block}

FORMATO: Responde en Markdown bien estructurado con headers ##, bullets, y **negritas** para hallazgos clave.
Incluye un resumen ejecutivo de 3-5 lineas al inicio del reporte."""

    try:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=180.0)
        message = await client.messages.create(
            model=model,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        report = message.content[0].text.strip()
        elapsed_ms = int((time.time() - start) * 1000)

        logger.info(
            "report_generation_complete",
            report_type=report_type,
            framework=framework_name,
            chars=len(report),
            elapsed_ms=elapsed_ms,
        )

        # Prepend header
        header = f"# {framework_name}\n"
        header += f"*{implementation_name} | {user_name} | {session_date} | {file_count} archivos*\n\n"

        return header + report

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error(
            "report_generation_failed",
            report_type=report_type,
            error=str(e),
            error_type=type(e).__name__,
            elapsed_ms=elapsed_ms,
        )
        return None


async def generate_all_reports(
    session: dict[str, Any],
    frameworks: dict[str, Any],
    implementation_name: str = "",
) -> dict[str, str | None]:
    """Generate all configured report types for a session.

    Args:
        session: Full session dict
        frameworks: The frameworks dict (analysis_framework.frameworks)
        implementation_name: Client name

    Returns:
        Dict mapping report_type → markdown (or None if failed)
    """
    import asyncio

    results: dict[str, str | None] = {}
    tasks = {}

    for report_type, config in frameworks.items():
        tasks[report_type] = generate_report(
            session=session,
            report_type=report_type,
            framework_config=config,
            implementation_name=implementation_name,
        )

    # Run all in parallel
    gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)

    for (report_type, _), result in zip(tasks.items(), gathered):
        if isinstance(result, Exception):
            logger.error("report_parallel_failed", report_type=report_type, error=str(result))
            results[report_type] = None
        else:
            results[report_type] = result

    return results
