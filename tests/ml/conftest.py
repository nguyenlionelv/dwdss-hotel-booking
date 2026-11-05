from datetime import date, timedelta
import pytest
from ml.demand_forecast.contracts import CalendarDay, FEATURE_SCHEMA, FEATURE_VERSION, ModelBundle
from ml.demand_forecast.data import make_snapshot

@pytest.fixture
def snapshot_factory():
    def factory(count=100, start=date(2020, 1, 1), changes=None):
        changes = changes or {}
        rows = []
        for i in range(count):
            day = start + timedelta(days=i)
            row = {"full_date": day, "target_guests": float(i + 1), "guest_data_status": "COMPLETE"}
            row.update(changes.get(i, {}))
            rows.append(row)
        return make_snapshot(rows, data_version="fixture-v1", extracted_at="2026-11-04T00:00:00+00:00",
                             source_checksums={s: c*64 for s,c in zip(("booking","holiday","weather"),"abc")},
                             quality={"passed":True,"dw_quality":{"passed":True},"data_version":"fixture-v1","run_id":"fixture"},
                             calendar=[CalendarDay.from_date(start + timedelta(days=i), "fixture-v1") for i in range(count+7)],
                             source_kind="synthetic_fixture", run_id="fixture")
    return factory

@pytest.fixture
def bundle_factory():
    def factory(snapshot, name="seasonal_naive", estimator=None, cutoff="2020-01-01"):
        return ModelBundle({"model_name":name,"model_version":"test-v1","data_version":snapshot.data_version,
                            "source_checksums":snapshot.source_checksums,"feature_version":FEATURE_VERSION,
                            "feature_schema":FEATURE_SCHEMA,"training_cutoff":cutoff}, estimator)
    return factory
