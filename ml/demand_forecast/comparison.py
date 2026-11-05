"""Frozen multi-version demand experiments; selection uses common validation only."""
from collections import defaultdict
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import uuid

import numpy as np

from .artifacts import code_identity, load_bundle, make_bundle, save_bundle
from .contracts import DemandError, feature_spec, local_date
from .data import digest, save_snapshot, snapshot_payload, write_json
from .evaluate import evaluate_bundle, nonoverlapping, origins_for_partition, summarize
from .filtering import filtering_analysis
from .predict import forecast_demand
from .train import fit_candidate, training_rows, validate_config
from .workflow import export_features, verify_reload

DEFAULT_COMPARISON_CONFIG = Path(__file__).with_name("comparison_config.json")


def load_settings(path=DEFAULT_COMPARISON_CONFIG):
    settings = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = ["demand-weekly-v1", "demand-short-v1", "demand-v1"]
    if settings.get("experiment_version") != "demand-feature-comparison-v1" or settings.get("feature_versions") != expected:
        raise DemandError("INVALID_CONFIG", "The comparison requires V1, V2 and V3 in order")
    for key in ("controlled_analysis", "require_nonoverlapping_mae_improvement", "test_partition_previously_evaluated"):
        if type(settings.get(key)) is not bool:
            raise DemandError("INVALID_CONFIG", f"{key} must be boolean")
    counts = settings.get("expected_training_rows")
    if not isinstance(counts, dict) or any(k not in {"V1", "V2", "V3"} or type(v) is not int or v < 1 for k, v in counts.items()):
        raise DemandError("INVALID_CONFIG", "Expected training row counts must be positive integers by version")
    return settings


def score_subset(points, origins):
    origins = set(origins)
    rows = [row for row in points if row["as_of_date"] in origins]
    result = summarize(rows)
    independent = set(nonoverlapping(sorted(origins)))
    result["nonoverlapping"] = summarize([r for r in rows if r["as_of_date"] in independent])
    return result


def paired_origin_comparison(candidate, baseline, origins):
    def errors(points):
        groups = defaultdict(list)
        for row in points:
            groups[row["as_of_date"]].append(abs(row["predicted_guest_count"] - row["actual_guest_count"]))
        return {origin: float(np.mean(values)) for origin, values in groups.items()}
    left, right = errors(candidate), errors(baseline)
    differences = [{"as_of_date": origin, "mae_improvement": right[origin] - left[origin]} for origin in origins]
    return {"origins": len(differences), "wins": sum(r["mae_improvement"] > 0 for r in differences),
            "ties": sum(r["mae_improvement"] == 0 for r in differences),
            "losses": sum(r["mae_improvement"] < 0 for r in differences), "paired_improvements": differences}


def select_strategy(comparison, policy):
    baseline = comparison[0]
    models = {"linear_regression": 0, "random_forest": 1, "xgboost": 2}
    candidates = comparison[1:]
    best = min(candidates, key=lambda row: (row["common_validation"]["mae"], row["common_validation"]["rmse"],
                                           models[row["model_name"]], row["version"]))
    baseline_mae = baseline["common_validation"]["mae"]
    improvement = baseline_mae - best["common_validation"]["mae"]
    relative = improvement / baseline_mae if baseline_mae else 0.0
    subset_improvement = (baseline["common_validation"]["nonoverlapping"]["mae"]
                          - best["common_validation"]["nonoverlapping"]["mae"])
    clears = improvement > 0 and relative >= policy["min_relative_mae_improvement"]
    if policy["require_nonoverlapping_mae_improvement"]:
        clears = clears and subset_improvement > 0
    chosen = best if clears else baseline
    return {"candidate_id": chosen["candidate_id"], "version": chosen["version"],
            "feature_version": chosen["feature_version"], "model_name": chosen["model_name"],
            "best_regression_candidate": best["candidate_id"], "best_relative_mae_improvement": relative,
            "best_nonoverlapping_mae_improvement": subset_improvement,
            "rationale": "Regression clears the frozen validation improvement gates." if clears else
                         "Seasonal naive retained: the best regression did not clear all frozen validation gates.",
            "policy": policy, "test_used_for_selection": False,
            "limitations": "Improvement gates are policy heuristics, not a statistical significance test."}


