from copy import deepcopy
from datetime import date, timedelta
import json
from unittest.mock import patch

import pytest

from ml.demand_forecast.artifacts import load_bundle, make_bundle, save_bundle
from ml.demand_forecast.comparison import load_settings, run_feature_comparison, select_strategy
from ml.demand_forecast.comparison_report import generate_report
from ml.demand_forecast.contracts import DemandError, FEATURE_SPECS
from ml.demand_forecast.data import digest, save_snapshot
from ml.demand_forecast.features import build_features
from ml.demand_forecast.filtering import filtering_analysis
from ml.demand_forecast.predict import forecast_demand
from ml.demand_forecast.train import fit_candidate, load_config
from scripts import compare_demand_features


@pytest.fixture
def comparison_config():
    config = load_config()
    config.update(min_train_rows=10, min_validation_origins=1, min_test_origins=1)
    config["splits"] = {"train": {"start": "2020-01-01", "end": "2020-02-04"},
                        "validation": {"start": "2020-02-05", "end": "2020-02-18"},
                        "test": {"start": "2020-02-19", "end": "2020-03-04"}}
    config["models"]["random_forest"]["n_estimators"] = 3
    config["models"]["xgboost"]["n_estimators"] = 3
    return config


def horizon(snapshot, cutoff):
    return [r for r in snapshot.calendar if cutoff < r.full_date <= cutoff + timedelta(days=7)]


def test_version_masks_follow_exact_calendar_offsets(snapshot_factory):
    snapshot = snapshot_factory(changes={10: {"target_guests": None, "guest_data_status": "PARTIAL"}})
    frames = {spec.label: build_features(snapshot, spec.version) for spec in FEATURE_SPECS.values()}
    assert [int(frames[label].train_ready.sum()) for label in ["V1", "V2", "V3"]] == [91, 85, 75]
    assert frames["V1"].iloc[11].train_ready  # Yesterday is PARTIAL; d-7 is known.
    assert not frames["V2"].iloc[11].train_ready
    assert not frames["V1"].iloc[17].train_ready  # Exact d-7, not the seventh available row.
    assert frames["V2"].iloc[18].train_ready
    assert not frames["V3"].iloc[18].train_ready
    assert frames["V3"].iloc[25].train_ready
    for frame in frames.values():
        assert len(frame) == 100 and not frame.iloc[10].target_ready
        assert frame.iloc[10].target_guests != frame.iloc[10].target_guests  # NULL -> NaN, never zero.
    masks = [set(frame.loc[frame.train_ready, "full_date"]) for frame in frames.values()]
    assert masks[2] <= masks[1] <= masks[0]


class HistoricalPlusTen:
    def __init__(self):
        self.inputs = []

    def predict(self, frame):
        self.inputs.append(frame.copy())
        return [frame.iloc[0]["lag_1" if "lag_1" in frame else "lag_7"] + 10]


@pytest.mark.parametrize("version", list(FEATURE_SPECS))
def test_all_versions_ignore_future_actuals_and_preserve_recursive_state(snapshot_factory, version):
    spec = FEATURE_SPECS[version]
    snapshot = snapshot_factory()
    changed = snapshot_factory(changes={i: {"target_guests": 999999} for i in range(20, 100)})
    cutoff = date(2020, 1, 20)
    estimator = HistoricalPlusTen()
    bundle = make_bundle(snapshot, "linear_regression", cutoff, "fixture", estimator=estimator, feature_version=version)
    a = forecast_demand(bundle, snapshot, horizon(snapshot, cutoff), cutoff)
    b = forecast_demand(bundle, changed, horizon(changed, cutoff), cutoff)
    expected = list(range(24, 31)) if spec.label == "V1" else list(range(30, 91, 10))
    assert [p["predicted_guest_count"] for p in a.forecasts] == expected
    assert [p["predicted_guest_count"] for p in b.forecasts] == expected
    assert list(estimator.inputs[0].columns) == list(spec.names)
    assert a.feature_version == version
    assert a.forecasts[-1]["input_sources"]["predicted_days"] == (0 if spec.label == "V1" else 6)
    if spec.label != "V1":
        assert estimator.inputs[1].iloc[0].rolling_mean_7 == pytest.approx((15 + 16 + 17 + 18 + 19 + 20 + 30) / 7)
    bundle.manifest["training_cutoff"] = "2020-01-21"
    with pytest.raises(DemandError, match="past requested"):
        forecast_demand(bundle, snapshot, horizon(snapshot, cutoff), cutoff)


