"""DSS-01: fixed 56-calendar-day population thresholds, independent of any web app."""
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from math import fsum
from statistics import pstdev

from .contracts import DemandError, DemandSnapshot, ForecastResult, HORIZON, local_date, nonnegative
from .data import digest, snapshot_payload

LOOKBACK_DAYS = 56
RULE_VERSION = "demand-dss-56d-v1"
ACTIONS = {
    "HIGH": "Review guest reception capacity, prepare housekeeping workload, and coordinate operational resources.",
    "NORMAL": "Maintain the current operational plan and monitor demand changes.",
    "LOW": "Review staff shift allocation and adjust preparation for lower expected demand.",
    "INSUFFICIENT_HISTORY": "Historical information is insufficient for reliable demand-level classification.",
}


@dataclass(frozen=True)
class DSSResult:
    status: str
    as_of_date: str
    data_version: str
    model_version: str
    threshold_rule: dict
    forecasts: tuple[dict, ...]
    reason_codes: tuple[str, ...] = ()
    rule_version: str = RULE_VERSION

    def to_dict(self):
        return asdict(self)


def validate_history(history: DemandSnapshot) -> None:
    if history.snapshot_hash != digest(snapshot_payload(history)):
        raise DemandError("CORRUPT_SNAPSHOT", "History changed after snapshot validation")
    quality = history.quality
    if quality.get("passed") is not True or quality.get("dw_quality", {}).get("passed") is not True:
        raise DemandError("QUALITY_FAILED", "A validated DW/Mart history snapshot is required")
    if str(quality.get("data_version")) != history.data_version or str(quality.get("run_id")) != history.run_id:
        raise DemandError("MIXED_VERSION", "History and quality evidence have different versions")


def apply_demand_rules(
    history: DemandSnapshot,
    as_of_date: date | datetime | str,
    predictions: ForecastResult,
) -> DSSResult:
    """Enrich a versioned forecast; incomplete reference history never removes valid points."""
    cutoff = local_date(as_of_date)
    validate_history(history)
    if predictions.data_version != history.data_version or predictions.source_checksums != history.source_checksums:
        raise DemandError("STALE_DATA", "Forecast and DSS history source/data versions differ")
    if predictions.as_of_date != cutoff.isoformat():
        raise DemandError("INVALID_CUTOFF", "Forecast and DSS cutoffs differ")
    if predictions.horizon != HORIZON or predictions.status not in {"ok", "unavailable"}:
        raise DemandError("INVALID_FORECAST", "Unsupported forecast status or horizon")

    indexed = {row.full_date: row for row in history.rows if row.full_date <= cutoff}
    first = cutoff - timedelta(days=LOOKBACK_DAYS - 1)
    unavailable, values = [], []
    for offset in range(LOOKBACK_DAYS):
        day = first + timedelta(days=offset)
        row = indexed.get(day)
        if row is None or row.guest_data_status == "MISSING":
            unavailable.append({"full_date": day.isoformat(), "reason_code": "MISSING_HISTORY_DAY"})
        elif row.guest_data_status != "COMPLETE":
            reason = "PARTIAL_HISTORY_TARGET" if row.guest_data_status == "PARTIAL" else "UNKNOWN_HISTORY_TARGET"
            unavailable.append({"full_date": day.isoformat(), "reason_code": reason})
        else:
            try:
                values.append(nonnegative(row.target_guests, integer=True))
            except DemandError:
                unavailable.append({"full_date": day.isoformat(), "reason_code": "INVALID_HISTORY_TARGET"})
    reasons = tuple(sorted({row["reason_code"] for row in unavailable}))
    thresholds = {
        "rule_version": RULE_VERSION, "window_start": first.isoformat(), "window_end": cutoff.isoformat(),
        "lookback_days_required": LOOKBACK_DAYS, "complete_days_available": len(values),
        "sufficient_history": not unavailable, "std_ddof": 0,
        "mean_guests_8w": None, "std_guests_8w": None, "high_threshold": None, "low_threshold": None,
        "unavailable_days": unavailable,
    }
    if predictions.status == "unavailable":
        if predictions.forecasts:
            raise DemandError("INVALID_FORECAST", "Unavailable forecast must not contain points")
        return DSSResult("FORECAST_UNAVAILABLE", cutoff.isoformat(), history.data_version,
                         predictions.model_version, thresholds, (), ("FORECAST_UNAVAILABLE", *reasons))
    if len(predictions.forecasts) != HORIZON:
        raise DemandError("INVALID_FORECAST", "Exactly seven chronological forecast points are required")
    if not unavailable:
        mean, std = fsum(values) / LOOKBACK_DAYS, pstdev(values)
        thresholds.update(mean_guests_8w=mean, std_guests_8w=std,
                          high_threshold=mean + std, low_threshold=max(0.0, mean - std))
    enriched = []
    for horizon, point in enumerate(predictions.forecasts, 1):
        expected = cutoff + timedelta(days=horizon)
        if (point.get("forecast_date") != expected.isoformat() or point.get("as_of_date") != cutoff.isoformat()
                or point.get("horizon") != horizon or point.get("model_version") != predictions.model_version
                or point.get("generated_at") != predictions.generated_at):
            raise DemandError("INVALID_FORECAST", "Forecast dates, order, or model metadata do not match")
        value = nonnegative(point.get("predicted_guest_count"))
        if unavailable:
            level = "INSUFFICIENT_HISTORY"
        elif value > thresholds["high_threshold"]:
            level = "HIGH"
        elif value < thresholds["low_threshold"]:
            level = "LOW"
        else:
            level = "NORMAL"
        enriched.append({**point, "predicted_guest_count": value,
                         "demand_level": level, "recommended_action": ACTIONS[level]})
    return DSSResult("INSUFFICIENT_HISTORY" if unavailable else "OK", cutoff.isoformat(), history.data_version,
                     predictions.model_version, thresholds, tuple(enriched), reasons)
