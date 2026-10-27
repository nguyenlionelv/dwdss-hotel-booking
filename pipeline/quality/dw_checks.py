"""Read-only validation of the active DW dataset against its pinned Staging sources."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import psycopg
from pipeline.source_to_staging.common import connect
from pipeline.staging_to_dw.checks import validate_loaded
from pipeline.staging_to_dw.config import DEFAULT_CONFIG, load_config


def json_value(value):
    if isinstance(value, (date, datetime, UUID, Decimal)):
        return str(value)
    raise TypeError(f"Unsupported report type: {type(value).__name__}")


def report(conn, bundle: dict) -> dict:
    if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        raise ValueError("DW quality requires an idle connection")
    with conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        active = conn.execute("""SELECT r.run_id FROM dw.active_dataset a JOIN dw.load_run r USING(run_id)
                                 WHERE a.singleton_id=1 AND r.status='published'""").fetchone()
        if not active:
            raise ValueError("No published DW dataset")
        result = validate_loaded(conn, active[0], bundle)
    return {"generated_at_utc": datetime.now(timezone.utc).isoformat(), **result}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dbname")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.report and args.report.exists():
        parser.error("Report already exists; choose a new evidence file")
    try:
        bundle = load_config(args.config)
        with connect(args.dbname) as conn:
            result = report(conn, bundle)
    except psycopg.Error as exc:
        result = {"passed": False, "errors": [f"PostgreSQL quality check failed (SQLSTATE {exc.sqlstate})"]}
    except (ValueError, OSError, KeyError) as exc:
        result = {"passed": False, "errors": [str(exc)]}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2, default=json_value)
            handle.write("\n")
    print(json.dumps(result, ensure_ascii=False, default=json_value))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