def test_feature_values_never_read_target_or_later_labels(snapshot_factory):
    original = snapshot_factory()
    changed = snapshot_factory(changes={i: {"target_guests": 1000000} for i in range(20, 100)})
    for version, spec in FEATURE_SPECS.items():
        a, b = build_features(original, version), build_features(changed, version)
        assert a.iloc[20][list(spec.names)].tolist() == b.iloc[20][list(spec.names)].tolist()


def test_controlled_subset_is_validated_and_encoder_fits_subset_only(snapshot_factory, comparison_config, tmp_path):
    snapshot = snapshot_factory()
    config = {**comparison_config, "feature_version": "demand-weekly-v1"}
    frame = build_features(snapshot, config["feature_version"])
    dates = list(frame.loc[frame.full_date.between(date(2020, 1, 15), date(2020, 1, 31)), "full_date"])
    bundle = fit_candidate("linear_regression", snapshot, frame, date(2020, 1, 1), date(2020, 2, 4),
                           config, "controlled", eligible_dates=dates)
    assert bundle.manifest["metadata"]["train_rows"] == 17
    categories = bundle.estimator.named_steps["preprocessing"].named_transformers_["calendar"].categories_
    assert list(categories[1]) == [1.0]  # February exists in the outer train interval, but not the fitted subset.
    saved = save_bundle(bundle, tmp_path / "bundle")
    assert load_bundle(saved).estimator.n_features_in_ == 4
    envelope = json.loads((saved / "manifest.json").read_text())
    envelope["manifest"]["feature_version"] = "demand-v1"
    envelope["manifest_sha256"] = digest(envelope["manifest"])
    (saved / "manifest.json").write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(DemandError, match="schema"):
        load_bundle(saved)
    with pytest.raises(DemandError, match="only eligible training"):
        fit_candidate("linear_regression", snapshot, frame, date(2020, 1, 1), date(2020, 2, 4), config,
                      "bad", eligible_dates=[date(2020, 2, 5)])


def test_funnel_incremental_and_overlapping_counts_reconcile(snapshot_factory, comparison_config):
    snapshot = snapshot_factory(changes={10: {"target_guests": None, "guest_data_status": "PARTIAL"}})
    frames = {spec.label: build_features(snapshot, spec.version) for spec in FEATURE_SPECS.values()}
    partition = filtering_analysis(snapshot, frames, comparison_config)["partitions"]["train"]
    assert [s["remaining"] for s in partition["stages"]] == [34, 26, 20, 10]
    assert sum(s["newly_excluded"] for s in partition["stages"]) + 10 == 35
    assert sum(r["days"] for r in partition["exclusive_combinations"]) == 35
    assert partition["stages"][1]["examples"][0]["unavailable_history"]


def test_selection_uses_common_validation_and_stability_gate_only():
    policy = {"min_relative_mae_improvement": .01, "require_nonoverlapping_mae_improvement": True}
    baseline = {"candidate_id": "baseline", "version": "Baseline", "feature_version": "demand-weekly-v1",
                "model_name": "seasonal_naive", "common_validation": {"mae": 10, "rmse": 11, "nonoverlapping": {"mae": 10}}}
    reg = {"candidate_id": "V1_linear", "version": "V1", "feature_version": "demand-weekly-v1",
           "model_name": "linear_regression", "common_validation": {"mae": 9, "rmse": 10, "nonoverlapping": {"mae": 9}},
           "version_validation": {"mae": 10000}, "test": {"mae": 1000000}}
    assert select_strategy([baseline, reg], policy)["candidate_id"] == "V1_linear"
    reg["test"]["mae"] = 0
    reg["version_validation"]["mae"] = 0
    assert select_strategy([baseline, reg], policy)["candidate_id"] == "V1_linear"
    reg["common_validation"]["nonoverlapping"]["mae"] = 11
    assert select_strategy([baseline, reg], policy)["candidate_id"] == "baseline"


