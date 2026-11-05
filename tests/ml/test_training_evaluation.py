from datetime import date,timedelta
import json
import numpy as np
import pytest

from ml.demand_forecast.artifacts import make_bundle,save_bundle,load_bundle
from ml.demand_forecast.contracts import FEATURE_NAMES,DemandError
from ml.demand_forecast.data import load_snapshot
from ml.demand_forecast.data import digest
from ml.demand_forecast.evaluate import metrics,summarize,origins_for_partition,evaluate_bundle,nonoverlapping
from ml.demand_forecast.features import build_features
from ml.demand_forecast.predict import forecast_demand
from ml.demand_forecast.train import load_config,validate_config,fit_candidate,training_rows
from ml.demand_forecast.workflow import run_experiment

@pytest.fixture
def config():
    result=load_config()
    result.update(min_train_rows=10,min_validation_origins=1,min_test_origins=1)
    result["splits"]={"train":{"start":"2020-01-01","end":"2020-02-04"},
                      "validation":{"start":"2020-02-05","end":"2020-03-10"},
                      "test":{"start":"2020-03-11","end":"2020-04-09"}}
    result["models"]["random_forest"]["n_estimators"]=8
    result["models"]["xgboost"]["n_estimators"]=8
    return result

def test_known_metrics_and_horizons():
    points=[{"as_of_date":"2020-01-20","forecast_date":"2020-01-21","horizon":1,
             "predicted_guest_count":4.,"actual_guest_count":1.},
            {"as_of_date":"2020-01-20","forecast_date":"2020-01-22","horizon":2,
             "predicted_guest_count":1.,"actual_guest_count":5.}]
    result=summarize(points)
    assert result["mae"]==3.5 and result["rmse"]==pytest.approx(np.sqrt(12.5))
    assert result["bias"]==-.5 and result["origins"]==1 and result["points"]==2
    assert result["by_horizon"]["1"]["mae"]==3 and result["by_horizon"]["7"]["mae"] is None
    assert metrics([])["points"]==0

def test_split_windows_are_exact_and_same_across_models(snapshot_factory,config):
    snapshot=snapshot_factory()
    split=config["splits"]["validation"]
    frozen=origins_for_partition(snapshot,split)
    assert frozen["eligible"][0]=="2020-02-04"
    assert frozen["eligible"][-1]=="2020-03-03"
    assert len(frozen["eligible"])==29
    assert nonoverlapping(frozen["eligible"])==["2020-02-04","2020-02-11","2020-02-18","2020-02-25","2020-03-03"]
    for raw in frozen["eligible"]:
        t=date.fromisoformat(raw)
        assert t+timedelta(days=1)>=date.fromisoformat(split["start"])
        assert t+timedelta(days=7)<=date.fromisoformat(split["end"])

def test_partial_origin_exclusions_and_baseline_broader(snapshot_factory):
    s=snapshot_factory(changes={10:{"target_guests":None,"guest_data_status":"PARTIAL"}})
    partition={"start":"2020-01-20","end":"2020-02-10"}
    common=origins_for_partition(s,partition)
    broader=origins_for_partition(s,partition,history_days=7)
    assert len(broader["eligible"])>len(common["eligible"])
    assert common["exclusion_counts"]["HISTORY_NOT_COMPLETE"]>0

@pytest.mark.parametrize("name",["linear_regression","random_forest","xgboost"])
def test_candidates_fit_only_training_labels_and_reload(snapshot_factory,config,tmp_path,name):
    s=snapshot_factory(); features=build_features(s)
    b=fit_candidate(name,s,features,date(2020,1,1),date(2020,2,4),config,name+"-test")
    assert b.manifest["metadata"]["train_rows"]==21
    assert b.manifest["training_cutoff"]=="2020-02-04"
    origins=origins_for_partition(s,config["splits"]["validation"])["eligible"]
    score,points=evaluate_bundle(b,s,origins)
    assert score["origins"]==29 and score["points"]==203
    assert all(score["by_horizon"][str(h)]["points"]==29 for h in range(1,8))
    path=save_bundle(b,tmp_path/name)
    loaded=load_bundle(path)
    other,again=evaluate_bundle(loaded,s,origins[:1])
    assert [r["predicted_guest_count"] for r in points[:7]]==pytest.approx([r["predicted_guest_count"] for r in again])
    # Alter all labels after the fitting boundary; fitted predictions are unchanged.
    changed=snapshot_factory(changes={i:{"target_guests":10000+i} for i in range(35,100)})
    duplicate=fit_candidate(name,changed,build_features(changed),date(2020,1,1),date(2020,2,4),config,name+"-repeat")
    x=features.loc[features.train_ready,list(FEATURE_NAMES)].astype(float)
    assert np.allclose(b.estimator.predict(x),duplicate.estimator.predict(x))

