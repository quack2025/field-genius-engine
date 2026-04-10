"""Daily digest — email summary of field activity to admins.

Configurable per implementation via onboarding_config.digest:
  - enabled: bool
  - emails: list of recipient emails
  - frequency: "daily" | "weekly"
  - send_hour: 19 (7pm)

Called via cron endpoint: POST /api/admin/send-digest
"""

from __future__ import annotations

import datetime
from typing import Any

import httpx
import structlog

from src.config.settings import settings
from src.engine.supabase_client import get_client, _run

logger = structlog.get_logger(__name__)


async def generate_digest(implementation_id: str) -> dict[str, Any] | None:
    """Generate digest data for an implementation. Returns None if no activity."""
    client = get_client()
    today = datetime.date.today()
    today_str = str(today)

    # Get implementation name
    impl = await _run(lambda: client.table("implementations")
        .select("name, onboarding_config")
        .eq("id", implementation_id)
        .maybe_single()
        .execute())
    if not impl or not impl.data:
        return None

    impl_name = impl.data["name"]

    # Get today's sessions
    sessions = await _run(lambda: client.table("sessions")
        .select("id, user_phone, user_name, status, raw_files, user_role, country")
        .eq("implementation", implementation_id)
        .eq("date", today_str)
        .execute())
    session_list = sessions.data or []

    if not session_list:
        return None

    # Aggregate stats
    total_photos = 0
    total_audio = 0
    total_video = 0
    total_locations = 0
    user_stats: dict[str, dict[str, Any]] = {}

    for s in session_list:
        name = s.get("user_name", s.get("user_phone", "?"))
        files = s.get("raw_files") or []
        photos = sum(1 for f in files if f.get("type") == "image")
        audio = sum(1 for f in files if f.get("type") == "audio")
        video = sum(1 for f in files if f.get("type") == "video")
        locations = sum(1 for f in files if f.get("type") == "location")

        total_photos += photos
        total_audio += audio
        total_video += video
        total_locations += locations

        user_stats[name] = {
            "photos": photos,
            "audio": audio,
            "video": video,
            "total": photos + audio + video,
            "status": s.get("status", "accumulating"),
            "country": s.get("country", ""),
        }

    # Get total registered users
    all_users = await _run(lambda: client.table("users")
        .select("phone, name", count="exact")
        .eq("implementation", implementation_id)
        .execute())
    total_registered = all_users.count or 0
    active_today = len(user_stats)
    inactive_today = total_registered - active_today

    # Sort by activity
    top_users = sorted(user_stats.items(), key=lambda x: x[1]["total"], reverse=True)[:10]

    # Pending reports (sessions not yet completed)
    pending = sum(1 for s in session_list if s.get("status") in ("accumulating", "segmenting"))

    # Estimate cost
    estimated_cost = (total_photos * 0.007) + (total_audio * 0.006) + (total_video * 0.02)

    return {
        "implementation_id": implementation_id,
        "implementation_name": impl_name,
        "date": today_str,
        "active_users": active_today,
        "total_registered": total_registered,
        "inactive_users": inactive_today,
        "photos": total_photos,
        "audio": total_audio,
        "video": total_video,
        "locations": total_locations,
        "total_files": total_photos + total_audio + total_video,
        "pending_reports": pending,
        "estimated_cost_usd": round(estimated_cost, 2),
        "top_users": [
            {"name": name, **stats} for name, stats in top_users
        ],
    }


