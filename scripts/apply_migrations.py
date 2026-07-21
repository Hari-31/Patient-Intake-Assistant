import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.database import require_postgres_url


def main() -> None:
    load_dotenv()
    try:
        database_url = require_postgres_url(os.getenv("DATABASE_URL"))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    migrations_dir = PROJECT_ROOT / "supabase" / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        raise SystemExit("No SQL migrations were found.")

    with psycopg.connect(database_url, connect_timeout=15) as connection:
        connection.execute(
            """
            create table if not exists public.app_schema_migrations (
                filename text primary key,
                applied_at timestamptz not null default now()
            )
            """
        )
        connection.execute(
            "alter table public.app_schema_migrations enable row level security"
        )
        connection.commit()

        for migration_file in migration_files:
            already_applied = connection.execute(
                "select 1 from public.app_schema_migrations where filename = %s",
                (migration_file.name,),
            ).fetchone()
            if already_applied:
                print(f"Skipped {migration_file.name} (already applied)")
                continue

            with connection.transaction():
                connection.execute(migration_file.read_text(encoding="utf-8"))
                connection.execute(
                    "insert into public.app_schema_migrations (filename) values (%s)",
                    (migration_file.name,),
                )
            print(f"Applied {migration_file.name}")


if __name__ == "__main__":
    main()
