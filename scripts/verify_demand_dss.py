"""Verify DSS on a fresh read-only Mart snapshot; preserve accepted artifacts and app code."""
import argparse
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jsonschema import Draft202012Validator, FormatChecker
from ml.demand_forecast.artifacts import load_bundle
from ml.demand_forecast.contracts import local_date, utc_now
from ml.demand_forecast.data import extract_snapshot, load_snapshot, save_snapshot, write_json
from ml.demand_forecast.dss_fixtures import synthetic_classification_example
from ml.demand_forecast.service import get_demand_forecast
from pipeline.source_to_staging.common import connect

ACCEPTED_RUN = ROOT / "artifacts/metrics/demand_feature_versions_20261105"


def inventory():
    roots = [ACCEPTED_RUN, ROOT / "artifacts/metrics/demand_recreated_20261104",
             ROOT / "artifacts/forecasts/demand_recreated_20261104", ROOT / "backend/app", ROOT / "frontend/src"]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for root in roots for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def audit_live_windows(snapshot, dbname):
    with connect(dbname) as conn, conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '120s'")
        read_only = conn.execute("SHOW transaction_read_only").fetchone()[0]
        version = conn.execute("SELECT data_version FROM mart.dataset_state WHERE singleton_id=1").fetchone()[0]
        assert str(version) == snapshot.data_version, "Published source changed during verification"
        rows = conn.execute("SELECT full_date,target_guests,guest_data_status FROM mart.daily_hotel_operations ORDER BY full_date").fetchall()
        assert [(r.full_date, r.target_guests, r.guest_data_status) for r in snapshot.rows] == rows
        # Live Mart continuity was checked above by the existing quality gate; SQL nevertheless
        # constructs the calendar explicitly so incomplete dates cannot compress a ROWS window.
        result = conn.execute("""WITH calendar AS (
          SELECT generate_series(min(full_date),max(full_date),interval '1 day')::date AS full_date
          FROM mart.daily_hotel_operations
        ), flags AS (
          SELECT c.full_date,(m.guest_data_status='COMPLETE' AND m.target_guests IS NOT NULL) IS TRUE AS complete
          FROM calendar c LEFT JOIN mart.daily_hotel_operations m USING(full_date)
        ), windows AS (
          SELECT *,count(*) OVER w AS days,count(*) FILTER (WHERE complete) OVER w AS valid_days,
                 sum(CASE WHEN complete THEN 0 ELSE 1 END) OVER (ORDER BY full_date) AS gap
          FROM flags WINDOW w AS (ORDER BY full_date ROWS BETWEEN 55 PRECEDING AND CURRENT ROW)
        ), runs AS (SELECT count(*) AS days FROM windows WHERE complete GROUP BY gap)
        SELECT count(*),count(*) FILTER (WHERE days=56),count(*) FILTER (WHERE days=56 AND valid_days=56),
               max(valid_days) FILTER (WHERE days=56),(SELECT max(days) FROM runs) FROM windows""").fetchone()
    run, longest, python_windows = 0, 0, 0
    for i, row in enumerate(snapshot.rows):
        run = run + 1 if row.guest_data_status == "COMPLETE" and row.target_guests is not None else 0
        longest = max(longest, run)
        python_windows += int(i >= 55 and run >= 56)
    assert result[2] == python_windows and result[4] == longest
    return {"transaction_read_only": read_only, "mart_days": result[0], "full_calendar_windows": result[1],
            "complete_56_day_windows": result[2], "max_complete_days_in_any_full_window": result[3],
            "longest_complete_run": result[4], "independent_sql_python_parity": True,
            "data_version": snapshot.data_version}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=ACCEPTED_RUN / "bundles/selected")
    parser.add_argument("--dw-config", type=Path, required=True)
    parser.add_argument("--dbname")
    parser.add_argument("--as-of-date", default="2017-08-31")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    output = args.output_dir or ROOT / "artifacts/metrics" / f"demand_dss_{uuid.uuid4().hex}"
    if output.exists(): parser.error("Choose a new evidence directory")
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    if branch != "App/phase-4": parser.error("Verification must run on App/phase-4")
    output.mkdir(parents=True)
    before = inventory()
    write_json(output / "protected_files_before.json", before)
    snapshot = extract_snapshot(args.dw_config, args.dbname)
    save_snapshot(snapshot, output / "snapshot.json")
    audit = audit_live_windows(snapshot, args.dbname)
    write_json(output / "dss_window_audit.json", audit)
    payload = get_demand_forecast(args.as_of_date, bundle_path=args.bundle, snapshot=snapshot)
    synthetic = synthetic_classification_example()
    schema = json.loads((ROOT / "docs/ml/demand_dss_response.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.validate(payload)
    validator.validate(synthetic)
    assert payload["forecast_status"] == "ok" and len(payload["forecasts"]) == 7
    cutoff = local_date(args.as_of_date)
    assert [r["forecast_date"] for r in payload["forecasts"]] == [str(cutoff + timedelta(days=i)) for i in range(1, 8)]
    if audit["complete_56_day_windows"] == 0:
        assert payload["dss_status"] == "INSUFFICIENT_HISTORY"
        assert all(r["demand_level"] == "INSUFFICIENT_HISTORY" for r in payload["forecasts"])
    archived = load_snapshot(ACCEPTED_RUN / "snapshot.json")
    replay = get_demand_forecast(args.as_of_date, bundle_path=args.bundle, snapshot=archived)
    assert [r["predicted_guest_count"] for r in payload["forecasts"]] == [r["predicted_guest_count"] for r in replay["forecasts"]]
    assert payload["dss_threshold_rule"] == replay["dss_threshold_rule"]
    if args.as_of_date == "2017-08-31":
        assert [r["predicted_guest_count"] for r in payload["forecasts"]] == [213, 140, 164, 154, 105, 69, 98]
        assert payload["summary"]["total_predicted_guests_7d"] == 943
    assert before == inventory(), "Accepted artifacts or Phase 3 app sources changed"
    write_json(output / "response_real.json", payload)
    write_json(output / "response_synthetic.json", synthetic)
    manifest = load_bundle(args.bundle).manifest
    report = {"generated_at_utc": utc_now(), "passed": True, "branch": branch,
              "bundle": args.bundle.as_posix(), "model_version": manifest["model_version"],
              "data_version": snapshot.data_version, "source_quality_passed": snapshot.quality["passed"],
              "source_quality_checks": len(snapshot.quality["checks"]) + len(snapshot.quality["dw_quality"]["checks"]),
              "reference_window_audit": audit, "as_of_date": args.as_of_date,
              "forecast_values": [r["predicted_guest_count"] for r in payload["forecasts"]],
              "forecast_total": payload["summary"]["total_predicted_guests_7d"],
              "dss_status": payload["dss_status"], "complete_history_days": payload["dss_threshold_rule"]["complete_days_available"],
              "schema_validated_examples": ["response_real.json", "response_synthetic.json"],
              "live_archived_inference_parity": True, "protected_files_unchanged": len(before),
              "models_retrained": 0, "full_stack_integration_verified": False}
    write_json(output / "verification.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
