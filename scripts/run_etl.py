"""Run the full Raw -> Staging -> DW -> Operations Mart workflow in one command."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.staging_to_dw.config import DEFAULT_CONFIG  # noqa: E402
from pipeline.workflow import run  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dbname", help="Override POSTGRES_DB")
    parser.add_argument("--output-dir", type=Path, help="New directory for all ETL evidence")
    args = parser.parse_args(argv)
    return run(args.config, dbname=args.dbname, output_dir=args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
