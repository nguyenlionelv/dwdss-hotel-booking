"""Run Source -> Staging or published Staging -> DW."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.source_to_staging.common import DEFAULT_MANIFEST  # noqa: E402
from pipeline.source_to_staging.common import StructuralError  # noqa: E402
from pipeline.source_to_staging.run import run as run_staging  # noqa: E402
from pipeline.staging_to_dw.config import DEFAULT_CONFIG  # noqa: E402
from pipeline.staging_to_dw.run import run as run_dw  # noqa: E402
from pipeline.quality.dw_checks import json_value  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", choices=["staging", "dw"], default="staging")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dbname", help="Override POSTGRES_DB")
    parser.add_argument("--report", type=Path, help="Write the batch result as JSON")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="DW input configuration")
    args = parser.parse_args()
    if args.report and args.report.exists():
        parser.error("Report already exists; choose a new evidence file")
    try:
        result = run_dw(args.config, dbname=args.dbname) if args.to == "dw" else run_staging(args.manifest, dbname=args.dbname)
    except psycopg.Error as exc:
        result = {"status": "failed", "error": f"PostgreSQL pipeline operation failed (SQLSTATE {exc.sqlstate})"}
    except (ValueError, RuntimeError, OSError, KeyError, StructuralError) as exc:
        result = {"status": "failed", "error": str(exc)}
    if args.report:
        try:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            with args.report.open("x", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2, default=json_value)
                handle.write("\n")
        except OSError:
            print(json.dumps({**result, "report_error": "Could not save evidence after the database operation"}, default=json_value))
            return 1
    print(json.dumps(result, ensure_ascii=False, default=json_value))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
