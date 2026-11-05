"""Compare V1/V2/V3 demand features using an official, quality-gated snapshot."""
import argparse
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.demand_forecast.comparison import DEFAULT_COMPARISON_CONFIG, load_settings, run_feature_comparison
from ml.demand_forecast.comparison_report import generate_report
from ml.demand_forecast.contracts import DemandError
from ml.demand_forecast.data import extract_snapshot, load_snapshot, write_json
from ml.demand_forecast.train import DEFAULT_CONFIG, load_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--comparison-config", type=Path, default=DEFAULT_COMPARISON_CONFIG)
    parser.add_argument("--dw-config", type=Path)
    parser.add_argument("--dbname")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    output = args.output_dir or ROOT / "artifacts/metrics" / f"demand_versions_{uuid.uuid4().hex}"
    if output.exists():
        parser.error("Choose a new output directory; accepted artifacts must not be overwritten")
    try:
        config, settings = load_config(args.config), load_settings(args.comparison_config)
        snapshot = load_snapshot(args.snapshot) if args.snapshot else extract_snapshot(args.dw_config, args.dbname)
        if snapshot.source_kind != "postgresql":
            raise DemandError("FIXTURE_NOT_OFFICIAL", "Comparison CLI requires an official PostgreSQL snapshot")
        result = run_feature_comparison(snapshot, config, output, settings=settings,
                                        progress=lambda message: print(message, flush=True))
        if result["status"] == "completed":
            generate_report(output)
        print(f'{result["status"]}: {output}', flush=True)
        return 0 if result["status"] == "completed" else 1
    except (DemandError, ValueError, OSError, KeyError) as exc:
        output.mkdir(parents=True, exist_ok=True)
        write_json(output / "failure.json", {"status": "failed", "error_code": getattr(exc, "code", "INVALID_INPUT"),
                                             "message": str(exc), "quality": getattr(exc, "quality", None)})
        print(f'{getattr(exc, "code", "INVALID_INPUT")}: {exc}; evidence: {output}', flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
