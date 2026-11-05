"""One feature definition for offline training and recursive inference."""
from datetime import timedelta
import pandas as pd
from .contracts import FEATURE_VERSION, feature_spec

def feature_values(day, state, feature_version=FEATURE_VERSION):
    """State holds COMPLETE actuals or isolated recursive predictions, never imputation."""
    spec = feature_spec(feature_version)
    values = {"day_of_week": float(day.isoweekday()), "month": float(day.month),
              "is_weekend": float(day.weekday() >= 5)}
    reasons = []
    for lag in (1, 7):
        if f"lag_{lag}" not in spec.names:
            continue
        value = state.get(day - timedelta(days=lag))
        values[f"lag_{lag}"] = value
        if value is None:
            reasons.append(f"LAG_{lag}_UNAVAILABLE")
    for window in (7, 14):
        if f"rolling_mean_{window}" not in spec.names:
            continue
        history = [state.get(day - timedelta(days=i)) for i in range(1, window + 1)]
        ready = all(value is not None for value in history)
        values[f"rolling_mean_{window}"] = sum(history) / window if ready else None
        if not ready:
            reasons.append(f"ROLLING_{window}_INCOMPLETE")
    return {name: values[name] for name in spec.names}, reasons

def build_features(snapshot, feature_version=FEATURE_VERSION):
    spec = feature_spec(feature_version)
    state = {row.full_date: row.target_guests for row in snapshot.rows if row.guest_data_status == "COMPLETE"}
    records = []
    for row in snapshot.rows:
        values, reasons = feature_values(row.full_date, state, spec.version)
        target_ready = row.guest_data_status == "COMPLETE" and row.target_guests is not None
        records.append({"full_date": row.full_date, "date_key": int(row.full_date.strftime("%Y%m%d")),
                        "data_version": snapshot.data_version, "feature_version": spec.version,
                        "target_guests": row.target_guests, "guest_data_status": row.guest_data_status,
                        **values, "feature_ready": not reasons, "target_ready": target_ready,
                        "train_ready": not reasons and target_ready,
                        "reason_codes": reasons + ([] if target_ready else ["TARGET_NOT_COMPLETE"])})
    frame = pd.DataFrame.from_records(records)
    frame.attrs.update(data_version=snapshot.data_version, feature_version=spec.version,
                       snapshot_hash=snapshot.snapshot_hash)
    return frame
