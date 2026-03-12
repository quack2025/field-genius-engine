"""Google Sheets writer — dynamic columns from schema, one tab per visit type."""

from __future__ import annotations

import json
import datetime
from typing import Any

import structlog
import gspread

from src.config.settings import settings

logger = structlog.get_logger(__name__)

_gc: gspread.Client | None = None


def _get_sheets_client() -> gspread.Client | None:
    """Return a singleton gspread client using service account credentials."""
    global _gc
    if _gc is not None:
        return _gc

    if not settings.google_service_account_email or not settings.google_private_key:
        logger.warning("sheets_client_no_credentials")
        return None

    try:
        creds_dict = {
            "type": "service_account",
            "project_id": "insight-genius-io",
            "private_key": settings.google_private_key.replace("\\n", "\n"),
            "client_email": settings.google_service_account_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        _gc = gspread.service_account_from_dict(creds_dict)
        logger.info("sheets_client_initialized")
        return _gc
    except Exception as e:
        logger.error("sheets_client_init_failed", error=str(e))
        return None


def _load_schema(visit_type: str, implementation: str = "argos") -> dict[str, Any]:
    """Load schema JSON for a visit type."""
    type_to_file = {
        "ferreteria": "ferreteria.json",
        "obra_civil": "obra_civil.json",
        "obra_pequeña": "obra_pequena.json",
        "obra_pequena": "obra_pequena.json",
    }
    filename = type_to_file.get(visit_type, "ferreteria.json")
    path = f"src/implementations/{implementation}/schemas/{filename}"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_headers(schema: dict[str, Any]) -> list[str]:
    """Build column headers from schema categories and fields."""
    headers = ["Fecha", "Ejecutivo", "Teléfono", "Ubicación", "Confianza"]
    for cat in schema["categories"]:
        for field in cat["fields"]:
            headers.append(f"{cat['label']} - {field['label']}")
    return headers


def _flatten_visit(
    report: dict[str, Any],
    schema: dict[str, Any],
    session: dict[str, Any],
) -> list[list[str]]:
    """Flatten extracted data into spreadsheet rows.

    For array categories, each item becomes a separate row.
    Non-array categories are repeated on every row.
    """
    extracted = report.get("extracted_data", {})
    date_str = session.get("date", str(datetime.date.today()))
    user_name = session.get("user_name", "")
    user_phone = session.get("user_phone", "")
    location = report.get("inferred_location", "")
    confidence = report.get("confidence_score", 0.0)

    # Identify array categories to determine how many rows we need
    array_cats = [c for c in schema["categories"] if c.get("is_array")]
    non_array_cats = [c for c in schema["categories"] if not c.get("is_array")]

    # Determine max array length
    max_rows = 1
    for cat in array_cats:
        items = extracted.get(cat["id"], [])
        if isinstance(items, list) and len(items) > max_rows:
            max_rows = len(items)

    rows: list[list[str]] = []
    for i in range(max_rows):
        row = [date_str, user_name, user_phone, location, str(confidence)]
        for cat in schema["categories"]:
            data = extracted.get(cat["id"])
            if cat.get("is_array"):
                items = data if isinstance(data, list) else []
                item = items[i] if i < len(items) else {}
                for field in cat["fields"]:
                    row.append(str(item.get(field["id"], "")))
            else:
                obj = data if isinstance(data, dict) else {}
                for field in cat["fields"]:
                    val = obj.get(field["id"], "")
                    # Only fill non-array fields on the first row
                    row.append(str(val) if i == 0 else "")
        rows.append(row)

    return rows


async def write_visit_report(
    report: dict[str, Any],
    session: dict[str, Any],
    implementation: str = "argos",
) -> str | None:
    """Write a visit report to Google Sheets. Returns the sheet tab name or None on failure.

    Fire-and-forget: caller should not block on this.
    """
    gc = _get_sheets_client()
    if gc is None:
        logger.warning("sheets_write_skipped", reason="no_client")
        return None

    spreadsheet_id = settings.google_spreadsheet_id
    if not spreadsheet_id:
        logger.warning("sheets_write_skipped", reason="no_spreadsheet_id")
        return None

    visit_type = report.get("visit_type", "ferreteria")

    try:
        schema = _load_schema(visit_type, implementation)
        tab_name = schema.get("sheets_tab", visit_type)
        headers = _build_headers(schema)

        spreadsheet = gc.open_by_key(spreadsheet_id)

        # Get or create worksheet
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=len(headers))
            worksheet.append_row(headers, value_input_option="USER_ENTERED")
            logger.info("sheets_tab_created", tab=tab_name)

        # Check if headers exist (first row)
        existing = worksheet.row_values(1)
        if not existing:
            worksheet.append_row(headers, value_input_option="USER_ENTERED")

        # Flatten and write rows
        rows = _flatten_visit(report, schema, session)
        for row in rows:
            worksheet.append_row(row, value_input_option="USER_ENTERED")

        logger.info(
            "sheets_write_success",
            tab=tab_name,
            rows_written=len(rows),
            visit_type=visit_type,
        )
        return tab_name

    except Exception as e:
        logger.error("sheets_write_failed", error=str(e), visit_type=visit_type)
        return None
