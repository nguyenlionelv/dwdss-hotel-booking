"""Run Source -> Staging or the complete published Staging -> DW/Mart workflow."""

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
from pipeline.staging_to_dw.run import run as load_dw  # noqa: E402
from pipeline.staging_to_dw.workflow import run as run_dw_workflow  # noqa: E402
from pipeline.quality.dw_checks import json_value  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--to", choices=["staging", "dw"], default="staging")
    parser.add_argument("--manifest", type=Path, help="Source manifest, Staging only")
    parser.add_argument("--dbname", help="Override POSTGRES_DB")
    parser.add_argument("--report", type=Path, help="New JSON report for Staging or --step load")
    parser.add_argument("--config", type=Path, help="DW input configuration")
    parser.add_argument("--step", choices=("all", "load"), help="DW step; defaults to all")
    parser.add_argument("--output-dir", type=Path, help="New evidence directory for the complete DW workflow")
    parser.add_argument("--with-mart", action="store_true", help="Install and independently verify Mart with DW")
    parser.add_argument("--with-tests", action="store_true", help="Run Staging, DW and Mart tests after DW verification")
    args = parser.parse_args(argv)
    workflow_options = args.output_dir is not None or args.with_mart or args.with_tests
    if args.to == "staging":
        if args.step is not None or args.config is not None or workflow_options:
            parser.error("--step, --config, --output-dir, --with-mart and --with-tests require --to dw")
    else:
        if args.manifest is not None:
            parser.error("--manifest is for Staging; DW selects its manifest through --config")
        if args.step == "load" and workflow_options:
            parser.error("--output-dir, --with-mart and --with-tests require the complete DW workflow")
        if args.step != "load":
            if args.report is not None:
                parser.error("Use --output-dir for the complete DW workflow, or --step load with --report")
            return run_dw_workflow(args.config or DEFAULT_CONFIG, dbname=args.dbname,
                                   output_dir=args.output_dir, with_mart=args.with_mart, with_tests=args.with_tests)
    if args.report and args.report.exists():
        parser.error("Report already exists; choose a new evidence file")
    try:
        if args.to == "dw":
            result = load_dw(args.config or DEFAULT_CONFIG, dbname=args.dbname)
        else:
            result = run_staging(args.manifest or DEFAULT_MANIFEST, dbname=args.dbname)
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
