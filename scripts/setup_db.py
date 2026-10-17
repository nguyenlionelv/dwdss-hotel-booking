"""Apply the idempotent Staging migration to PostgreSQL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.source_to_staging.common import connect  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dbname", help="Override POSTGRES_DB, useful for isolated integration tests")
    args = parser.parse_args()
    ddl = (ROOT / "database/staging/001_staging.sql").read_text(encoding="utf-8")
    with connect(args.dbname) as conn:
        conn.execute(ddl)
    print("Staging migration applied")


if __name__ == "__main__":
    main()
