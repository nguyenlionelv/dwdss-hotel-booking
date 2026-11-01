"""Apply the Staging schema or versioned DW/Operations Mart migrations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.source_to_staging.common import connect  # noqa: E402
from pipeline.staging_to_dw.migrations import apply_dw_migrations  # noqa: E402
from pipeline.dw_to_mart.migrations import apply_mart_migration  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dbname", help="Override POSTGRES_DB, useful for isolated integration tests")
    parser.add_argument("--schema", choices=("staging", "dw", "mart"), default="staging")
    parser.add_argument("--report", type=Path, help="New JSON evidence file; an existing report is never overwritten")
    args = parser.parse_args()
    if args.report and args.report.exists():
        parser.error("Report already exists; select a new evidence path")
    try:
        with connect(args.dbname) as conn:
            if args.schema == "dw":
                result = apply_dw_migrations(conn)
            elif args.schema == "mart":
                result = apply_mart_migration(conn)
            else:
                ddl = (ROOT / "database/staging/001_staging.sql").read_text(encoding="utf-8")
                conn.execute(ddl)
                result = {"schema": "staging", "status": "applied"}
    except psycopg.Error as exc:
        # Driver details may contain connection settings or raw values.
        result = {"schema": args.schema, "status": "failed", "sqlstate": exc.sqlstate,
                  "error": "PostgreSQL migration failed; inspect connection settings or migration SQL"}
    except (ValueError, OSError) as exc:
        result = {"schema": args.schema, "status": "failed", "error": str(exc)}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    if args.schema == "staging" and not args.report and result["status"] == "applied":
        print("Staging migration applied")
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
