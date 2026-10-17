#!/usr/bin/env python3
"""Generate reproducible Portugal and Lisboa public-holiday source data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path

import holidays


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/holiday"))
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    args = parser.parse_args()
    if args.end_year < args.start_year:
        raise ValueError("end-year must be greater than or equal to start-year")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / f"pt_lisboa_holidays_{args.start_year}_{args.end_year}_{args.run_id}.csv"
    metadata_path = args.output_dir / f"pt_lisboa_holidays_{args.start_year}_{args.end_year}_{args.run_id}.metadata.json"
    if csv_path.exists() or metadata_path.exists():
        raise FileExistsError("Refusing to overwrite an existing holiday acquisition")

    years = list(range(args.start_year, args.end_year + 1))
    national = holidays.country_holidays("PT", years=years, observed=False, language="pt_PT")
    lisboa = holidays.country_holidays("PT", subdiv="11", years=years, observed=False, language="pt_PT")
    rows: list[dict[str, str]] = []
    for day, name in sorted(national.items()):
        rows.append(
            {
                "date": day.isoformat(),
                "holiday_name": name,
                "country": "PT",
                "subdivision": "",
                "scope": "national",
                "category": "public",
                "observed": "false",
            }
        )
    for day, name in sorted(lisboa.items()):
        if day not in national or name != national[day]:
            rows.append(
                {
                    "date": day.isoformat(),
                    "holiday_name": name,
                    "country": "PT",
                    "subdivision": "11",
                    "scope": "Lisboa",
                    "category": "public",
                    "observed": "false",
                }
            )
    rows.sort(key=lambda row: (row["date"], row["scope"], row["holiday_name"]))
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "python-holidays",
        "library_version": importlib.metadata.version("holidays"),
        "documentation": "https://holidays.readthedocs.io/en/main/auto_gen_docs/portugal/",
        "country": "PT",
        "subdivision": "11 (Lisboa)",
        "years": years,
        "category": "PUBLIC",
        "observed": False,
        "local_rule": "Keep national rows once and add only Lisboa-specific/different rows.",
        "csv_file": str(csv_path),
        "csv_sha256": sha256(csv_path),
        "row_count": len(rows),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
