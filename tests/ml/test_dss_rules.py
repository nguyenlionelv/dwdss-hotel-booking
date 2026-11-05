from dataclasses import asdict, replace
from datetime import date, timedelta
from math import sqrt

import pytest

from ml.demand_forecast.contracts import DemandError, ForecastResult
from ml.demand_forecast.data import make_snapshot
from ml.demand_forecast.dss import ACTIONS, apply_demand_rules


def prediction(history, cutoff, values=None):
    values = [20.0] * 7 if values is None else values
    generated = "2026-11-05T00:00:00+00:00"
    points = tuple({"as_of_date": str(cutoff), "forecast_date": str(cutoff + timedelta(days=i)),
                    "horizon": i, "predicted_guest_count": value, "model_version": "synthetic-rules",
                    "generated_at": generated, "input_sources": {"actual_days": 1, "predicted_days": 0}}
                   for i, value in enumerate(values, 1))
    return ForecastResult("ok", str(cutoff), "synthetic-rules", history.data_version, generated, points,
                          source_checksums=dict(history.source_checksums))


def test_population_thresholds_and_strict_full_precision_boundaries(snapshot_factory):
    history = snapshot_factory(count=56, changes={i: {"target_guests": 10 if i % 2 == 0 else 30} for i in range(56)})
    cutoff = history.rows[-1].full_date
    # Independently: 28 tens + 28 thirties => mean=20, population variance=100.
    values = [40.0, 20.0, 0.0, 30.0, 10.0, 30.000000001, 9.999999999]
    result = apply_demand_rules(history, cutoff, prediction(history, cutoff, values))
    assert result.status == "OK" and result.reason_codes == ()
    assert result.threshold_rule["mean_guests_8w"] == 20
    assert result.threshold_rule["std_guests_8w"] == 10
    assert result.threshold_rule["high_threshold"] == 30
    assert result.threshold_rule["low_threshold"] == 10
    assert result.threshold_rule["std_ddof"] == 0
    assert result.threshold_rule["complete_days_available"] == 56
    assert [r["demand_level"] for r in result.forecasts] == ["HIGH", "NORMAL", "LOW", "NORMAL", "NORMAL", "HIGH", "LOW"]
    assert [r["predicted_guest_count"] for r in result.forecasts] == values
    assert all(r["recommended_action"] == ACTIONS[r["demand_level"]] for r in result.forecasts)


def test_zero_population_std(snapshot_factory):
    history = snapshot_factory(count=56, changes={i: {"target_guests": 10} for i in range(56)})
    cutoff = history.rows[-1].full_date
    result = apply_demand_rules(history, cutoff, prediction(history, cutoff, [9.9, 10, 10.1, 10, 10, 10, 10]))
    assert result.threshold_rule["std_guests_8w"] == 0
    assert result.threshold_rule["high_threshold"] == result.threshold_rule["low_threshold"] == 10
    assert [r["demand_level"] for r in result.forecasts[:3]] == ["LOW", "NORMAL", "HIGH"]


def test_low_threshold_is_clamped_at_zero(snapshot_factory):
    history = snapshot_factory(count=56, changes={i: {"target_guests": 56 if i == 55 else 0} for i in range(56)})
    cutoff = history.rows[-1].full_date
    result = apply_demand_rules(history, cutoff, prediction(history, cutoff, [0.0] * 7))
    # Independently: mean=1; E[X^2]=56 => population variance=55.
    assert result.threshold_rule["mean_guests_8w"] == 1
    assert result.threshold_rule["std_guests_8w"] == pytest.approx(sqrt(55))
    assert result.threshold_rule["low_threshold"] == 0
    assert all(r["demand_level"] == "NORMAL" for r in result.forecasts)


@pytest.mark.parametrize("count,available", [(55, 55), (56, 56), (57, 56)])
def test_exactly_56_inclusive_calendar_days(snapshot_factory, count, available):
    history = snapshot_factory(count=count)
    cutoff = history.rows[-1].full_date
    result = apply_demand_rules(history, cutoff, prediction(history, cutoff))
    assert result.threshold_rule["window_start"] == str(cutoff - timedelta(days=55))
    assert result.threshold_rule["window_end"] == str(cutoff)
    assert result.threshold_rule["complete_days_available"] == available
    assert result.status == ("OK" if count >= 56 else "INSUFFICIENT_HISTORY")


