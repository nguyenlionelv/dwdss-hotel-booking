"""Refresh only Operations Mart from the published DW snapshot."""

import argparse
import json
from pathlib import Path
import sys

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.dw_to_mart.run import run  # noqa: E402
from pipeline.quality.dw_checks import json_value  # noqa: E402
from pipeline.staging_to_dw.config import DEFAULT_CONFIG  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dbname")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.report and args.report.exists():
        parser.error("Report already exists; choose a new evidence file")
    try:
        result = run(args.config, dbname=args.dbname)
    except psycopg.Error as exc:
        result = {"status": "failed", "error": f"PostgreSQL Mart operation failed (SQLSTATE {exc.sqlstate})"}
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        result = {"status": "failed", "error": str(exc)}
    if args.report:
        try:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            with args.report.open("x", encoding="utf-8") as handle:
                json.dump(result,handle,ensure_ascii=False,indent=2,default=json_value)
                handle.write("\n")
        except OSError:
            print(json.dumps({**result,"report_error":"Could not save evidence after the database operation"},default=json_value))
            return 1
    print(json.dumps(result,ensure_ascii=False,default=json_value))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
