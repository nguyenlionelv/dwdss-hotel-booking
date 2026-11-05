from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
import math
import pytest
from ml.demand_forecast.baseline import seasonal_naive
from ml.demand_forecast.contracts import DemandError, local_date
from ml.demand_forecast.data import make_snapshot, normalize_rows, load_snapshot, save_snapshot
from ml.demand_forecast.features import build_features
from ml.demand_forecast.predict import forecast_demand

def calendar(snapshot, cutoff):
    return [r for r in snapshot.calendar if cutoff < r.full_date <= cutoff + timedelta(days=7)]

class LagPlusOne:
    def predict(self, x):
        return [x.iloc[0]["lag_1"] + 1]

class Constant:
    def __init__(self, value): self.value = value
    def predict(self, x): return [self.value]

def test_hand_calculated_features(snapshot_factory):
    table = build_features(snapshot_factory(count=20))
    assert table.iloc[:14].feature_ready.eq(False).all()
    row = table.iloc[14]
    assert (row.lag_1, row.lag_7, row.rolling_mean_7, row.rolling_mean_14) == (14,8,11,7.5)
    assert row.train_ready and row.day_of_week == 3 and not row.is_weekend

def test_partial_preserves_calendar_and_readiness(snapshot_factory):
    table = build_features(snapshot_factory(count=40, changes={20:{"guest_data_status":"PARTIAL","target_guests":None}}))
    assert len(table) == 40
    assert table.iloc[20].feature_ready and not table.iloc[20].target_ready
    assert math.isnan(table.iloc[20].target_guests)
    assert not table.iloc[21:35].feature_ready.any()
    assert table.iloc[35].feature_ready
    assert "TARGET_NOT_COMPLETE" in table.iloc[20].reason_codes

def test_missing_date_inserted_not_compressed(snapshot_factory):
    rows = list(snapshot_factory(count=20).rows)
    del rows[5]
    result = normalize_rows(rows)
    assert len(result) == 20 and result[5].target_guests is None and result[5].guest_data_status == "MISSING"

def test_true_zero_retained(snapshot_factory):
    snapshot = snapshot_factory(count=20, changes={0:{"target_guests":0}})
    assert build_features(snapshot).iloc[14].rolling_mean_14 == pytest.approx(104/14)
    assert seasonal_naive({r.full_date:r.target_guests for r in snapshot.rows}, date(2020,1,7))[0] == 0

@pytest.mark.parametrize("value", [-1,float("nan"),float("inf"),1.5,True])
def test_invalid_actuals_rejected(snapshot_factory, value):
    with pytest.raises(DemandError): snapshot_factory(changes={0:{"target_guests":value}})

def test_partial_subtotal_and_duplicate_calendar_rejected(snapshot_factory):
    with pytest.raises(DemandError, match="NULL"):
        snapshot_factory(changes={0:{"guest_data_status":"PARTIAL","target_guests":5}})
    rows = snapshot_factory().rows
    with pytest.raises(DemandError, match="Duplicate"):
        normalize_rows([rows[0], rows[0]])
    with pytest.raises(DemandError, match="mismatch"):
        normalize_rows([{**asdict(rows[0]),"is_weekend":True}])

def test_timezone_dates():
    assert local_date(datetime(2020,7,1,23,30,tzinfo=timezone.utc)) == date(2020,7,2)
    with pytest.raises(DemandError): local_date(datetime(2020,1,1))
    with pytest.raises(DemandError): local_date("2020-02-30")

def test_seasonal_naive_exact_contract(snapshot_factory, bundle_factory):
    snapshot = snapshot_factory()
    cutoff = date(2020,1,20)
    result = forecast_demand(bundle_factory(snapshot),snapshot,calendar(snapshot,cutoff),cutoff)
    assert result.status == "ok" and len(result.forecasts) == 7
    assert [r["predicted_guest_count"] for r in result.forecasts] == list(range(14,21))
    assert result.forecasts[-1]["forecast_date"] == "2020-01-27"
    assert result.to_dict()["summary"]["total_predicted_guests_7d"] == 119
    assert "demand_level" not in result.forecasts[0]

def test_recursive_forecast_never_reads_future_actuals(snapshot_factory,bundle_factory):
    cutoff = date(2020,1,20)
    a = snapshot_factory()
    b = snapshot_factory(changes={i:{"target_guests":999999} for i in range(20,100)})
    model = bundle_factory(a,"linear_regression",LagPlusOne())
    left = forecast_demand(model,a,calendar(a,cutoff),cutoff)
    right = forecast_demand(model,b,calendar(b,cutoff),cutoff)
    assert [r["predicted_guest_count"] for r in left.forecasts] == list(range(21,28))
    assert [r["predicted_guest_count"] for r in left.forecasts] == [r["predicted_guest_count"] for r in right.forecasts]
    assert left.forecasts[-1]["input_sources"]["predicted_days"] == 6
    assert a.rows[20].target_guests == 21

@pytest.mark.parametrize("name,missing", [("seasonal_naive",19),("linear_regression",10)])
def test_history_unavailable_is_explicit(snapshot_factory,bundle_factory,name,missing):
    snapshot = snapshot_factory(changes={missing:{"target_guests":None,"guest_data_status":"PARTIAL"}})
    cutoff=date(2020,1,20)
    result=forecast_demand(bundle_factory(snapshot,name,LagPlusOne()),snapshot,calendar(snapshot,cutoff),cutoff)
    assert result.status == "unavailable" and result.reason_code == "INSUFFICIENT_HISTORY"
    assert result.forecasts == ()

@pytest.mark.parametrize("value",[float("nan"),float("inf")])
def test_nonfinite_prediction_rejected(snapshot_factory,bundle_factory,value):
    s=snapshot_factory(); t=date(2020,1,20)
    with pytest.raises(DemandError,match="NaN"):
        forecast_demand(bundle_factory(s,"linear_regression",Constant(value)),s,calendar(s,t),t)

def test_negative_prediction_clamped(snapshot_factory,bundle_factory):
    s=snapshot_factory(); t=date(2020,1,20)
    result=forecast_demand(bundle_factory(s,"linear_regression",Constant(-4)),s,calendar(s,t),t)
    assert all(p["predicted_guest_count"] == 0 for p in result.forecasts)

def test_versions_cutoff_and_horizon_guards(snapshot_factory,bundle_factory):
    s=snapshot_factory(); t=date(2020,1,20); b=bundle_factory(s,"linear_regression",LagPlusOne(),"2020-02-01")
    with pytest.raises(DemandError,match="past requested"):
        forecast_demand(b,s,calendar(s,t),t)
    b=bundle_factory(s); b.manifest["data_version"]="stale"
    with pytest.raises(DemandError,match="versions differ"):
        forecast_demand(b,s,calendar(s,t),t)
    b=bundle_factory(s)
    with pytest.raises(DemandError,match="Exactly seven"):
        forecast_demand(b,s,calendar(s,t)[:6],t)
    b.manifest["feature_schema"]=[]
    with pytest.raises(DemandError,match="schema"):
        forecast_demand(b,s,calendar(s,t),t)

def test_snapshot_roundtrip_and_corruption(snapshot_factory,tmp_path):
    s=snapshot_factory(); p=tmp_path/"snapshot.json"
    save_snapshot(s,p)
    assert load_snapshot(p) == s
    p.write_text(p.read_text().replace('fixture-v1','changed'),encoding="utf-8")
    with pytest.raises(DemandError,match="hash"):
        load_snapshot(p)
