"""Execute the Supabase schema migration.

Runs migrations/002_rebuild_schema.sql — the pipeline_* schema of record,
applied to production (opqnmrjnnafswbkawdii) on 25 April 2026. Until
17 August 2026 this script ran 001_schema.sql, which creates the RETIRED
gem_* tables; pointing it at 001 again would recreate them in a live
database. 001 is kept as history only.

002 is safe to re-run against the production database (every statement is
CREATE TABLE IF NOT EXISTS; the gatekeeper_* → prescreen_* renames it
documents were applied by hand and exist only as comments). It is NOT a
fresh-database bootstrap: it references gp_pipeline(id), which 001 created,
so on an empty database it fails loudly on the foreign key rather than
building a partial schema. A true from-scratch bootstrap needs a curated
script that does not yet exist — do not "fix" that by running 001 first.

Usage:
    python3 migrate.py --db-url "postgresql://postgres.[ref]:[password]@..."
    python3 migrate.py   (reads DATABASE_URL from .env)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Run GEM Engine database migration")
    parser.add_argument("--db-url", help="Postgres connection string (overrides DATABASE_URL env var)")
    parser.add_argument("--dry-run", action="store_true", help="Print the SQL without executing")
    args = parser.parse_args()

    migration_path = ENGINE_ROOT / "migrations" / "002_rebuild_schema.sql"
    if not migration_path.exists():
        print(f"Migration file not found: {migration_path}")
        sys.exit(1)

    sql = migration_path.read_text()

    if args.dry_run:
        print(sql)
        return

    # Get connection string
    db_url = args.db_url
    if not db_url:
        try:
            from dotenv import load_dotenv
            load_dotenv(ENGINE_ROOT / ".env", override=True)
        except ImportError:
            pass
        db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        print("ERROR: No database connection string provided.")
        print("  Option 1: python3 migrate.py --db-url 'postgresql://...'")
        print("  Option 2: Add DATABASE_URL to .env")
        print("  Option 3: python3 migrate.py --dry-run (to see the SQL)")
        print()
        print("Find your connection string in Supabase Dashboard:")
        print("  Settings → Database → Connection string (URI)")
        sys.exit(1)

    try:
        import psycopg2
    except ImportError:
        print("Installing psycopg2-binary...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary", "-q"])
        import psycopg2

    print(f"Connecting to database...")
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        conn.autocommit = True
        cur = conn.cursor()
        print("Connected. Running migration...")
        cur.execute(sql)
        print("Migration complete.")
        cur.close()
        conn.close()
        print("Done.")
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
