"""Framework-independent forecast-to-DSS orchestration; no training or mocked fallback."""
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from .artifacts import load_bundle
from .contracts import DemandError, DemandSnapshot, HORIZON, ModelBundle, local_date
from .data import extract_snapshot
from .dss import apply_demand_rules, validate_history
from .predict import forecast_demand

RESPONSE_VERSION = "demand-dss-v1"


def forecast_with_dss(
    bundle: ModelBundle,
    history: DemandSnapshot,
    as_of_date: date | datetime | str,
    *,
    model_name: str | None = None,
) -> dict:
    """Predict T+1…T+7 and classify from T−55…T, preserving independent statuses."""
    cutoff = local_date(as_of_date)
    if model_name is not None and model_name != bundle.manifest["model_name"]:
        raise DemandError("MODEL_NOT_AVAILABLE", "Requested model is not the configured accepted bundle")
    validate_history(history)
    calendar = [day for day in history.calendar if cutoff < day.full_date <= cutoff + timedelta(days=HORIZON)]
    forecast = forecast_demand(bundle, history, calendar, cutoff)
    dss = apply_demand_rules(history, cutoff, forecast)
    summary = None
    if dss.forecasts:
        peak = max(point["predicted_guest_count"] for point in dss.forecasts)
        summary = {
            "total_predicted_guests_7d": sum(point["predicted_guest_count"] for point in dss.forecasts),
            "peak_predicted_guest_count": peak,
            "peak_forecast_dates": [point["forecast_date"] for point in dss.forecasts if point["predicted_guest_count"] == peak],
        }
    return {
        "schema_version": RESPONSE_VERSION, "hotel_name": forecast.hotel_name, "timezone": forecast.timezone,
        "as_of_date": forecast.as_of_date, "horizon": HORIZON,
        "model_name": bundle.manifest["model_name"], "model_version": forecast.model_version,
        "feature_version": forecast.feature_version, "data_version": forecast.data_version,
        "generated_at": forecast.generated_at, "forecast_status": forecast.status,
        "forecast_reason_code": forecast.reason_code, "forecast_message": forecast.message,
        "dss_status": dss.status, "dss_reason_codes": list(dss.reason_codes),
        "dss_threshold_rule": dss.threshold_rule, "forecasts": list(dss.forecasts), "summary": summary,
        "provenance": {"source_kind": history.source_kind, "source_checksums": dict(history.source_checksums),
                       "snapshot_hash": history.snapshot_hash, "extracted_at": history.extracted_at,
                       "dw_run_id": history.run_id, "quality_passed": True},
    }


class DemandForecastService:
    """Load a trusted bundle once; inject a validated snapshot provider per request."""

    def __init__(self, bundle: ModelBundle, history_provider: Callable[[], DemandSnapshot]):
        self.bundle = bundle
        self.history_provider = history_provider

    @classmethod
    def from_bundle(cls, bundle_path: str | Path, history_provider: Callable[[], DemandSnapshot]):
        return cls(load_bundle(bundle_path), history_provider)

    def forecast(self, as_of_date: date | datetime | str, *, model_name: str | None = None) -> dict:
        cutoff = local_date(as_of_date)
        if model_name is not None and model_name != self.bundle.manifest["model_name"]:
            raise DemandError("MODEL_NOT_AVAILABLE", "Requested model is not the configured accepted bundle")
        return forecast_with_dss(self.bundle, self.history_provider(), cutoff, model_name=model_name)


def get_demand_forecast(
    as_of_date: date | datetime | str,
    *,
    bundle_path: str | Path,
    snapshot: DemandSnapshot | None = None,
    dw_config: str | Path | None = None,
    dbname: str | None = None,
    model_name: str | None = None,
) -> dict:
    """Convenience entry point; a fresh quality-gated DB read is used when snapshot is omitted."""
    provider = (lambda: snapshot) if snapshot is not None else (lambda: extract_snapshot(dw_config, dbname))
    return DemandForecastService.from_bundle(bundle_path, provider).forecast(as_of_date, model_name=model_name)
