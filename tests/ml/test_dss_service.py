from copy import deepcopy
from datetime import date
import json
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker
import pytest

from ml.demand_forecast.artifacts import make_bundle, save_bundle
from ml.demand_forecast.contracts import DemandError
from ml.demand_forecast.data import save_snapshot
from ml.demand_forecast.dss_fixtures import synthetic_classification_example
from ml.demand_forecast.service import DemandForecastService, forecast_with_dss, get_demand_forecast
from scripts import forecast_dss

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "docs/ml/demand_dss_response.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def test_available_forecast_with_unavailable_dss_serializes(snapshot_factory):
    history = snapshot_factory(count=55)
    cutoff = history.rows[-1].full_date
    bundle = make_bundle(history, "seasonal_naive", cutoff, "synthetic-baseline", feature_version="demand-weekly-v1")
    payload = forecast_with_dss(bundle, history, cutoff)
    assert payload["forecast_status"] == "ok" and payload["dss_status"] == "INSUFFICIENT_HISTORY"
    assert len(payload["forecasts"]) == 7
    assert payload["dss_threshold_rule"]["complete_days_available"] == 55
    assert payload["summary"]["total_predicted_guests_7d"] == sum(range(49, 56))
    assert payload["provenance"]["source_kind"] == "synthetic_fixture"
    VALIDATOR.validate(json.loads(json.dumps(payload, allow_nan=False)))
    invalid = deepcopy(payload)
    invalid["dss_threshold_rule"]["high_threshold"] = 100
    assert not VALIDATOR.is_valid(invalid)


def test_forecast_unavailable_is_distinct_from_dss_unavailable(snapshot_factory):
    history = snapshot_factory(count=60, changes={59: {"target_guests": None, "guest_data_status": "PARTIAL"}})
    cutoff = history.rows[-1].full_date
    payload = forecast_with_dss(make_bundle(history, "seasonal_naive", cutoff, "fixture"), history, cutoff)
    assert payload["forecast_status"] == "unavailable"
    assert payload["forecast_reason_code"] == "INSUFFICIENT_HISTORY"
    assert payload["dss_status"] == "FORECAST_UNAVAILABLE"
    assert payload["forecasts"] == [] and payload["summary"] is None
    VALIDATOR.validate(payload)


def test_hand_calculated_synthetic_fixture_is_labeled_and_schema_valid():
    first = synthetic_classification_example()
    second = synthetic_classification_example()
    VALIDATOR.validate(first)
    assert first["provenance"]["source_kind"] == "synthetic_fixture"
    assert first["data_version"] == "synthetic-dss-v1"
    assert first["dss_status"] == "OK"
    assert first["dss_threshold_rule"]["mean_guests_8w"] == 20
    assert first["dss_threshold_rule"]["std_guests_8w"] == 10
    assert first["summary"]["total_predicted_guests_7d"] == 129
    assert [p["demand_level"] for p in first["forecasts"]] == ["NORMAL", "NORMAL", "HIGH", "NORMAL", "LOW", "LOW", "NORMAL"]
    assert [p["predicted_guest_count"] for p in first["forecasts"]] == [p["predicted_guest_count"] for p in second["forecasts"]]


def test_service_ignores_future_actuals_and_rejects_stale_bundle(snapshot_factory):
    history = snapshot_factory(count=100)
    changed = snapshot_factory(count=100, changes={i: {"target_guests": 999999} for i in range(56, 100)})
    cutoff = date(2020, 2, 25)
    bundle = make_bundle(history, "seasonal_naive", cutoff, "fixture")
    first, second = (forecast_with_dss(bundle, data, cutoff) for data in [history, changed])
    assert first["dss_threshold_rule"] == second["dss_threshold_rule"]
    assert [p["predicted_guest_count"] for p in first["forecasts"]] == [p["predicted_guest_count"] for p in second["forecasts"]]
    bundle.manifest["data_version"] = "stale"
    with pytest.raises(DemandError) as caught:
        forecast_with_dss(bundle, history, cutoff)
    assert caught.value.code == "STALE_DATA"


def test_peak_ties_and_model_filter_no_silent_fallback(snapshot_factory):
    history = snapshot_factory(count=56, changes={i: {"target_guests": 10} for i in range(56)})
    cutoff = history.rows[-1].full_date
    bundle = make_bundle(history, "seasonal_naive", cutoff, "fixture")
    provider_calls = []
    service = DemandForecastService(bundle, lambda: provider_calls.append(True) or history)
    with pytest.raises(DemandError) as caught:
        service.forecast(cutoff, model_name="xgboost")
    assert caught.value.code == "MODEL_NOT_AVAILABLE" and provider_calls == []
    with pytest.raises(DemandError):
        service.forecast("2020-02-30")
    assert provider_calls == []
    payload = service.forecast(cutoff, model_name="seasonal_naive")
    assert len(provider_calls) == 1 and len(payload["summary"]["peak_forecast_dates"]) == 7
    VALIDATOR.validate(payload)


def test_service_loads_once_and_never_fits(snapshot_factory, tmp_path):
    history = snapshot_factory(count=60)
    cutoff = history.rows[-1].full_date
    saved = save_bundle(make_bundle(history, "seasonal_naive", cutoff, "fixture"), tmp_path / "bundle")
    with patch("ml.demand_forecast.train.fit_candidate", side_effect=AssertionError("must not train")), \
         patch("ml.demand_forecast.service.load_bundle", wraps=__import__("ml.demand_forecast.artifacts", fromlist=["load_bundle"]).load_bundle) as load:
        service = DemandForecastService.from_bundle(saved, lambda: history)
        assert service.forecast(cutoff)["forecast_status"] == "ok"
        assert service.forecast(cutoff)["forecast_status"] == "ok"
        assert load.call_count == 1
    assert get_demand_forecast(cutoff, bundle_path=saved, snapshot=history)["model_version"] == "fixture"


def test_live_provider_errors_propagate_without_mock(snapshot_factory, tmp_path):
    history = snapshot_factory(count=60)
    saved = save_bundle(make_bundle(history, "seasonal_naive", "2020-01-01", "fixture"), tmp_path / "bundle")
    with patch("ml.demand_forecast.service.extract_snapshot", side_effect=DemandError("QUALITY_FAILED", "source gate failed")):
        with pytest.raises(DemandError) as caught:
            get_demand_forecast("2020-02-29", bundle_path=saved)
    assert caught.value.code == "QUALITY_FAILED"


def test_dss_cli_errors_and_success_with_insufficient_history(snapshot_factory, tmp_path, capsys):
    history = snapshot_factory(count=55)
    bundle = tmp_path / "bundle"
    save_bundle(make_bundle(history, "seasonal_naive", "2020-01-01", "fixture"), bundle)
    assert forecast_dss.main(["--as-of-date", "2020-02-24", "--bundle", str(tmp_path / "missing")]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "MISSING_MODEL"
    snapshot_path = tmp_path / "synthetic.json"
    save_snapshot(history, snapshot_path)
    assert forecast_dss.main(["--as-of-date", "2020-02-24", "--bundle", str(bundle), "--snapshot", str(snapshot_path)]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "FIXTURE_NOT_OFFICIAL"
    with patch("ml.demand_forecast.service.extract_snapshot", return_value=history):
        assert forecast_dss.main(["--as-of-date", "2020-02-24", "--bundle", str(bundle), "--output", str(tmp_path / "result.json")]) == 0
    payload = json.loads((tmp_path / "result.json").read_text())
    assert payload["forecast_status"] == "ok" and payload["dss_status"] == "INSUFFICIENT_HISTORY"
    VALIDATOR.validate(payload)
