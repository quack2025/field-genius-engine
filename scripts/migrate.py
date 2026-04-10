"""Simple SQL migration runner for Supabase.

Tracks applied migrations in a `_migrations` table.
Run: python scripts/migrate.py [--dry-run]

Reads SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from .env or environment.
"""

import os
import sys
import re
from pathlib import Path


def main():
    dry_run = "--dry-run" in sys.argv

    # Load env
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    from supabase import create_client
    client = create_client(url, key)

    # Ensure migrations tracking table exists
    try:
        client.table("_migrations").select("name").limit(1).execute()
    except Exception:
        # Table doesn't exist — create it via RPC or direct SQL
        print("Creating _migrations table...")
        client.postgrest.rpc("exec_sql", {
            "sql": """
            CREATE TABLE IF NOT EXISTS _migrations (
                name text PRIMARY KEY,
                applied_at timestamptz DEFAULT now()
            );
            """
        }).execute()

    # Get already applied
    result = client.table("_migrations").select("name").execute()
    applied = {r["name"] for r in (result.data or [])}
    print(f"Already applied: {len(applied)} migrations")

    # Find SQL files
    sql_dir = Path(__file__).parent.parent / "sql"
    files = sorted(sql_dir.glob("*.sql"))

    # Filter to numbered migrations only (e.g., 001_name.sql)
    numbered = [f for f in files if re.match(r"^\d{3}_", f.name)]

    pending = [f for f in numbered if f.name not in applied]

    if not pending:
        print("No pending migrations.")
        return

    print(f"Pending: {len(pending)} migrations")
    for f in pending:
        print(f"  {'[DRY RUN] ' if dry_run else ''}Applying: {f.name}")
        if not dry_run:
            sql = f.read_text(encoding="utf-8")
            try:
                # Execute via Supabase RPC (requires exec_sql function)
                client.postgrest.rpc("exec_sql", {"sql": sql}).execute()
                client.table("_migrations").insert({"name": f.name}).execute()
                print(f"    OK: {f.name}")
            except Exception as e:
                print(f"    FAILED: {f.name} — {e}")
                print("    Stopping. Fix the error and re-run.")
                sys.exit(1)

    print("Done!" if not dry_run else "Dry run complete. No changes applied.")


if __name__ == "__main__":
    main()
