"""Analyzer — Phase 3: strategic analysis per visit using configurable frameworks."""

from __future__ import annotations

import time
from typing import Any

import structlog
from anthropic import AsyncAnthropic

from src.config.settings import settings

logger = structlog.get_logger(__name__)


async def analyze_visit(
    extracted_data: dict[str, Any],
    image_descriptions: dict[str, str],
    visit_location: str,
    visit_type: str,
    framework: dict[str, Any],
    implementation_name: str = "",
) -> str | None:
    """Run strategic analysis on a single visit using the configured framework.

    Args:
        extracted_data: Structured data from Phase 2 extraction
        image_descriptions: Raw vision descriptions per image (from Phase 1)
        visit_location: Inferred location name
        visit_type: Visit type slug
        framework: Analysis framework config (e.g., Babson Pentagon)
        implementation_name: Client/implementation name for context

    Returns:
        Markdown string with the full strategic analysis, or None on failure.
    """
    start = time.time()
    framework_name = framework.get("name", "Strategic Analysis")
    model = framework.get("model", "claude-sonnet-4-20250514")
    dimensions = framework.get("dimensions", [])

    logger.info(
        "analyzer_start",
        framework=framework_name,
        location=visit_location,
        dimensions=len(dimensions),
    )

    # Build the observation context from image descriptions
    observations = []
    for fname, desc in image_descriptions.items():
        observations.append(f"**{fname}:**\n{desc}")
    observations_text = "\n\n".join(observations)

    # Build extracted data summary
    import json
    extracted_summary = json.dumps(extracted_data, ensure_ascii=False, indent=2)

    # Single prompt with all dimensions (more coherent than per-dimension calls)
    dimension_instructions = []
    for dim in dimensions:
        dimension_instructions.append(
            f"## {dim['label']}\n{dim['prompt']}"
        )
    dimensions_block = "\n\n".join(dimension_instructions)

    closing_prompt = framework.get("closing_prompt", "")

    prompt = f"""Eres un consultor senior de retail y trade marketing, experto en el marco analítico "{framework_name}".

CONTEXTO DE LA VISITA
- Punto de venta: {visit_location}
- Tipo de visita: {visit_type}
- Cliente/operación: {implementation_name}

OBSERVACIONES DE CAMPO (descripción de cada foto capturada):

{observations_text}

DATOS ESTRUCTURADOS EXTRAÍDOS:

{extracted_summary}

INSTRUCCIONES

Realiza un análisis estratégico profesional de este punto de venta usando el {framework_name}.
Para cada dimensión, sé específico: cita evidencia concreta de las fotos y datos.
No seas genérico — este análisis debe ser accionable para un gerente de trade marketing.

{dimensions_block}

## Gold Insight Estratégico
{closing_prompt}

FORMATO: Responde en Markdown bien estructurado con headers ##, bullets, y **negritas** para hallazgos clave. Incluye un resumen ejecutivo de 3-4 líneas al inicio."""

    try:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=180.0)
        message = await client.messages.create(
            model=model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )

        analysis = message.content[0].text.strip()
        elapsed_ms = int((time.time() - start) * 1000)

        logger.info(
            "analyzer_complete",
            framework=framework_name,
            location=visit_location,
            chars=len(analysis),
            elapsed_ms=elapsed_ms,
        )

        # Prepend header
        header = f"# Análisis Estratégico — {visit_location}\n"
        header += f"*Framework: {framework_name} | Tipo: {visit_type}*\n\n"

        return header + analysis

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error(
            "analyzer_failed",
            error=str(e),
            error_type=type(e).__name__,
            elapsed_ms=elapsed_ms,
        )
        return None


async def consolidate_analyses(
    visit_analyses: list[dict[str, Any]],
    framework: dict[str, Any],
    implementation_name: str = "",
) -> str | None:
    """Consolidate multiple per-visit analyses into a unified strategic report.

    Args:
        visit_analyses: List of dicts with keys: location, visit_type, analysis_markdown, date, executive
        framework: Analysis framework config (must have consolidation_prompt)
        implementation_name: Client name for context

    Returns:
        Markdown string with the consolidated report, or None on failure.
    """
    start = time.time()
    framework_name = framework.get("name", "Strategic Analysis")
    model = framework.get("model", "claude-sonnet-4-20250514")
    consolidation_template = framework.get("consolidation_prompt", "")

    if not consolidation_template:
        logger.warning("analyzer_no_consolidation_prompt")
        return None

    logger.info(
        "consolidation_start",
        framework=framework_name,
        visit_count=len(visit_analyses),
    )

    # Build the individual analyses block
    analyses_block = []
    for i, va in enumerate(visit_analyses, 1):
        header = f"### Visita {i}: {va.get('location', 'Desconocido')}"
        header += f"\n*Tipo: {va.get('visit_type', '')} | Fecha: {va.get('date', '')} | Ejecutivo: {va.get('executive', '')}*"
        analyses_block.append(f"{header}\n\n{va.get('analysis_markdown', 'Sin análisis disponible')}")

    all_analyses = "\n\n---\n\n".join(analyses_block)

    # Build consolidation prompt
    system_prompt = consolidation_template.replace(
        "{visit_count}", str(len(visit_analyses))
    )

    prompt = f"""OPERACIÓN: {implementation_name}
NÚMERO DE VISITAS: {len(visit_analyses)}
MARCO ANALÍTICO: {framework_name}

ANÁLISIS INDIVIDUALES POR VISITA:

{all_analyses}

---

Genera el reporte ejecutivo consolidado. Estructura:

1. **Executive Summary** (5-7 líneas con los hallazgos más importantes)
2. **Análisis por dimensión del {framework_name}** — para cada dimensión, sintetiza patrones, variaciones, y benchmarks internos
3. **Mapa de Oportunidades** — las 5 oportunidades estratégicas más importantes, priorizadas por impacto
4. **Plan de Acción** — acciones concretas para las próximas 2 semanas
5. **Métricas sugeridas** — KPIs para medir el impacto de las acciones

FORMATO: Markdown profesional con headers, tablas donde aplique, y bullets accionables."""

    try:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=300.0)
        message = await client.messages.create(
            model=model,
            max_tokens=12000,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        report = message.content[0].text.strip()
        elapsed_ms = int((time.time() - start) * 1000)

        logger.info(
            "consolidation_complete",
            chars=len(report),
            visits=len(visit_analyses),
            elapsed_ms=elapsed_ms,
        )

        header = f"# Reporte Consolidado — {implementation_name}\n"
        header += f"*{len(visit_analyses)} visitas analizadas | Framework: {framework_name}*\n\n"

        return header + report

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error(
            "consolidation_failed",
            error=str(e),
            error_type=type(e).__name__,
            elapsed_ms=elapsed_ms,
        )
        return None
