"""Check DW inputs without creating or modifying database objects."""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg  # noqa: E402
from pipeline.source_to_staging.common import StructuralError  # noqa: E402
from pipeline.staging_to_dw.config import DEFAULT_CONFIG, load_config  # noqa: E402
from pipeline.staging_to_dw.preflight import run  # noqa: E402


def json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime, UUID)):
        return str(value)
    raise TypeError(f"Unsupported report type: {type(value).__name__}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dbname", help="Override POSTGRES_DB")
    parser.add_argument("--output-dir", type=Path, help="New evidence directory; existing directories are refused")
    args = parser.parse_args()
    output = args.output_dir or ROOT / "artifacts/dw/operations" / (
        "inputs_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8])
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(json.dumps({"passed": False, "errors": ["Evidence directory already exists; choose a new output directory"]}))
        return 1
    try:
        result = run(load_config(args.config), dbname=args.dbname)
    except psycopg.Error:
        # Driver errors can contain connection details; keep credentials out of evidence.
        result = {"passed": False, "dw_ready": False, "errors": ["PostgreSQL operation failed; inspect local connection/settings"]}
    except (ValueError, OSError, KeyError, csv.Error, StructuralError) as exc:
        result = {"passed": False, "dw_ready": False, "errors": [str(exc)]}
    (output / "preflight.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=json_value) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "dw_ready": False, "report": str(output / "preflight.json"),
                      "errors": result["errors"], "coverage_gaps": result.get("coverage_gaps", [])}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
