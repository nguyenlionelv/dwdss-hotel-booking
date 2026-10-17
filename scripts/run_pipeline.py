"""Run the currently implemented Source -> Staging pipeline only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.source_to_staging.common import DEFAULT_MANIFEST  # noqa: E402
from pipeline.source_to_staging.run import run  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", choices=["staging"], default="staging")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dbname", help="Override POSTGRES_DB")
    parser.add_argument("--report", type=Path, help="Write the batch result as JSON")
    args = parser.parse_args()
    result = run(args.manifest, dbname=args.dbname)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
