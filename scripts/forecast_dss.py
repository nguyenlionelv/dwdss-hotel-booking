"""Run accepted demand forecast plus DSS-01 without retraining or web-app changes."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.demand_forecast.contracts import DemandError
from ml.demand_forecast.data import load_snapshot, write_json
from ml.demand_forecast.service import get_demand_forecast


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--dw-config", type=Path)
    parser.add_argument("--dbname")
    parser.add_argument("--model-name")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.output and args.output.exists():
        parser.error("Choose a new output file; existing evidence is never overwritten")
    try:
        snapshot = load_snapshot(args.snapshot) if args.snapshot else None
        if snapshot is not None and snapshot.source_kind != "postgresql":
            raise DemandError("FIXTURE_NOT_OFFICIAL", "CLI replay requires an official snapshot; use the Python fixture API for synthetic examples")
        payload = get_demand_forecast(args.as_of_date, bundle_path=args.bundle, snapshot=snapshot,
                                      dw_config=args.dw_config, dbname=args.dbname, model_name=args.model_name)
        if args.output:
            write_json(args.output, payload)
        print(json.dumps(payload, allow_nan=False))
        # An unavailable DSS reference does not turn a successful forecast into a CLI failure.
        return 0 if payload["forecast_status"] == "ok" else 1
    except (DemandError, ValueError, OSError, KeyError) as exc:
        print(json.dumps({"error": {"code": getattr(exc, "code", "INVALID_INPUT"), "message": str(exc)}}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
