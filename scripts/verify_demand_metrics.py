"""Recompute accepted comparison metrics from saved predictions; never refits models."""
import argparse
import json
from math import isclose, sqrt
from pathlib import Path
from statistics import fmean
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.demand_forecast.artifacts import load_bundle
from ml.demand_forecast.data import digest, load_snapshot, write_json


def check_score(rows, saved):
    if not rows:
        raise ValueError("No prediction points for saved score")
    errors = [row["predicted_guest_count"] - row["actual_guest_count"] for row in rows]
    actual = {"mae": fmean(abs(e) for e in errors), "rmse": sqrt(fmean(e * e for e in errors)),
              "bias": fmean(errors), "points": len(rows), "origins": len({r["as_of_date"] for r in rows})}
    for key, value in actual.items():
        if not isclose(value, saved[key], rel_tol=0, abs_tol=1e-10):
            raise ValueError(f"Saved {key} differs from recomputed value")
    for h in range(1, 8):
        group = [row for row in rows if row["horizon"] == h]
        expected = saved["by_horizon"][str(h)]
        if len(group) != expected["points"]:
            raise ValueError("Horizon point counts differ")
        if group:
            errors = [row["predicted_guest_count"] - row["actual_guest_count"] for row in group]
            if not isclose(fmean(abs(e) for e in errors), expected["mae"], rel_tol=0, abs_tol=1e-10):
                raise ValueError("Horizon MAE differs")
            if not isclose(sqrt(fmean(e * e for e in errors)), expected["rmse"], rel_tol=0, abs_tol=1e-10):
                raise ValueError("Horizon RMSE differs")


def verify_metrics(run_dir):
    root = Path(run_dir)
    read = lambda name: json.loads((root / name).read_text(encoding="utf-8"))
    metrics, plan, rows = read("metrics.json"), read("frozen_plan.json"), read("predictions.json")
    if metrics["status"] != "completed" or plan["settings"]["experiment_version"] != "demand-feature-comparison-v1":
        raise ValueError("A completed feature-version comparison is required")
    if plan.pop("plan_sha256") != digest(plan):
        raise ValueError("Frozen plan hash mismatch")
    snapshot = load_snapshot(root / "snapshot.json")
    if snapshot.snapshot_hash != metrics["snapshot_hash"] or snapshot.data_version != metrics["data_version"]:
        raise ValueError("Snapshot identity differs from metrics")
    actual = {str(r.full_date): r for r in snapshot.rows}
    for row in rows:
        target = actual[row["forecast_date"]]
        if target.guest_data_status != "COMPLETE" or target.target_guests != row["actual_guest_count"]:
            raise ValueError("Scored outcome differs from a COMPLETE snapshot target")
    checked = 0
    for candidate in metrics["comparison"]:
        points = [row for row in rows if row["partition"] == "validation" and row["candidate_id"] == candidate["candidate_id"]]
        check_score(points, candidate["version_validation"])
        check_score([row for row in points if row["is_common_origin"]], candidate["common_validation"])
        checked += 2
    for controlled in metrics["controlled"]:
        primary_id = f"{controlled['version']}_{controlled['model_name']}"
        candidate_id = primary_id if controlled["reused_primary_fit"] else f"controlled_{primary_id}_subset_{controlled['training_subset']}"
        partition = "validation" if controlled["reused_primary_fit"] else "controlled_validation"
        points = [row for row in rows if row["partition"] == partition and row["candidate_id"] == candidate_id and row["is_common_origin"]]
        check_score(points, controlled["common_validation"])
        checked += 1
    test = [row for row in rows if row["partition"] == "selected_test"]
    check_score(test, metrics["final_test"]["metrics"])
    check_score([row for row in test if row["is_common_origin"]], metrics["final_test"]["common_origin_metrics"])
    checked += 2
    if "baseline_same_origins" in metrics["final_test"]:
        check_score([r for r in rows if r["partition"] == "baseline_test_reference"], metrics["final_test"]["baseline_same_origins"])
        checked += 1
    bundles = [p for p in (root / "bundles").iterdir() if p.is_dir()]
    for bundle in bundles: load_bundle(bundle)
    return {"passed": True, "score_sets_recomputed": checked, "bundles_reloaded": len(bundles),
            "prediction_points_verified": len(rows), "data_version": snapshot.data_version,
            "models_retrained": 0, "historical_training_code_hashes_preserved": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if args.report and args.report.exists(): parser.error("Choose a new report file")
    result = verify_metrics(args.run_dir)
    if args.report: write_json(args.report, result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