@pytest.mark.parametrize("status,code", [("PARTIAL", "PARTIAL_HISTORY_TARGET"), ("MISSING", "MISSING_HISTORY_DAY"), ("UNKNOWN", "UNKNOWN_HISTORY_TARGET")])
def test_incomplete_day_is_not_replaced_by_older_history(snapshot_factory, status, code):
    history = snapshot_factory(count=90, changes={60: {"target_guests": None, "guest_data_status": status}})
    cutoff = history.rows[-1].full_date
    result = apply_demand_rules(history, cutoff, prediction(history, cutoff))
    assert result.status == "INSUFFICIENT_HISTORY"
    assert result.threshold_rule["complete_days_available"] == 55
    assert result.reason_codes == (code,)
    assert result.threshold_rule["unavailable_days"] == [{"full_date": str(history.rows[60].full_date), "reason_code": code}]
    for key in ["mean_guests_8w", "std_guests_8w", "low_threshold", "high_threshold"]:
        assert result.threshold_rule[key] is None
    assert len(result.forecasts) == 7
    assert all(r["demand_level"] == "INSUFFICIENT_HISTORY" for r in result.forecasts)


def test_missing_date_preserves_calendar_gap(snapshot_factory):
    original = snapshot_factory(count=80)
    raw = asdict(original)
    raw.pop("snapshot_hash")
    raw["rows"] = [r for i, r in enumerate(raw["rows"]) if i != 50]
    history = make_snapshot(**raw)
    cutoff = history.rows[-1].full_date
    result = apply_demand_rules(history, cutoff, prediction(history, cutoff))
    assert len(history.rows) == 80
    assert result.threshold_rule["complete_days_available"] == 55
    assert result.threshold_rule["unavailable_days"][0]["full_date"] == str(original.rows[50].full_date)


def test_only_cutoff_window_contributes_no_future_or_older_values(snapshot_factory):
    history = snapshot_factory(count=100)
    cutoff = date(2020, 3, 20)  # Day index 79; required targets are integers 25..80.
    changed = snapshot_factory(count=100, changes={i: {"target_guests": 999999} for i in [*range(24), *range(80, 100)]})
    first = apply_demand_rules(history, cutoff, prediction(history, cutoff))
    second = apply_demand_rules(changed, cutoff, prediction(changed, cutoff))
    assert first.threshold_rule == second.threshold_rule
    assert first.forecasts == second.forecasts
    assert first.threshold_rule["mean_guests_8w"] == 52.5
    assert first.threshold_rule["std_guests_8w"] == pytest.approx(sqrt((56 ** 2 - 1) / 12))


def test_version_source_and_cutoff_mismatches_fail(snapshot_factory):
    history = snapshot_factory(count=56)
    cutoff = history.rows[-1].full_date
    valid = prediction(history, cutoff)
    for invalid in [replace(valid, data_version="stale"), replace(valid, source_checksums={}),
                    replace(valid, source_checksums={**history.source_checksums, "booking": "d" * 64})]:
        with pytest.raises(DemandError) as caught:
            apply_demand_rules(history, cutoff, invalid)
        assert caught.value.code == "STALE_DATA"
    with pytest.raises(DemandError) as caught:
        apply_demand_rules(history, cutoff - timedelta(days=1), valid)
    assert caught.value.code == "INVALID_CUTOFF"


@pytest.mark.parametrize("mutation", ["count", "order", "model", "negative", "nonfinite"])
def test_invalid_forecast_is_not_classified(snapshot_factory, mutation):
    history = snapshot_factory(count=56)
    cutoff = history.rows[-1].full_date
    valid = prediction(history, cutoff)
    rows = [dict(r) for r in valid.forecasts]
    if mutation == "count": rows.pop()
    if mutation == "order": rows.reverse()
    if mutation == "model": rows[0]["model_version"] = "other"
    if mutation == "negative": rows[0]["predicted_guest_count"] = -1
    if mutation == "nonfinite": rows[0]["predicted_guest_count"] = float("nan")
    with pytest.raises(DemandError):
        apply_demand_rules(history, cutoff, replace(valid, forecasts=tuple(rows)))


def test_mutated_history_is_rejected(snapshot_factory):
    history = snapshot_factory(count=56)
    cutoff = history.rows[-1].full_date
    with pytest.raises(DemandError) as caught:
        apply_demand_rules(replace(history, data_version="changed"), cutoff, prediction(history, cutoff))
    assert caught.value.code == "CORRUPT_SNAPSHOT"
