"""Framework-independent demand forecast contracts; no fitting on import."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
import math
import re
from typing import Any
from zoneinfo import ZoneInfo

FEATURE_VERSION = "demand-v1"
FEATURE_NAMES = ("lag_1", "lag_7", "rolling_mean_7", "rolling_mean_14", "day_of_week", "month", "is_weekend")
FEATURE_SCHEMA = [{"name": n, "dtype": "float64"} for n in FEATURE_NAMES]
HORIZON = 7
BUSINESS_TIMEZONE = "Europe/Lisbon"
STATUSES = {"COMPLETE", "PARTIAL", "MISSING", "UNKNOWN"}

class DemandError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)

@dataclass(frozen=True)
class FeatureSpec:
    label: str
    version: str
    names: tuple[str, ...]
    forecast_history_days: int

    @property
    def schema(self):
        return [{"name": name, "dtype": "float64"} for name in self.names]


# demand-v1 and the legacy constants remain V3 for accepted-bundle compatibility.
CALENDAR_FEATURES = ("day_of_week", "month", "is_weekend")
FEATURE_SPECS = {
    "demand-weekly-v1": FeatureSpec("V1", "demand-weekly-v1", ("lag_7", *CALENDAR_FEATURES), 7),
    "demand-short-v1": FeatureSpec("V2", "demand-short-v1", ("lag_1", "lag_7", "rolling_mean_7", *CALENDAR_FEATURES), 7),
    FEATURE_VERSION: FeatureSpec("V3", FEATURE_VERSION, FEATURE_NAMES, 14),
}


def feature_spec(version=FEATURE_VERSION):
    if not isinstance(version, str) or version not in FEATURE_SPECS:
        raise DemandError("INCOMPATIBLE_FEATURES", "Unsupported bundle feature version/schema")
    return FEATURE_SPECS[version]


def local_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise DemandError("INVALID_DATE", "Timestamp must include a timezone")
        return value.astimezone(ZoneInfo(BUSINESS_TIMEZONE)).date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise DemandError("INVALID_DATE", "Expected a valid ISO business date")

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def nonnegative(value: Any, *, integer=False) -> float:
    if isinstance(value, bool):
        raise DemandError("INVALID_VALUE", "Boolean is not demand")
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise DemandError("INVALID_VALUE", "Demand must be numeric") from exc
    if not math.isfinite(number) or number < 0 or (integer and not number.is_integer()):
        raise DemandError("INVALID_VALUE", "Demand must be finite, nonnegative, and integral for actuals")
    return number

@dataclass(frozen=True)
class DailyTarget:
    full_date: date
    target_guests: float | None
    guest_data_status: str

@dataclass(frozen=True)
class CalendarDay:
    full_date: date
    day_of_week: int
    month: int
    is_weekend: bool
    data_version: str

    @classmethod
    def from_date(cls, day, data_version):
        return cls(day, day.isoweekday(), day.month, day.weekday() >= 5, data_version)

@dataclass(frozen=True)
class DemandSnapshot:
    rows: tuple[DailyTarget, ...]
    data_version: str
    extracted_at: str
    source_checksums: dict[str, str]
    quality: dict
    calendar: tuple[CalendarDay, ...]
    source_kind: str = "postgresql"
    run_id: str = ""
    snapshot_hash: str = ""

@dataclass
class ModelBundle:
    manifest: dict
    estimator: Any = None

@dataclass(frozen=True)
class ForecastResult:
    status: str
    as_of_date: str
    model_version: str
    data_version: str
    generated_at: str
    forecasts: tuple[dict, ...] = ()
    reason_code: str | None = None
    message: str | None = None
    feature_version: str = FEATURE_VERSION
    horizon: int = HORIZON
    hotel_name: str = "City Hotel"
    timezone: str = BUSINESS_TIMEZONE
    source_checksums: dict[str, str] = field(default_factory=dict)

    def to_dict(self):
        result = asdict(self)
        if self.forecasts:
            peak = max(r["predicted_guest_count"] for r in self.forecasts)
            result["summary"] = {"total_predicted_guests_7d": sum(r["predicted_guest_count"] for r in self.forecasts),
                                 "peak_forecast_dates": [r["forecast_date"] for r in self.forecasts if r["predicted_guest_count"] == peak]}
        return result
