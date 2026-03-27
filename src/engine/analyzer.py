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


# ── Structured Fact Extraction ──────────────────────────────────────


async def extract_facts(
    report_markdown: str,
    observations_text: str,
    framework_id: str,
    session_meta: dict[str, Any],
) -> dict[str, Any] | None:
    """Extract structured facts from a generated report using Haiku (fast/cheap).

    Called after generate_report() to produce queryable data for aggregation.
    Returns a dict with structured facts + key_quotes, or None on failure.
    """
    start = time.time()
    logger.info("fact_extraction_start", framework=framework_id, session_id=session_meta.get("id"))

    prompt = f"""Analiza este reporte de campo y las observaciones originales.
Extrae UNICAMENTE hechos concretos y verificables en formato JSON.

REPORTE:
{report_markdown[:6000]}

OBSERVACIONES ORIGINALES (resumidas):
{observations_text[:3000]}

METADATA:
- Ejecutivo: {session_meta.get("user_name", "")}
- Fecha: {session_meta.get("date", "")}
- Zona: {session_meta.get("zone", "no especificada")}

Responde UNICAMENTE con JSON valido con esta estructura:
{{
  "entities_mentioned": [
    {{"name": "nombre de marca/competidor/producto", "type": "competitor|brand|product|place", "count": N, "context": "breve contexto"}}
  ],
  "prices_detected": [
    {{"entity": "quien", "item": "que", "price": numero, "currency": "COP|CRC|USD", "is_promotion": true/false}}
  ],
  "alerts": [
    {{"type": "competitive_threat|churn_risk|opportunity|quality_issue", "severity": "high|medium|low", "description": "que pasa", "zone": "donde"}}
  ],
  "sentiment": {{"positive": N, "negative": N, "neutral": N}},
  "zones_covered": ["zona1", "zona2"],
  "key_themes": ["tema1", "tema2", "tema3"],
  "key_quotes": ["cita textual 1 del reporte que sea representativa", "cita 2", "cita 3"]
}}

Si no hay datos para una categoria, usa lista vacia []. No inventes datos."""

    try:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=60.0)
        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        # Parse JSON (handle markdown code blocks)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        facts = json.loads(raw)

        elapsed_ms = int((time.time() - start) * 1000)
        fact_count = (
            len(facts.get("entities_mentioned", []))
            + len(facts.get("prices_detected", []))
            + len(facts.get("alerts", []))
        )

        logger.info("fact_extraction_complete", framework=framework_id, fact_count=fact_count, elapsed_ms=elapsed_ms)
        return {
            "facts": facts,
            "key_quotes": facts.get("key_quotes", [])[:5],
            "fact_count": fact_count,
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error("fact_extraction_failed", framework=framework_id, error=str(e), elapsed_ms=elapsed_ms)
        return None


# ── Multi-Level Report Generation ───────────────────────────────────


async def generate_group_report(
    facts_rows: list[dict[str, Any]],
    framework_id: str,
    framework_config: dict[str, Any],
    group_name: str,
    date_range: str,
    implementation_name: str = "",
) -> str | None:
    """Generate a group-level report by aggregating structured facts from multiple sessions.

    Args:
        facts_rows: List of session_facts rows (each has .facts, .key_quotes, session metadata)
        framework_id: Which framework ('competidor', 'cliente', etc.)
        framework_config: The framework dict with system_prompt and sections
        group_name: Name of the group (e.g., "Zona San Jose")
        date_range: Human-readable date range
        implementation_name: Client name
    """
    start = time.time()
    session_count = len(facts_rows)
    framework_name = framework_config.get("name", framework_id)

    logger.info("group_report_start", framework=framework_id, group=group_name, sessions=session_count)

    # Aggregate facts with Python (not SQL, for flexibility)
    all_entities: dict[str, int] = {}
    all_alerts: list[dict] = []
    all_prices: list[dict] = []
    all_themes: dict[str, int] = {}
    all_quotes: list[str] = []
    sentiment_totals = {"positive": 0, "negative": 0, "neutral": 0}
    zones: set[str] = set()
    executives: set[str] = set()

    for row in facts_rows:
        facts = row.get("facts", {})
        executives.add(row.get("user_name", ""))

        for entity in facts.get("entities_mentioned", []):
            name = entity.get("name", "")
            all_entities[name] = all_entities.get(name, 0) + entity.get("count", 1)

        all_alerts.extend(facts.get("alerts", []))
        all_prices.extend(facts.get("prices_detected", []))

        for theme in facts.get("key_themes", []):
            all_themes[theme] = all_themes.get(theme, 0) + 1

        sent = facts.get("sentiment", {})
        for k in ("positive", "negative", "neutral"):
            sentiment_totals[k] += sent.get(k, 0)

        zones.update(facts.get("zones_covered", []))
        all_quotes.extend(row.get("key_quotes", [])[:2])  # Top 2 per session

    # Build aggregated context for Claude
    top_entities = sorted(all_entities.items(), key=lambda x: -x[1])[:15]
    top_themes = sorted(all_themes.items(), key=lambda x: -x[1])[:10]
    high_alerts = [a for a in all_alerts if a.get("severity") == "high"]
    sample_quotes = all_quotes[:10]

    aggregated = f"""DATOS AGREGADOS — {session_count} sesiones, {len(executives)} ejecutivos
Periodo: {date_range}
Zonas cubiertas: {', '.join(sorted(zones)) or 'No especificadas'}

ENTIDADES MAS MENCIONADAS:
{json.dumps(top_entities, ensure_ascii=False)}

TEMAS PRINCIPALES:
{json.dumps(top_themes, ensure_ascii=False)}

ALERTAS DE ALTA SEVERIDAD ({len(high_alerts)}):
{json.dumps(high_alerts[:10], ensure_ascii=False)}

PRECIOS DETECTADOS ({len(all_prices)} total):
{json.dumps(all_prices[:20], ensure_ascii=False)}

SENTIMIENTO AGREGADO: {json.dumps(sentiment_totals)}

CITAS REPRESENTATIVAS DEL EQUIPO:
{chr(10).join(f'- "{q}"' for q in sample_quotes)}"""

    # Build section instructions from framework
    sections = framework_config.get("sections", []) or framework_config.get("dimensions", [])
    section_instructions = []
    for sec in sections:
        section_instructions.append(f"## {sec.get('label', '')}\n{sec.get('prompt', '')}")

    prompt = f"""CONTEXTO
- Operacion: {implementation_name}
- Grupo: {group_name}
- Periodo: {date_range}
- Sesiones analizadas: {session_count}
- Ejecutivos: {len(executives)}

{aggregated}

INSTRUCCIONES

Genera un reporte consolidado de tipo "{framework_name}" para el grupo "{group_name}".
Este reporte sintetiza las observaciones de {session_count} sesiones de campo.
Identifica PATRONES, no casos individuales. Cita evidencia de las citas representativas.
Prioriza hallazgos accionables para el equipo de marketing/estrategia.

{"".join(section_instructions)}

FORMATO: Markdown profesional. Resumen ejecutivo de 5 lineas al inicio. Usa tablas para comparaciones."""

    try:
        system = framework_config.get("system_prompt", "")
        client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=180.0)
        message = await client.messages.create(
            model=framework_config.get("model", "claude-sonnet-4-20250514"),
            max_tokens=10000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )

        report = message.content[0].text.strip()
        elapsed_ms = int((time.time() - start) * 1000)

        logger.info("group_report_complete", framework=framework_id, group=group_name, chars=len(report), elapsed_ms=elapsed_ms)

        header = f"# {framework_name} — {group_name}\n"
        header += f"*{implementation_name} | {session_count} sesiones | {len(executives)} ejecutivos | {date_range}*\n\n"
        return header + report

    except Exception as e:
        logger.error("group_report_failed", error=str(e))
        return None


