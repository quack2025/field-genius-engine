"""Media retention — cleanup old files from Supabase Storage.

Policy:
  - Media raw files (images, audio, video) older than RETENTION_DAYS: DELETE from storage
  - Transcriptions + image_descriptions in raw_files JSON: KEEP (text, negligible size)
  - Reports and session_facts: KEEP indefinitely
  - Sessions metadata: KEEP indefinitely

Usage:
  - Called via admin endpoint: POST /api/admin/run-retention
  - Can be scheduled via cron (Railway cron or external)
  - Safe to run multiple times (idempotent)
"""

from __future__ import annotations

import datetime
from typing import Any

import structlog

from src.engine.supabase_client import get_client

logger = structlog.get_logger(__name__)

RETENTION_DAYS = 90


async def run_retention(
    retention_days: int = RETENTION_DAYS,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete media files older than retention_days from Supabase Storage.

    Keeps transcriptions and image_descriptions in the session JSON.
    Returns summary of what was deleted.
    """
    client = get_client()
    cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=retention_days)
    cutoff_str = cutoff.isoformat()

    logger.info("retention_start", cutoff=cutoff_str, dry_run=dry_run)

    # Find sessions older than cutoff in batches (avoid OOM on large datasets)
    BATCH_SIZE = 200
    sessions: list[dict[str, Any]] = []
    offset = 0
    while True:
        batch = (
            client.table("sessions")
            .select("id, raw_files, date, user_phone")
            .lt("created_at", cutoff_str)
            .range(offset, offset + BATCH_SIZE - 1)
            .execute()
        )
        rows = batch.data or []
        sessions.extend(rows)
        if len(rows) < BATCH_SIZE:
            break
        offset += BATCH_SIZE

    total_files = 0
    total_deleted = 0
    total_bytes_freed = 0
    errors: list[str] = []

    for session in sessions:
        raw_files: list[dict[str, Any]] = session.get("raw_files") or []
        updated_files = []
        session_deleted = 0

        for f in raw_files:
            storage_path = f.get("storage_path")
            file_type = f.get("type", "")
            total_files += 1

            # Only delete actual media files with storage paths
            if storage_path and file_type in ("image", "audio", "video"):
                if not dry_run:
                    try:
                        client.storage.from_("media").remove([storage_path])
                        session_deleted += 1
                        total_bytes_freed += f.get("size_bytes", 0)
                    except Exception as e:
                        errors.append(f"{storage_path}: {str(e)[:80]}")
                else:
                    session_deleted += 1
                    total_bytes_freed += f.get("size_bytes", 0)

                # Keep the metadata but clear storage_path to mark as cleaned
                cleaned = {**f, "storage_path": None, "cleaned_at": cutoff_str}
                updated_files.append(cleaned)
            else:
                updated_files.append(f)

        # Update session with cleaned file entries (keep transcriptions/descriptions)
        if session_deleted > 0 and not dry_run:
            try:
                client.table("sessions").update({
                    "raw_files": updated_files,
                }).eq("id", session["id"]).execute()
            except Exception as e:
                errors.append(f"session {session['id'][:8]}: {str(e)[:80]}")

        total_deleted += session_deleted

    summary = {
        "sessions_scanned": len(sessions),
        "files_scanned": total_files,
        "files_deleted": total_deleted,
        "bytes_freed": total_bytes_freed,
        "bytes_freed_mb": round(total_bytes_freed / (1024 * 1024), 1),
        "retention_days": retention_days,
        "cutoff_date": cutoff_str[:10],
        "dry_run": dry_run,
        "errors": errors[:20],
    }

    logger.info("retention_complete", **{k: v for k, v in summary.items() if k != "errors"})
    return summary
