"""Seven-day inference independent of database/framework lifecycles."""
from datetime import timedelta
import math
import pandas as pd
from .baseline import seasonal_naive
from .contracts import (HORIZON, DemandError, ForecastResult, feature_spec, local_date, utc_now)
from .data import validate_calendar
from .features import feature_values

def forecast_demand(bundle, history, future_calendar, as_of_date):
    cutoff = local_date(as_of_date)
    manifest = bundle.manifest
    spec = feature_spec(manifest.get("feature_version"))
    if manifest.get("feature_schema") != spec.schema:
        raise DemandError("INCOMPATIBLE_FEATURES", "Unsupported bundle feature version/schema")
    if (manifest.get("data_version") != history.data_version
            or manifest.get("source_checksums") != history.source_checksums):
        raise DemandError("STALE_DATA", "Bundle and history source/data versions differ")
    model_name = manifest["model_name"]
    if model_name not in {"seasonal_naive", "linear_regression", "random_forest", "xgboost"}:
        raise DemandError("UNKNOWN_MODEL", "Unsupported demand model")
    if model_name != "seasonal_naive" and local_date(manifest["training_cutoff"]) > cutoff:
        raise DemandError("FUTURE_TRAINED_MODEL", "Training labels extend past requested cutoff")
    if model_name != "seasonal_naive" and bundle.estimator is None:
        raise DemandError("MISSING_MODEL", "Regression estimator unavailable")
    if cutoff not in {r.full_date for r in history.rows}:
        raise DemandError("INVALID_CUTOFF", "Cutoff must be in snapshot actual range")
    calendar = validate_calendar(future_calendar, history.data_version)
    expected = [cutoff + timedelta(days=h) for h in range(1, HORIZON + 1)]
    if [r.full_date for r in calendar] != expected:
        raise DemandError("INVALID_CALENDAR", "Exactly seven cutoff-relative horizon dates required")
    state = {r.full_date: r.target_guests for r in history.rows
             if r.full_date <= cutoff and r.guest_data_status == "COMPLETE"}
    generated_at, points = utc_now(), []
    try:
        naive = seasonal_naive(state, cutoff) if model_name == "seasonal_naive" else None
        for h, day in enumerate(expected, 1):
            values, reasons = feature_values(day, state, spec.version)
            if naive is None:
                if reasons:
                    raise DemandError("INSUFFICIENT_HISTORY", ", ".join(reasons))
                vector = pd.DataFrame([{n: values[n] for n in spec.names}], columns=list(spec.names))
                prediction = float(bundle.estimator.predict(vector)[0])
            else:
                prediction = naive[h - 1]
            if not math.isfinite(prediction):
                raise DemandError("INVALID_PREDICTION", "Estimator produced NaN or Infinity")
            prediction = max(0.0, prediction)
            points.append({"as_of_date": cutoff.isoformat(), "forecast_date": day.isoformat(),
                           "horizon": h, "predicted_guest_count": prediction,
                           "model_version": manifest["model_version"], "generated_at": generated_at,
                           "input_sources": {"actual_days": 1 if naive is not None or spec.label == "V1" else spec.forecast_history_days+1-h,
                                             "predicted_days": 0 if naive is not None or spec.label == "V1" else h-1}})
            state[day] = prediction
    except DemandError as exc:
        if exc.code != "INSUFFICIENT_HISTORY":
            raise
        return ForecastResult("unavailable", cutoff.isoformat(), manifest["model_version"],
                              history.data_version, generated_at, reason_code=exc.code, message=str(exc),
                              feature_version=spec.version, source_checksums=dict(manifest["source_checksums"]))
    return ForecastResult("ok", cutoff.isoformat(), manifest["model_version"],
                          history.data_version, generated_at, tuple(points), feature_version=spec.version,
                          source_checksums=dict(manifest["source_checksums"]))