async def generate_project_report(
    group_reports: list[dict[str, Any]],
    framework_id: str,
    framework_config: dict[str, Any],
    implementation_name: str,
    date_range: str,
    total_sessions: int,
) -> str | None:
    """Generate a project-wide report from group-level reports.

    Args:
        group_reports: List of dicts with {group_name, report_markdown, session_count, fact_summary}
        framework_id: Which framework
        framework_config: Framework config
        implementation_name: Client name
        date_range: Period
        total_sessions: Total sessions across all groups
    """
    start = time.time()
    framework_name = framework_config.get("name", framework_id)

    logger.info("project_report_start", framework=framework_id, groups=len(group_reports), total_sessions=total_sessions)

    # Build group summaries (truncate each to ~2K chars to fit in context)
    group_blocks = []
    for gr in group_reports:
        md = gr.get("report_markdown", "")[:2500]
        group_blocks.append(
            f"### {gr['group_name']} ({gr.get('session_count', '?')} sesiones)\n{md}"
        )
    groups_text = "\n\n---\n\n".join(group_blocks)

    prompt = f"""CONTEXTO DEL PROYECTO
- Operacion: {implementation_name}
- Periodo: {date_range}
- Grupos analizados: {len(group_reports)}
- Total de sesiones: {total_sessions}

REPORTES POR GRUPO:

{groups_text}

INSTRUCCIONES

Genera un informe ejecutivo estrategico de tipo "{framework_name}" a nivel de PROYECTO COMPLETO.
Compara los diferentes grupos/zonas. Identifica:
1. Patrones que se repiten en TODOS los grupos (hallazgos universales)
2. Diferencias significativas ENTRE grupos (oportunidades localizadas)
3. Los 5 hallazgos mas importantes para la toma de decisiones
4. Plan de accion priorizado (quick wins + estrategico)

No repitas lo que ya dice cada grupo — sintetiza, compara, prioriza.

FORMATO: Markdown ejecutivo. Executive Summary de 5-7 lineas. Tablas comparativas entre grupos. Acciones con responsable y timeline."""

    try:
        system = framework_config.get("system_prompt", "")
        client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=180.0)
        message = await client.messages.create(
            model=framework_config.get("model", "claude-sonnet-4-20250514"),
            max_tokens=12000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )

        report = message.content[0].text.strip()
        elapsed_ms = int((time.time() - start) * 1000)

        logger.info("project_report_complete", framework=framework_id, chars=len(report), elapsed_ms=elapsed_ms)

        header = f"# {framework_name} — Informe Ejecutivo\n"
        header += f"*{implementation_name} | {len(group_reports)} grupos | {total_sessions} sesiones | {date_range}*\n\n"
        return header + report

    except Exception as e:
        logger.error("project_report_failed", error=str(e))
        return None
