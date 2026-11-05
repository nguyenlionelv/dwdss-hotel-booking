from dataclasses import asdict
from datetime import date
from unittest.mock import patch
import json
import pytest

from ml.demand_forecast.contracts import DemandError
from ml.demand_forecast.data import extract_snapshot,make_snapshot,save_snapshot
from ml.demand_forecast.features import build_features
from ml.demand_forecast.train import load_config,fit_candidate
from scripts import train_models,forecast_demand,build_demand_features

def test_quality_failure_rejects_snapshot(snapshot_factory):
    raw=asdict(snapshot_factory())
    raw.pop("snapshot_hash")
    raw["quality"]["passed"]=False
    with pytest.raises(DemandError,match="quality must pass"):
        make_snapshot(**raw)

def test_quality_version_mismatch_rejects_snapshot(snapshot_factory):
    raw=asdict(snapshot_factory()); raw.pop("snapshot_hash")
    raw["quality"]["data_version"]="other-version"
    with pytest.raises(DemandError,match="does not match"):
        make_snapshot(**raw)

def test_training_cli_stops_before_fit_on_quality_failure(tmp_path):
    error=DemandError("QUALITY_FAILED","Fixture quality failure")
    error.quality={"passed":False,"checks":{"calendar":1}}
    with patch.object(train_models,"extract_snapshot",side_effect=error), patch.object(train_models,"run_experiment") as run:
        assert train_models.main(["--task","demand","--output-dir",str(tmp_path/"blocked")])==1
    run.assert_not_called()
    failure=json.loads((tmp_path/"blocked"/"failure.json").read_text())
    assert failure["error_code"]=="QUALITY_FAILED" and not failure["training_workflow_started"]
    assert failure["quality"]["checks"]["calendar"]==1

def test_training_cli_rejects_fixture_and_canceled_tasks(snapshot_factory,tmp_path):
    snapshot=tmp_path/"fixture.json"; save_snapshot(snapshot_factory(),snapshot)
    assert train_models.main(["--task","demand","--snapshot",str(snapshot),"--output-dir",str(tmp_path/"run")])==1
    assert json.loads((tmp_path/"run"/"failure.json").read_text())["error_code"]=="FIXTURE_NOT_OFFICIAL"
    with pytest.raises(SystemExit) as exc:
        train_models.main(["--task","cancellation"])
    assert exc.value.code==2

def test_forecast_cli_missing_model_and_feature_cli_failure(tmp_path,capsys):
    assert forecast_demand.main(["--bundle",str(tmp_path/"missing"),"--as-of-date","2020-01-01"])==1
    assert json.loads(capsys.readouterr().out)["reason_code"]=="MISSING_MODEL"
    with patch.object(build_demand_features,"extract_snapshot",side_effect=DemandError("DATABASE_UNAVAILABLE","fixture failure")):
        assert build_demand_features.main(["--output-dir",str(tmp_path/"features")])==1
    assert json.loads((tmp_path/"features"/"failure.json").read_text())["error_code"]=="DATABASE_UNAVAILABLE"

def test_stale_feature_identity_is_rejected(snapshot_factory):
    s=snapshot_factory(); f=build_features(s)
    f.attrs["data_version"]="stale"
    with pytest.raises(DemandError,match="pinned snapshot"):
        fit_candidate("linear_regression",s,f,date(2020,1,1),date(2020,2,4),load_config(),"test")

def test_database_error_mapping_does_not_leak_connection_details():
    import psycopg
    for error,code in [(psycopg.OperationalError("private connection detail"),"DATABASE_UNAVAILABLE"),
                       (psycopg.errors.UndefinedTable("private table detail"),"SOURCE_NOT_READY")]:
        with patch("pipeline.staging_to_dw.config.load_config",return_value={}), \
             patch("pipeline.source_to_staging.common.connect",side_effect=error):
            with pytest.raises(DemandError) as caught:
                extract_snapshot()
        assert caught.value.code==code and "private" not in str(caught.value)
