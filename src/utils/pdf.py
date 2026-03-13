"""PDF report generator — WeasyPrint with HTML template for field reports."""

from __future__ import annotations

import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def _build_html(
    reports: list[dict[str, Any]],
    session: dict[str, Any],
) -> str:
    """Build HTML for the field report PDF."""
    user_name = session.get("user_name", "Ejecutivo")
    date_str = session.get("date", str(datetime.date.today()))

    # Collect alerts across all visits
    all_alerts: list[str] = []
    for r in reports:
        extracted = r.get("extracted_data", {})
        for cat_data in extracted.values():
            if isinstance(cat_data, list):
                for item in cat_data:
                    if isinstance(item, dict) and item.get("alerta"):
                        all_alerts.append(
                            f"{item.get('marca', '?')} — {item.get('actividad', '?')}"
                        )

    # Build visit sections
    visit_sections = ""
    for i, report in enumerate(reports, 1):
        location = report.get("inferred_location", "Sin ubicación")
        vtype = report.get("visit_type", "")
        confidence = report.get("confidence_score", 0)
        extracted = report.get("extracted_data", {})

        categories_html = ""
        for cat_id, cat_data in extracted.items():
            if cat_id in ("confidence_score", "needs_clarification", "clarification_questions"):
                continue

            cat_label = cat_id.replace("_", " ").title()

            if isinstance(cat_data, dict) and any(v for v in cat_data.values()):
                rows = "".join(
                    f"<tr><td class='field-name'>{k}</td><td>{v}</td></tr>"
                    for k, v in cat_data.items() if v
                )
                categories_html += f"""
                <div class="category">
                    <h4>{cat_label}</h4>
                    <table><tbody>{rows}</tbody></table>
                </div>"""

            elif isinstance(cat_data, list) and cat_data:
                # Build table from list of dicts
                if cat_data and isinstance(cat_data[0], dict):
                    cols = list(cat_data[0].keys())
                    header = "".join(f"<th>{c}</th>" for c in cols)
                    body = ""
                    for item in cat_data:
                        cells = "".join(f"<td>{item.get(c, '')}</td>" for c in cols)
                        body += f"<tr>{cells}</tr>"
                    categories_html += f"""
                    <div class="category">
                        <h4>{cat_label}</h4>
                        <table>
                            <thead><tr>{header}</tr></thead>
                            <tbody>{body}</tbody>
                        </table>
                    </div>"""

        visit_sections += f"""
        <div class="visit">
            <h3>Visita {i}: {location}</h3>
            <p class="visit-meta">
                Tipo: <strong>{vtype}</strong> |
                Confianza: <strong>{confidence:.0%}</strong>
            </p>
            {categories_html}
        </div>"""

    alerts_html = ""
    if all_alerts:
        alert_items = "".join(f"<li>{a}</li>" for a in all_alerts)
        alerts_html = f"""
        <div class="alerts">
            <h3>Alertas de Competencia</h3>
            <ul>{alert_items}</ul>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<style>
    @page {{
        size: letter;
        margin: 2cm;
    }}
    body {{
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        font-size: 11pt;
        color: #333;
        line-height: 1.5;
    }}
    .header {{
        border-bottom: 3px solid #003366;
        padding-bottom: 10px;
        margin-bottom: 20px;
    }}
    .header h1 {{
        color: #003366;
        margin: 0;
        font-size: 20pt;
    }}
    .header h2 {{
        color: #666;
        margin: 5px 0 0 0;
        font-size: 12pt;
        font-weight: normal;
    }}
    .summary {{
        background: #f5f7fa;
        padding: 15px;
        border-radius: 6px;
        margin-bottom: 20px;
    }}
    .summary p {{
        margin: 4px 0;
    }}
    .alerts {{
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 10px 15px;
        margin-bottom: 20px;
        border-radius: 4px;
    }}
    .alerts h3 {{
        color: #856404;
        margin: 0 0 8px 0;
        font-size: 13pt;
    }}
    .alerts ul {{
        margin: 0;
        padding-left: 20px;
    }}
    .visit {{
        border: 1px solid #ddd;
        border-radius: 6px;
        padding: 15px;
        margin-bottom: 15px;
        page-break-inside: avoid;
    }}
    .visit h3 {{
        color: #003366;
        margin: 0 0 8px 0;
        font-size: 14pt;
    }}
    .visit-meta {{
        color: #666;
        font-size: 10pt;
        margin-bottom: 10px;
    }}
    .category {{
        margin: 10px 0;
    }}
    .category h4 {{
        color: #555;
        border-bottom: 1px solid #eee;
        padding-bottom: 4px;
        margin: 8px 0 6px 0;
        font-size: 11pt;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 10pt;
    }}
    th {{
        background: #003366;
        color: white;
        padding: 6px 8px;
        text-align: left;
    }}
    td {{
        padding: 5px 8px;
        border-bottom: 1px solid #eee;
    }}
    .field-name {{
        font-weight: bold;
        width: 35%;
        color: #555;
    }}
    .footer {{
        margin-top: 30px;
        padding-top: 10px;
        border-top: 1px solid #ddd;
        font-size: 9pt;
        color: #999;
        text-align: center;
    }}
</style>
</head>
<body>
    <div class="header">
        <h1>Reporte de Campo</h1>
        <h2>{user_name} — {date_str}</h2>
    </div>

    <div class="summary">
        <p><strong>Ejecutivo:</strong> {user_name}</p>
        <p><strong>Fecha:</strong> {date_str}</p>
        <p><strong>Visitas registradas:</strong> {len(reports)}</p>
    </div>

    {alerts_html}
    {visit_sections}

    <div class="footer">
        Generado por Field Genius Engine — Genius Labs AI — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
    </div>
</body>
</html>"""

    return html


