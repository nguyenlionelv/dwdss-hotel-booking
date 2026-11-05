"""Offline chronological experiment; writes immutable evidence, never warehouse data."""
from collections import Counter
from datetime import timedelta
import csv
import json
from pathlib import Path
import uuid
import numpy as np

from .artifacts import make_bundle, save_bundle, load_bundle
from .contracts import FEATURE_VERSION, DemandError, feature_spec, local_date
from .data import digest, snapshot_payload, save_snapshot, write_json
from .evaluate import evaluate_bundle, origins_for_partition, nonoverlapping
from .features import build_features
from .predict import forecast_demand
from .train import fit_candidate, training_rows, validate_config

def export_features(snapshot, path, feature_version=FEATURE_VERSION):
    frame = build_features(snapshot, feature_version)
    exported = frame.copy()
    exported["reason_codes"] = exported.reason_codes.map(json.dumps)
    exported.to_csv(path,index=False,mode="x")
    return frame

def write_predictions(path, rows):
    columns = ["partition","model_name","as_of_date","forecast_date","horizon","predicted_guest_count","actual_guest_count"]
    with Path(path).open("x",encoding="utf-8",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

def verify_reload(bundle, saved_path, snapshot, origin):
    loaded = load_bundle(saved_path)
    cutoff = local_date(origin)
    calendar = [r for r in snapshot.calendar if cutoff < r.full_date <= cutoff+timedelta(days=7)]
    before = forecast_demand(bundle,snapshot,calendar,cutoff)
    after = forecast_demand(loaded,snapshot,calendar,cutoff)
    if before.status != "ok" or after.status != "ok" or not np.allclose(
            [r["predicted_guest_count"] for r in before.forecasts],
            [r["predicted_guest_count"] for r in after.forecasts],rtol=1e-12,atol=1e-12):
        raise DemandError("RELOAD_MISMATCH", "Exported model does not reproduce predictions")

def run_experiment(snapshot, config, output_dir):
    validate_config(config)
    spec = feature_spec(config["feature_version"])
    if snapshot.snapshot_hash != digest(snapshot_payload(snapshot)):
        raise DemandError("CORRUPT_SNAPSHOT", "Snapshot identity changed since validation")
    if snapshot.quality.get("passed") is not True or snapshot.quality.get("dw_quality",{}).get("passed") is not True:
        raise DemandError("QUALITY_FAILED", "Source quality must pass")
    output = Path(output_dir)
    output.mkdir(parents=True,exist_ok=False)
    save_snapshot(snapshot,output/"snapshot.json")
    features = export_features(snapshot,output/"demand_features.csv",spec.version)
    splits = config["splits"]
    train_start, train_end = (local_date(splits["train"][k]) for k in ("start","end"))
    validation_end = local_date(splits["validation"]["end"])
    names = ["seasonal_naive",*config["models"]]
    frozen = {"snapshot_hash":snapshot.snapshot_hash,"data_version":snapshot.data_version,
              "config_sha256":digest(config),"config":config,"partitions":{}}
    for name, split in splits.items():
        start,end = local_date(split["start"]),local_date(split["end"])
        rows = features.loc[features.full_date.between(start,end)]
        common = origins_for_partition(snapshot,split,history_days=spec.forecast_history_days)
        frozen["partitions"][name] = {
            "calendar_rows":len(rows),"complete_targets":int(rows.target_ready.sum()),
            "train_ready_rows":int(rows.train_ready.sum()),
            "feature_exclusion_counts":dict(Counter(r for reasons in rows.reason_codes for r in reasons)),
            "common":common,"nonoverlapping_common":nonoverlapping(common["eligible"]),
            "baseline_broader":origins_for_partition(snapshot,split,history_days=7)}
    # Freeze exact dates, availability and configuration BEFORE any model fitting/ranking.
    frozen["plan_sha256"] = digest(frozen)
    write_json(output/"frozen_plan.json",frozen)
    validation_origins = frozen["partitions"]["validation"]["common"]["eligible"]
    test_origins = frozen["partitions"]["test"]["common"]["eligible"]
    result = {"status":"incomplete","run_kind":snapshot.source_kind,"data_version":snapshot.data_version,
              "snapshot_hash":snapshot.snapshot_hash,"plan_sha256":frozen["plan_sha256"],
              "comparison":[],"selected_model":None,"limitations":[
                  "Final reservation states are a retrospective guest-arrival proxy.",
                  "Only COMPLETE history/outcome windows are scored; report temporal coverage.",
                  "Overlapping daily origins are correlated, not independent samples.",
                  "Selection's relative MAE threshold is a policy heuristic, not a significance test.",
                  "Synthetic fixture results are not official model-performance evidence."
              ]}
    enough = (frozen["partitions"]["train"]["train_ready_rows"] >= config["min_train_rows"]
              and len(validation_origins) >= config["min_validation_origins"]
              and len(test_origins) >= config["min_test_origins"])
    if not enough:
        result["reason_code"] = "INSUFFICIENT_EVALUATION_DATA"
        write_json(output/"metrics.json",result)
        return result

    run_id = uuid.uuid4().hex[:12]
    bundles, predictions = {}, []
    for name in names:
        row = {"model_name":name,"status":"candidate","validation":None,"test":None,
               "test_status":"not_test_evaluated"}
        try:
            bundle = (make_bundle(snapshot,name,train_end,f"{name}-{run_id}-validation",feature_version=spec.version)
                      if name=="seasonal_naive" else
                      fit_candidate(name,snapshot,features,train_start,train_end,config,f"{name}-{run_id}-validation"))
            row["validation"], points = evaluate_bundle(bundle,snapshot,validation_origins)
            if bundle.estimator is not None:
                fit_rows = training_rows(features,train_start,train_end)
                fitted = np.maximum(0,bundle.estimator.predict(fit_rows.loc[:,list(spec.names)].astype(float)))
                row["in_sample_one_step_mae_not_backtest"] = float(np.mean(np.abs(fitted-fit_rows.target_guests)))
            predictions.extend({"partition":"validation",**r} for r in points)
            bundle.manifest["metadata"].update(plan_sha256=frozen["plan_sha256"],config_sha256=digest(config),
                                                metrics_reference="run:metrics.json")
            saved = save_bundle(bundle,output/"bundles"/f"validation_{name}")
            verify_reload(bundle,saved,snapshot,validation_origins[0])
            bundles[name] = bundle
        except Exception as exc:
            row.update(status="failed",error_code=getattr(exc,"code","CANDIDATE_FAILED"),
                       error=f"{type(exc).__name__}: {exc}")
        result["comparison"].append(row)

    if len(bundles) != len(names):
        result["reason_code"] = "MODEL_SELECTION_INCOMPLETE"
        write_json(output/"metrics.json",result)
        write_predictions(output/"predictions.csv",predictions)
        return result

    scores = {row["model_name"]:row for row in result["comparison"]}
    baseline = scores["seasonal_naive"]["validation"]["mae"]
    best = min(names,key=lambda n:(scores[n]["validation"]["mae"],scores[n]["validation"]["rmse"],names.index(n)))
    improvement = baseline-scores[best]["validation"]["mae"]
    if improvement <= 0 or (baseline > 0 and improvement/baseline < config["min_relative_mae_improvement"]):
        best = "seasonal_naive"
    result["selected_model"] = best
    result["selection"] = {"criterion":"validation MAE, then RMSE, then configured simplicity order",
                           "min_relative_mae_improvement":config["min_relative_mae_improvement"],
                           "improvement_over_baseline":baseline-scores[best]["validation"]["mae"],
                           "test_used_for_selection":False,
                           "rationale": "Seasonal naive retained unless the best candidate clears the configured validation improvement threshold."}

    final = (make_bundle(snapshot,best,validation_end,f"{best}-{run_id}-selected",feature_version=spec.version)
             if best=="seasonal_naive" else
             fit_candidate(best,snapshot,features,train_start,validation_end,config,f"{best}-{run_id}-selected"))
    final.manifest["metadata"].update(plan_sha256=frozen["plan_sha256"],config_sha256=digest(config),
                                      selection=result["selection"],metrics_reference="run:metrics.json")

    # Test is consulted only AFTER selection/refit; only baseline and the selected model are scored.
    for name in dict.fromkeys(("seasonal_naive",best)):
        bundle = final if name==best else bundles[name]
        scores[name]["test"], points = evaluate_bundle(bundle,snapshot,test_origins)
        scores[name]["test_status"] = "evaluated"
        predictions.extend({"partition":"test",**r} for r in points)
    scores[best]["status"] = "selected"
    scores["seasonal_naive"]["is_baseline"] = True
    if best != "seasonal_naive":
        scores["seasonal_naive"]["status"] = "baseline"
    result["baseline_broader"] = {}
    for partition in ("validation","test"):
        origins = frozen["partitions"][partition]["baseline_broader"]["eligible"]
        score,points = evaluate_bundle(bundles["seasonal_naive"],snapshot,origins)
        result["baseline_broader"][partition] = score
        predictions.extend({"partition":f"{partition}_baseline_broader",**r} for r in points)
    final.manifest["metadata"]["validation_metrics"] = scores[best]["validation"]
    final.manifest["metadata"]["test_metrics"] = scores[best]["test"]
    selected_path = save_bundle(final,output/"bundles"/"selected")
    verify_reload(final,selected_path,snapshot,test_origins[0])
    result.update(status="completed",selected_bundle="bundles/selected",
                  final_training_cutoff=str(validation_end),
                  final_train_rows=len(training_rows(features,train_start,validation_end)),
                  reload_verified=True)
    write_json(output/"metrics.json",result)
    write_predictions(output/"predictions.csv",predictions)
    with (output/"comparison.md").open("x",encoding="utf-8") as f:
        f.write(f"# Demand model comparison\n\nSource kind: {snapshot.source_kind}. Data version: {snapshot.data_version}.\n\n")
        f.write("| Model | Validation MAE | Validation RMSE | Test MAE | Test RMSE | Status |\n| --- | --- | --- | --- | --- | --- |\n")
        for row in result["comparison"]:
            val,test = row["validation"],row["test"]
            f.write(f'| {row["model_name"]} | {val["mae"]:.6f} | {val["rmse"]:.6f} | '
                    + (f'{test["mae"]:.6f} | {test["rmse"]:.6f}' if test else "not evaluated | not evaluated")
                    + f' | {row["status"]} |\n')
        f.write("\nUse frozen_plan.json for usable dates/exclusions; metrics.json includes per-horizon errors, bias, groups, and limitations.\n")
    return result