def build_digest_html(data: dict[str, Any]) -> str:
    """Build HTML email body from digest data."""
    top_rows = ""
    for u in data["top_users"]:
        top_rows += f"""<tr>
            <td style="padding:6px 12px;border-bottom:1px solid #eee">{u['name']}</td>
            <td style="padding:6px 12px;border-bottom:1px solid #eee;text-align:center">{u['photos']}</td>
            <td style="padding:6px 12px;border-bottom:1px solid #eee;text-align:center">{u['audio']}</td>
            <td style="padding:6px 12px;border-bottom:1px solid #eee;text-align:center">{u['total']}</td>
        </tr>"""

    compliance_pct = round(data["active_users"] / max(data["total_registered"], 1) * 100)

    return f"""
    <div style="font-family:system-ui,-apple-system,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a">
        <div style="background:linear-gradient(135deg,#003366,#0055a4);padding:24px;border-radius:12px 12px 0 0">
            <h1 style="color:white;margin:0;font-size:20px">Resumen del dia — {data['implementation_name']}</h1>
            <p style="color:#8bb8e8;margin:4px 0 0;font-size:14px">{data['date']}</p>
        </div>

        <div style="background:white;padding:24px;border:1px solid #e5e7eb;border-top:none">
            <div style="display:flex;gap:16px;margin-bottom:24px">
                <div style="flex:1;background:#f0f9ff;padding:16px;border-radius:8px;text-align:center">
                    <div style="font-size:28px;font-weight:700;color:#003366">{data['active_users']}</div>
                    <div style="font-size:12px;color:#6b7280">ejecutivos activos</div>
                    <div style="font-size:11px;color:#9ca3af">(de {data['total_registered']} registrados — {compliance_pct}%)</div>
                </div>
                <div style="flex:1;background:#f0fdf4;padding:16px;border-radius:8px;text-align:center">
                    <div style="font-size:28px;font-weight:700;color:#166534">{data['total_files']}</div>
                    <div style="font-size:12px;color:#6b7280">archivos recibidos</div>
                    <div style="font-size:11px;color:#9ca3af">{data['photos']} fotos · {data['audio']} audios</div>
                </div>
            </div>

            <h3 style="font-size:14px;color:#374151;margin:0 0 8px">Top ejecutivos</h3>
            <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:24px">
                <tr style="background:#f9fafb">
                    <th style="padding:8px 12px;text-align:left;font-weight:600">Ejecutivo</th>
                    <th style="padding:8px 12px;text-align:center;font-weight:600">Fotos</th>
                    <th style="padding:8px 12px;text-align:center;font-weight:600">Audios</th>
                    <th style="padding:8px 12px;text-align:center;font-weight:600">Total</th>
                </tr>
                {top_rows}
            </table>

            {"<div style='background:#fef3c7;padding:12px 16px;border-radius:8px;margin-bottom:16px;font-size:13px'>⚠️ <strong>" + str(data['inactive_users']) + " ejecutivos</strong> no enviaron datos hoy</div>" if data['inactive_users'] > 0 else ""}

            <div style="background:#f8fafc;padding:16px;border-radius:8px;margin-bottom:16px">
                <div style="font-size:13px;color:#6b7280">Reportes pendientes: <strong>{data['pending_reports']}</strong> sesiones</div>
                <div style="font-size:13px;color:#6b7280">Costo estimado de procesamiento: <strong>${data['estimated_cost_usd']:.2f} USD</strong></div>
            </div>

            <a href="https://app.xponencial.net/sessions" style="display:inline-block;background:#003366;color:white;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:14px;font-weight:500">
                Ver sesiones y generar reportes →
            </a>
        </div>

        <div style="padding:16px;text-align:center;font-size:11px;color:#9ca3af;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px;background:#fafafa">
            Field Genius Engine — Genius Labs AI · Xponencial.net
        </div>
    </div>
    """


async def send_digest_email(
    to_emails: list[str],
    subject: str,
    html_body: str,
) -> bool:
    """Send email via Resend API."""
    resend_key = settings.resend_api_key if hasattr(settings, 'resend_api_key') else ""
    if not resend_key:
        logger.warning("digest_email_skipped_no_resend_key")
        return False

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {resend_key}"},
                json={
                    "from": "Field Genius <noreply@xponencial.net>",
                    "to": to_emails,
                    "subject": subject,
                    "html": html_body,
                },
            )
            if resp.status_code in (200, 201):
                logger.info("digest_email_sent", to=to_emails, status=resp.status_code)
                return True
            else:
                logger.error("digest_email_failed", status=resp.status_code, body=resp.text[:200])
                return False
    except Exception as e:
        logger.error("digest_email_error", error=str(e))
        return False


async def run_digest_for_implementation(implementation_id: str) -> dict[str, Any]:
    """Generate and send digest for a single implementation. Returns summary."""
    from src.engine.config_loader import get_implementation
    config = await get_implementation(implementation_id)
    digest_config = config.onboarding_config.get("digest", {})

    if not digest_config.get("enabled"):
        return {"implementation_id": implementation_id, "status": "disabled"}

    emails = digest_config.get("emails", [])
    if not emails:
        return {"implementation_id": implementation_id, "status": "no_emails"}

    # Generate digest data
    data = await generate_digest(implementation_id)
    if not data:
        return {"implementation_id": implementation_id, "status": "no_activity"}

    # Build and send email
    html = build_digest_html(data)
    subject = f"Resumen del dia — {data['implementation_name']} | {data['date']}"

    sent = await send_digest_email(emails, subject, html)

    return {
        "implementation_id": implementation_id,
        "status": "sent" if sent else "send_failed",
        "recipients": emails,
        "active_users": data["active_users"],
        "total_files": data["total_files"],
    }