def test_encoder_fitted_on_training_categories_only(snapshot_factory,config):
    s=snapshot_factory(); features=build_features(s)
    b=fit_candidate("linear_regression",s,features,date(2020,1,1),date(2020,2,4),config,"linear-test")
    encoder=b.estimator.named_steps["preprocessing"].named_transformers_["calendar"]
    assert list(encoder.categories_[1])==[1.,2.]

def test_corrupt_estimator_manifest_schema_and_missing_bundle(snapshot_factory,config,tmp_path):
    s=snapshot_factory(); f=build_features(s)
    b=fit_candidate("linear_regression",s,f,date(2020,1,1),date(2020,2,4),config,"linear-test")
    p=save_bundle(b,tmp_path/"model")
    (p/"estimator.joblib").write_bytes(b"broken")
    with pytest.raises(DemandError,match="checksum"):
        load_bundle(p)
    p=save_bundle(make_bundle(s,"seasonal_naive",date(2020,1,1),"baseline-test"),tmp_path/"baseline")
    envelope=json.loads((p/"manifest.json").read_text())
    envelope["manifest"]["feature_schema"]=[]
    (p/"manifest.json").write_text(json.dumps(envelope),encoding="utf-8")
    with pytest.raises(DemandError,match="checksum"):
        load_bundle(p)
    with pytest.raises(DemandError,match="does not exist"):
        load_bundle(tmp_path/"absent")

def test_full_fixture_workflow_and_test_selection_protocol(snapshot_factory,config,tmp_path):
    s=snapshot_factory(); output=tmp_path/"run"
    result=run_experiment(s,config,output)
    assert result["status"]=="completed" and result["run_kind"]=="synthetic_fixture"
    assert result["reload_verified"]
    assert len(result["comparison"])==4
    assert result["selected_model"]=="linear_regression"
    for row in result["comparison"]:
        assert row["validation"]["origins"]==29
        assert (row["test"] is not None)==(row["model_name"] in {"seasonal_naive",result["selected_model"]})
    assert result["final_train_rows"]==56
    assert load_snapshot(output/"snapshot.json")==s
    assert (output/"predictions.csv").is_file() and (output/"comparison.md").is_file()
    loaded=load_bundle(output/result["selected_bundle"])
    assert loaded.manifest["training_cutoff"]=="2020-03-10"
    assert result["selection"]["test_used_for_selection"] is False
    with pytest.raises(FileExistsError): run_experiment(s,config,output)

def test_candidate_failure_is_transparent_and_selection_incomplete(snapshot_factory,config,tmp_path):
    # A deterministic failing factory avoids relying on unknown-keyword handling in XGBoost.
    from unittest.mock import patch
    from ml.demand_forecast.train import candidate_pipeline
    def failing(name,configuration):
        if name=="xgboost": raise ValueError("fixture candidate failure")
        return candidate_pipeline(name,configuration)
    with patch("ml.demand_forecast.train.candidate_pipeline",side_effect=failing):
        result=run_experiment(snapshot_factory(),config,tmp_path/"failed")
    assert result["status"]=="incomplete" and result["selected_model"] is None
    assert next(r for r in result["comparison"] if r["model_name"]=="xgboost")["status"]=="failed"
    assert all(r["test"] is None for r in result["comparison"])

def test_insufficient_windows_stop_before_fitting(snapshot_factory,config,tmp_path):
    config["min_validation_origins"]=999
    result=run_experiment(snapshot_factory(),config,tmp_path/"sparse")
    assert result["status"]=="incomplete" and result["reason_code"]=="INSUFFICIENT_EVALUATION_DATA"
    assert not (tmp_path/"sparse"/"bundles").exists()

def test_partition_overlap_and_canceled_candidates_rejected(config):
    config["splits"]["validation"]["start"]="2020-02-04"
    with pytest.raises(DemandError): validate_config(config)
    config["splits"]["validation"]["start"]="2020-02-05"
    config["models"]["cancellation"]={}
    with pytest.raises(DemandError): validate_config(config)

def test_semantic_schema_and_runtime_guards_after_valid_checksums(snapshot_factory,config,tmp_path):
    s=snapshot_factory()
    base=save_bundle(make_bundle(s,"seasonal_naive",date(2020,1,1),"baseline"),tmp_path/"base")
    envelope=json.loads((base/"manifest.json").read_text())
    envelope["manifest"]["feature_schema"].reverse()
    envelope["manifest_sha256"]=digest(envelope["manifest"])
    (base/"manifest.json").write_text(json.dumps(envelope),encoding="utf-8")
    with pytest.raises(DemandError,match="schema"):
        load_bundle(base)
    b=fit_candidate("linear_regression",s,build_features(s),date(2020,1,1),date(2020,2,4),config,"linear")
    p=save_bundle(b,tmp_path/"regression")
    envelope=json.loads((p/"manifest.json").read_text())
    envelope["manifest"]["runtime"]["scikit-learn"]="incompatible"
    envelope["manifest_sha256"]=digest(envelope["manifest"])
    (p/"manifest.json").write_text(json.dumps(envelope),encoding="utf-8")
    with pytest.raises(DemandError,match="dependency versions"):
        load_bundle(p)
