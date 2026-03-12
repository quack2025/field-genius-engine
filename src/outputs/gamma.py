"""Gamma integration — Mode A: super prompt generator, Mode B: Gamma API direct."""

from __future__ import annotations

import json
import datetime
from typing import Any

import structlog

from src.config.settings import settings

logger = structlog.get_logger(__name__)


def build_gamma_prompt(
    reports: list[dict[str, Any]],
    session: dict[str, Any],
) -> str:
    """Mode A: Generate a structured super prompt for Gamma.

    This prompt can be pasted into Gamma to auto-generate a presentation.
    Always works — no API key needed.
    """
    user_name = session.get("user_name", "Ejecutivo")
    date_str = session.get("date", str(datetime.date.today()))
    num_visits = len(reports)

    sections: list[str] = []

    # Title slide
    sections.append(f"""# Reporte de Campo — {user_name}
**Fecha:** {date_str}
**Visitas realizadas:** {num_visits}
**Implementación:** Argos — Visitas de campo
""")

    # Executive summary
    visit_summaries = []
    alerts = []
    for r in reports:
        vtype = r.get("visit_type", "")
        location = r.get("inferred_location", "Sin ubicación")
        confidence = r.get("confidence_score", 0)
        visit_summaries.append(f"- **{location}** ({vtype}) — Confianza: {confidence:.0%}")

        # Collect alerts
        extracted = r.get("extracted_data", {})
        for cat_id, cat_data in extracted.items():
            if isinstance(cat_data, list):
                for item in cat_data:
                    if isinstance(item, dict) and item.get("alerta"):
                        alerts.append(f"⚠️ {item.get('marca', '')} — {item.get('actividad', '')}")

    sections.append(f"""## Resumen Ejecutivo

### Visitas del día
{chr(10).join(visit_summaries)}
""")

    if alerts:
        sections.append(f"""### Alertas detectadas
{chr(10).join(alerts)}
""")

    # Per-visit detail slides
    for i, report in enumerate(reports, 1):
        vtype = report.get("visit_type", "")
        location = report.get("inferred_location", "")
        extracted = report.get("extracted_data", {})

        sections.append(f"""## Visita {i}: {location}
**Tipo:** {vtype}
**Confianza:** {report.get('confidence_score', 0):.0%}
""")

        for cat_id, cat_data in extracted.items():
            if cat_id in ("confidence_score", "needs_clarification", "clarification_questions"):
                continue

            if isinstance(cat_data, dict):
                items_text = "\n".join(
                    f"  - **{k}:** {v}" for k, v in cat_data.items() if v
                )
                if items_text:
                    sections.append(f"### {cat_id.replace('_', ' ').title()}\n{items_text}\n")

            elif isinstance(cat_data, list) and cat_data:
                sections.append(f"### {cat_id.replace('_', ' ').title()}")
                for j, item in enumerate(cat_data, 1):
                    if isinstance(item, dict):
                        item_text = " | ".join(
                            f"**{k}:** {v}" for k, v in item.items() if v
                        )
                        sections.append(f"{j}. {item_text}")
                sections.append("")

    # Closing slide
    sections.append("""## Próximos pasos

Basado en los hallazgos del día, las acciones recomendadas se detallan en cada visita.
Revisar alertas de competencia y oportunidades de negocio identificadas.

---
*Generado automáticamente por Field Genius Engine — Genius Labs AI*
""")

    prompt = "\n".join(sections)

    logger.info(
        "gamma_prompt_built",
        visits=num_visits,
        length=len(prompt),
    )
    return prompt


async def create_presentation(
    reports: list[dict[str, Any]],
    session: dict[str, Any],
) -> dict[str, Any]:
    """Mode B: Call Gamma API to create a presentation directly.

    Falls back to Mode A (super prompt) if no API key or API fails.
    Returns {"mode": "api"|"prompt", "url": str|None, "prompt": str|None}
    """
    prompt = build_gamma_prompt(reports, session)

    # If no API key, return Mode A only
    if not settings.gamma_api_key:
        logger.info("gamma_mode_a", reason="no_api_key")
        return {"mode": "prompt", "url": None, "prompt": prompt}

    # Mode B: Try Gamma API
    try:
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://gamma.app/api/v1/presentations",
                headers={
                    "Authorization": f"Bearer {settings.gamma_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "content": prompt,
                    "title": f"Reporte de Campo — {session.get('user_name', '')} — {session.get('date', '')}",
                },
            )

            if response.status_code == 200:
                data = response.json()
                url = data.get("url", data.get("presentation_url"))
                logger.info("gamma_api_success", url=url)
                return {"mode": "api", "url": url, "prompt": prompt}
            else:
                logger.warning(
                    "gamma_api_failed",
                    status=response.status_code,
                    body=response.text[:200],
                )

    except Exception as e:
        logger.error("gamma_api_error", error=str(e))

    # Fallback to Mode A
    logger.info("gamma_fallback_to_prompt")
    return {"mode": "prompt", "url": None, "prompt": prompt}