async def generate_report_pdf(
    reports: list[dict[str, Any]],
    session: dict[str, Any],
) -> bytes | None:
    """Generate a PDF report from visit reports.

    Returns PDF bytes or None on failure.
    """
    try:
        from weasyprint import HTML

        html_content = _build_html(reports, session)
        pdf_bytes = HTML(string=html_content).write_pdf()

        logger.info(
            "pdf_generated",
            visits=len(reports),
            size_kb=len(pdf_bytes) // 1024,
        )
        return pdf_bytes

    except Exception as e:
        logger.error("pdf_generation_failed", error=str(e))
        return None


def build_whatsapp_summary(
    reports: list[dict[str, Any]],
    session: dict[str, Any],
) -> str:
    """Build an actionable WhatsApp summary — alerts and opportunities first."""
    user_name = session.get("user_name", "Ejecutivo")
    date_str = session.get("date", str(datetime.date.today()))
    file_count = len(session.get("raw_files", []))

    lines = [
        f"*Reporte de campo* - {user_name}",
        f"Fecha: {date_str} | {len(reports)} visita(s) | {file_count} archivo(s)",
        "",
    ]

    META_FIELDS = {"confidence_score", "needs_clarification", "clarification_questions"}

    for i, r in enumerate(reports, 1):
        location = r.get("inferred_location", "Sin ubicacion")
        visit_type = r.get("visit_type", "")
        confidence = r.get("confidence_score", 0)
        extracted = r.get("extracted_data", {})

        lines.append(f"{'='*30}")
        lines.append(f"*{i}. {location}* ({visit_type})")
        if confidence:
            lines.append(f"Confianza: {confidence:.0%}")

        # Iterate over all extracted categories generically
        for cat_id, cat_data in extracted.items():
            if cat_id in META_FIELDS:
                continue

            cat_label = cat_id.replace("_", " ").title()

            if isinstance(cat_data, dict):
                # Show non-empty fields
                field_lines = []
                for k, v in cat_data.items():
                    if v and v not in (False, 0, ""):
                        field_lines.append(f"  {k}: {v}")
                if field_lines:
                    lines.append(f"\n{cat_label}:")
                    lines.extend(field_lines)

            elif isinstance(cat_data, list) and cat_data:
                lines.append(f"\n{cat_label}: {len(cat_data)} registro(s)")
                # Show first 3 items as summary
                for j, item in enumerate(cat_data[:3]):
                    if isinstance(item, dict):
                        summary_parts = [str(v) for v in item.values() if v]
                        lines.append(f"  {j+1}. {' | '.join(summary_parts[:3])}")

        lines.append("")

    lines.append("Detalle completo en Google Sheets.")

    return "\n".join(lines)
