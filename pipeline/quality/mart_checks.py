"""Read-only DW and Operations Mart checks in one published snapshot."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.dw_to_mart.checks import validate_operations  # noqa: E402
from pipeline.quality.dw_checks import json_value  # noqa: E402
from pipeline.source_to_staging.common import connect  # noqa: E402
from pipeline.staging_to_dw.checks import validate_loaded  # noqa: E402
from pipeline.staging_to_dw.config import DEFAULT_CONFIG, load_config  # noqa: E402


def report(conn, bundle: dict) -> dict:
    if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        raise ValueError("Mart quality requires an idle connection")
    with conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        active = conn.execute("""SELECT r.run_id FROM dw.active_dataset a JOIN dw.load_run r USING(run_id)
                                 WHERE a.singleton_id=1 AND r.status='published'""").fetchone()
        if not active:
            raise ValueError("No published DW dataset")
        dw = validate_loaded(conn,active[0],bundle)
        mart = validate_operations(conn,active[0],bundle)
    return {**mart, "passed": dw["passed"] and mart["passed"], "dw_quality": dw,
            "errors": [*dw["errors"],*mart["errors"]], "generated_at_utc": datetime.now(timezone.utc).isoformat()}


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
            result = report(conn,bundle)
    except psycopg.Error as exc:
        result = {"passed":False,"errors":[f"PostgreSQL Mart quality failed (SQLSTATE {exc.sqlstate})"]}
    except (ValueError, OSError, KeyError) as exc:
        result = {"passed":False,"errors":[str(exc)]}
    if args.report:
        try:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            with args.report.open("x",encoding="utf-8") as handle:
                json.dump(result,handle,ensure_ascii=False,indent=2,default=json_value)
                handle.write("\n")
        except OSError:
            print(json.dumps({**result,"report_error":"Could not save quality evidence"},default=json_value))
            return 1
    print(json.dumps(result,ensure_ascii=False,default=json_value))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
