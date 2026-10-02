"""Apply or roll back CampaIA PostgreSQL runtime migrations."""

from __future__ import annotations

import argparse
import os

from api.postgres import PostgresMigrationRunner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("up", "down", "status"))
    parser.add_argument(
        "--database-url",
        default=os.environ.get("CAMPAIA_DATABASE_URL"),
        help="PostgreSQL DSN; defaults to CAMPAIA_DATABASE_URL.",
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or CAMPAIA_DATABASE_URL is required")

    runner = PostgresMigrationRunner(args.database_url)
    if args.action == "up":
        changed = runner.apply_all()
        print("Applied:", ", ".join(changed) if changed else "none")
    elif args.action == "down":
        changed = runner.rollback_latest()
        print("Rolled back:", changed or "none")
    else:
        print("Applied:", ", ".join(runner.applied_versions()) or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