def test_full_comparison_controlled_fits_and_test_freeze(snapshot_factory, comparison_config, tmp_path):
    import ml.demand_forecast.comparison as comparison
    snapshot = snapshot_factory()
    settings = load_settings()
    settings["expected_training_rows"] = {}
    output = tmp_path / "comparison"
    evaluate = comparison.evaluate_bundle
    test_calls = []

    def checked_evaluate(bundle, data, origins):
        if origins and min(origins) >= "2020-02-18":
            assert (output / "selection.json").is_file()
            test_calls.append(bundle.manifest["model_name"])
        return evaluate(bundle, data, origins)

    with patch.object(comparison, "evaluate_bundle", side_effect=checked_evaluate):
        result = run_feature_comparison(snapshot, comparison_config, output, settings=settings)
    assert result["status"] == "completed", result
    assert len(result["comparison"]) == 10 and len(result["controlled"]) == 18
    assert sum(not r["reused_primary_fit"] for r in result["controlled"]) == 9
    assert all(r["reload_verified"] for r in result["comparison"])
    assert all(r["common_validation"]["origins"] == 8 for r in result["comparison"])
    assert len(test_calls) == (1 if result["selection"]["version"] == "Baseline" else 2)
    assert result["selection"]["test_used_for_selection"] is False
    frozen = json.loads((output / "frozen_plan.json").read_text())
    expected = frozen.pop("plan_sha256")
    assert expected == digest(frozen)
    selected = load_bundle(output / "bundles/selected")
    assert selected.manifest["training_cutoff"] == "2020-02-18"
    assert result["demo_forecast_status"] == "ok"
    generate_report(output)
    assert (output / "charts/filtering_funnel.png").is_file()
    assert "synthetic_fixture" in (output / "report.md").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        run_feature_comparison(snapshot, comparison_config, output, settings=settings)


def test_candidate_failure_stops_selection_and_test(snapshot_factory, comparison_config, tmp_path):
    import ml.demand_forecast.comparison as comparison
    settings = load_settings()
    settings.update(expected_training_rows={}, controlled_analysis=False)
    real_fit = comparison.fit_candidate

    def failing(model, *args, **kwargs):
        if model == "xgboost":
            raise ValueError("deterministic fixture failure")
        return real_fit(model, *args, **kwargs)

    output = tmp_path / "incomplete"
    with patch.object(comparison, "fit_candidate", side_effect=failing):
        result = run_feature_comparison(snapshot_factory(), comparison_config, output, settings=settings)
    assert result["status"] == "incomplete" and result["reason_code"] == "MODEL_SELECTION_INCOMPLETE"
    assert not (output / "selection.json").exists()
    assert all(r["test_status"] == "not_evaluated" for r in result["comparison"])


def test_comparison_cli_preserves_quality_gate_and_rejects_fixture(snapshot_factory, tmp_path):
    error = DemandError("QUALITY_FAILED", "fixture source failed")
    with patch.object(compare_demand_features, "extract_snapshot", side_effect=error), \
         patch.object(compare_demand_features, "run_feature_comparison") as run:
        assert compare_demand_features.main(["--output-dir", str(tmp_path / "failed")]) == 1
    run.assert_not_called()
    saved = tmp_path / "fixture.json"
    save_snapshot(snapshot_factory(), saved)
    assert compare_demand_features.main(["--snapshot", str(saved), "--output-dir", str(tmp_path / "fixture")]) == 1
    failure = json.loads((tmp_path / "fixture/failure.json").read_text())
    assert failure["error_code"] == "FIXTURE_NOT_OFFICIAL"