def run_feature_comparison(snapshot, config, output_dir, *, settings=None, progress=None):
    validate_config(config)
    settings = deepcopy(settings if settings is not None else load_settings())
    if snapshot.snapshot_hash != digest(snapshot_payload(snapshot)):
        raise DemandError("CORRUPT_SNAPSHOT", "Snapshot identity changed since validation")
    if snapshot.quality.get("passed") is not True or snapshot.quality.get("dw_quality", {}).get("passed") is not True:
        raise DemandError("QUALITY_FAILED", "DW/Mart quality must pass before comparison")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    save_snapshot(snapshot, output / "snapshot.json")
    emit = progress or (lambda message: None)
    specs = [feature_spec(version) for version in settings["feature_versions"]]
    frames, configs, partitions = {}, {}, {}
    for spec in specs:
        destination = output / "features" / spec.label
        destination.mkdir(parents=True)
        frames[spec.label] = export_features(snapshot, destination / "demand_features.csv", spec.version)
        configs[spec.label] = {**deepcopy(config), "feature_version": spec.version}
        partitions[spec.label] = {}
        for name, split in config["splits"].items():
            dates = training_rows(frames[spec.label], local_date(split["start"]), local_date(split["end"])).full_date
            origins = origins_for_partition(snapshot, split, history_days=spec.forecast_history_days)
            partitions[spec.label][name] = {"eligible_rows": len(dates), "eligible_dates": [str(d) for d in dates], **origins}
    baseline_origins = {name: origins_for_partition(snapshot, split, history_days=7)
                        for name, split in config["splits"].items()}
    common = {name: sorted(set(baseline_origins[name]["eligible"]).intersection(
        *(set(partitions[spec.label][name]["eligible"]) for spec in specs))) for name in config["splits"]}
    policy = {"ranking": "common validation MAE, then RMSE, then linear/forest/XGBoost, then V1/V2/V3",
              "min_relative_mae_improvement": config["min_relative_mae_improvement"],
              "require_nonoverlapping_mae_improvement": settings["require_nonoverlapping_mae_improvement"],
              "controlled_candidates_used_for_selection": False}
    frozen = {"snapshot_hash": snapshot.snapshot_hash, "data_version": snapshot.data_version,
              "run_kind": snapshot.source_kind, "code": code_identity(), "settings": settings,
              "training_configs": configs, "partitions": partitions, "common_origins": common,
              "baseline_origins": baseline_origins, "selection_policy": policy}
    frozen["plan_sha256"] = digest(frozen)
    write_json(output / "frozen_plan.json", frozen)
    analysis = filtering_analysis(snapshot, frames, config)
    write_json(output / "filtering.json", analysis)
    result = {"status": "incomplete", "run_kind": snapshot.source_kind, "data_version": snapshot.data_version,
              "snapshot_hash": snapshot.snapshot_hash, "plan_sha256": frozen["plan_sha256"],
              "comparison": [], "controlled": [], "selection": None,
              "limitations": ["Targets are retrospective final reservation states, not verified point-in-time operational observations.",
                              "Overlapping daily forecast origins are correlated; non-overlapping subsets remain small.",
                              "Availability/COMPLETE filters select clean periods and change seasonal representation.",
                              "Controlled subset experiments reduce sample/feature confounding but change date composition with sample size.",
                              "Synthetic fixtures are not official performance evidence."]}
    if settings["test_partition_previously_evaluated"]:
        result["limitations"].append("The historical test partition was evaluated in prior work; this is not a newly untouched holdout. No new test score informed this run's selection.")
    for label, expected in settings["expected_training_rows"].items():
        if partitions[label]["train"]["eligible_rows"] != expected:
            raise DemandError("UNEXPECTED_TRAINING_ROWS", f"{label} expected {expected}, found {partitions[label]['train']['eligible_rows']}")
    if (any(partitions[s.label]["train"]["eligible_rows"] < config["min_train_rows"] for s in specs)
            or len(common["validation"]) < config["min_validation_origins"]
            or len(common["test"]) < config["min_test_origins"]):
        result["reason_code"] = "INSUFFICIENT_EVALUATION_DATA"
        write_json(output / "metrics.json", result)
        return result

    start = local_date(config["splits"]["train"]["start"])
    end = local_date(config["splits"]["train"]["end"])
    validation_end = local_date(config["splits"]["validation"]["end"])
    run_id = uuid.uuid4().hex[:12]
    predictions, bundles, validation_points = [], {}, {}
    baseline = make_bundle(snapshot, "seasonal_naive", end, f"baseline-{run_id}", feature_version=specs[0].version)
    candidates = [("Baseline", "seasonal_naive", specs[0].version)] + [
        (spec.label, model, spec.version) for spec in specs for model in config["models"]]
    for label, model, version in candidates:
        candidate_id = f"{label}_{model}"
        row = {"candidate_id": candidate_id, "version": label, "model_name": model,
               "feature_version": version, "status": "failed", "test_status": "not_evaluated"}
        emit(f"Fitting/evaluating {candidate_id}")
        try:
            bundle = baseline if label == "Baseline" else fit_candidate(
                model, snapshot, frames[label], start, end, configs[label], f"{candidate_id}-{run_id}")
            origin_report = baseline_origins["validation"] if label == "Baseline" else partitions[label]["validation"]
            expanded, points = evaluate_bundle(bundle, snapshot, origin_report["eligible"])
            row.update(status="candidate", training_rows=None if label == "Baseline" else bundle.manifest["metadata"]["train_rows"],
                       common_validation=score_subset(points, common["validation"]),
                       version_validation=expanded, supported_origins=len(origin_report["eligible"]),
                       origin_coverage=len(origin_report["eligible"]) / (len(origin_report["eligible"]) + len(origin_report["excluded"])),
                       skipped_origins=origin_report["excluded"], skipped_reason_counts=origin_report["exclusion_counts"])
            if label != "Baseline":
                fit_rows = training_rows(frames[label], start, end)
                fitted = np.maximum(0, bundle.estimator.predict(fit_rows.loc[:, list(feature_spec(version).names)].astype(float)))
                row["in_sample_one_step_mae_not_backtest"] = float(np.mean(np.abs(fitted - fit_rows.target_guests)))
            bundle.manifest["metadata"].update(plan_sha256=frozen["plan_sha256"], metrics_reference="run:metrics.json",
                                                common_validation=row["common_validation"])
            saved = save_bundle(bundle, output / "bundles" / candidate_id)
            verify_reload(bundle, saved, snapshot, common["validation"][0])
            row["reload_verified"] = True
            bundles[candidate_id], validation_points[candidate_id] = bundle, points
            predictions.extend({"partition": "validation", "candidate_id": candidate_id,
                                "feature_version": version, "is_common_origin": p["as_of_date"] in common["validation"], **p} for p in points)
        except Exception as exc:
            row.update(status="failed", error_code=getattr(exc, "code", "CANDIDATE_FAILED"), error=f"{type(exc).__name__}: {exc}")
        result["comparison"].append(row)
        write_json(output / "progress" / f"{candidate_id}.json", row)
    if any(row["status"] == "failed" for row in result["comparison"]):
        result["reason_code"] = "MODEL_SELECTION_INCOMPLETE"
        write_json(output / "metrics.json", result)
        write_json(output / "predictions.json", predictions)
        return result

    for row in result["comparison"][1:]:
        row["paired_common_validation"] = paired_origin_comparison(
            validation_points[row["candidate_id"]], validation_points["Baseline_seasonal_naive"], common["validation"])

    if settings["controlled_analysis"]:
        for spec in specs:
            for subset_spec in specs:
                if subset_spec.label < spec.label:
                    continue
                for model in config["models"]:
                    candidate_id = f"{spec.label}_{model}"
                    subset_dates = [local_date(d) for d in partitions[subset_spec.label]["train"]["eligible_dates"]]
                    if spec.label == subset_spec.label:
                        main = next(row for row in result["comparison"] if row["candidate_id"] == candidate_id)
                        result["controlled"].append({"version": spec.label, "model_name": model,
                            "training_subset": subset_spec.label, "training_rows": len(subset_dates),
                            "common_validation": main["common_validation"], "reused_primary_fit": True})
                        continue
                    controlled_id = f"controlled_{candidate_id}_subset_{subset_spec.label}"
                    emit(f"Fitting/evaluating {controlled_id}")
                    bundle = fit_candidate(model, snapshot, frames[spec.label], start, end, configs[spec.label],
                                           f"{controlled_id}-{run_id}", eligible_dates=subset_dates)
                    score, points = evaluate_bundle(bundle, snapshot, common["validation"])
                    bundle.manifest["metadata"].update(plan_sha256=frozen["plan_sha256"], training_subset=subset_spec.label,
                                                        metrics_reference="run:metrics.json")
                    saved = save_bundle(bundle, output / "bundles" / controlled_id)
                    verify_reload(bundle, saved, snapshot, common["validation"][0])
                    result["controlled"].append({"version": spec.label, "model_name": model,
                        "training_subset": subset_spec.label, "training_rows": len(subset_dates),
                        "common_validation": score, "reused_primary_fit": False, "reload_verified": True})
                    predictions.extend({"partition": "controlled_validation", "candidate_id": controlled_id,
                                        "feature_version": spec.version, "is_common_origin": True, **p} for p in points)

    # No test prediction is made before this immutable selection file is written.
    selection = select_strategy(result["comparison"], policy)
    selection.update(plan_sha256=frozen["plan_sha256"], final_training_cutoff=str(validation_end),
                     selected_config=configs[selection["version"]] if selection["version"] != "Baseline" else None)
    write_json(output / "selection.json", selection)
    result["selection"] = selection
    emit(f"Frozen selection: {selection['candidate_id']}; refitting then evaluating final test")
    label, model, version = selection["version"], selection["model_name"], selection["feature_version"]
    selected = (make_bundle(snapshot, model, validation_end, f"selected-{run_id}", feature_version=version)
                if label == "Baseline" else fit_candidate(model, snapshot, frames[label], start, validation_end,
                                                          configs[label], f"selected-{run_id}"))
    test_origins = baseline_origins["test"]["eligible"] if label == "Baseline" else partitions[label]["test"]["eligible"]
    test_score, test_points = evaluate_bundle(selected, snapshot, test_origins)
    result["final_test"] = {"candidate_id": selection["candidate_id"], "metrics": test_score,
                            "common_origin_metrics": score_subset(test_points, common["test"]),
                            "test_origins": test_origins, "evaluated_after_selection": True,
                            "refit_rows": selected.manifest["metadata"].get("train_rows"),
                            "final_training_cutoff": str(validation_end)}
    predictions.extend({"partition": "selected_test", "candidate_id": selection["candidate_id"],
                        "feature_version": version, "is_common_origin": p["as_of_date"] in common["test"], **p} for p in test_points)
    if label != "Baseline":
        reference_score, reference_points = evaluate_bundle(baseline, snapshot, test_origins)
        result["final_test"]["baseline_same_origins"] = reference_score
        predictions.extend({"partition": "baseline_test_reference", "candidate_id": "Baseline_seasonal_naive",
                            "feature_version": baseline.manifest["feature_version"],
                            "is_common_origin": p["as_of_date"] in common["test"], **p} for p in reference_points)
    selected.manifest["metadata"].update(selection=selection, plan_sha256=frozen["plan_sha256"],
                                          test_metrics=test_score, metrics_reference="run:metrics.json")
    selected_path = save_bundle(selected, output / "bundles" / "selected")
    verify_reload(selected, selected_path, snapshot, test_origins[0])
    cutoff = snapshot.rows[-1].full_date
    calendar = [d for d in snapshot.calendar if cutoff < d.full_date <= cutoff + timedelta(days=7)]
    demo = forecast_demand(load_bundle(selected_path), snapshot, calendar, cutoff)
    write_json(output / "selected_forecast.json", demo.to_dict())
    result.update(status="completed", selected_bundle="bundles/selected", reload_verified=True,
                  demo_forecast_status=demo.status)
    for row in result["comparison"]:
        if row["candidate_id"] == selection["candidate_id"]:
            row.update(status="selected", test_status="selected_refit_evaluated")
    write_json(output / "metrics.json", result)
    write_json(output / "predictions.json", predictions)
    return result
