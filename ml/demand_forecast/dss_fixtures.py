"""Explicit synthetic DSS example only: never used as an inference fallback."""
from datetime import date, timedelta

from .artifacts import make_bundle
from .contracts import CalendarDay
from .data import make_snapshot
from .service import forecast_with_dss


class SyntheticCalendarEstimator:
    """Hand-specified predictions test the rule boundary; this is not a fitted model."""
    def predict(self, frame):
        by_weekday = {1: 0.0, 2: 10.0, 3: 20.0, 4: 30.0, 5: 40.0, 6: 19.5, 7: 9.5}
        return [by_weekday[int(frame.iloc[0].day_of_week)]]


def synthetic_classification_example() -> dict:
    start, version = date(2020, 1, 1), "synthetic-dss-v1"
    rows = [{"full_date": start + timedelta(days=i), "target_guests": 10 if i % 2 == 0 else 30,
             "guest_data_status": "COMPLETE"} for i in range(56)]
    history = make_snapshot(rows, data_version=version, extracted_at="2026-11-05T00:00:00+00:00",
        source_checksums={"booking": "a" * 64, "holiday": "b" * 64, "weather": "c" * 64},
        quality={"passed": True, "dw_quality": {"passed": True}, "data_version": version, "run_id": "synthetic-dss"},
        calendar=[CalendarDay.from_date(start + timedelta(days=i), version) for i in range(63)],
        source_kind="synthetic_fixture", run_id="synthetic-dss")
    cutoff = start + timedelta(days=55)
    bundle = make_bundle(history, "linear_regression", cutoff, "synthetic-calendar-rule-example",
                         feature_version="demand-weekly-v1", estimator=SyntheticCalendarEstimator(),
                         metadata={"synthetic_only": True, "fitted": False})
    return forecast_with_dss(bundle, history, cutoff)
