"""Notebook equivalence, availability boundaries, artifact integrity and API contracts."""
import ast
import json
import os
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ml.demand_forecast import imputed, causal, monthly
from ml.demand_forecast.artifacts import save_bundle, load_bundle
from ml.demand_forecast.predict import daily_prediction, ForecastInputError
from ml.demand_forecast.registry import entries, resolve
from ml.demand_forecast.data import load_snapshot
from ml.demand_forecast.evaluation import folds
from backend.app.services.dss_service import thresholds, classify
from pipeline.source_to_staging.common import ROOT


@pytest.fixture
def frames():
    days = pd.date_range('2015-07-01', periods=110)
    rows, bookings = [], []
    for i, day in enumerate(days):
        partial = i % 13 == 4
        known = 1 + i % 4
        rows.append(dict(full_date=day, target_guests=np.nan if partial else known + 2,
            observed_total_guests=known if partial else known + 2,
            guest_valid_booking_count=1 if partial else 2,
            missing_guest_bookings_count=int(partial), guest_ineligible_booking_count=int(partial),
            non_canceled_bookings=2,rejected_booking_count=0,excluded_booking_count=0,
            guest_data_status='PARTIAL' if partial else 'COMPLETE',booking_data_status='COMPLETE'))
        for j in range(2):
            bookings.append(dict(full_date=day,source_row_id=2+2*i+j,source_file_sha256='a'*64,
                is_canceled=0,total_guests=0 if partial and j==1 else known if j==0 else 2,
                guest_eligible=not(partial and j==1),reserved_room_type='A' if i%10 else 'B'))
    return pd.DataFrame(rows),pd.DataFrame(bookings)


def notebook_functions(module, filename, daily, bookings):
    """Load only original function definitions as an independent numerical oracle."""
    ns = {**vars(module), 'daily':daily,'bookings':bookings,
        'valid':bookings[bookings.is_canceled.eq(0)&bookings.guest_eligible],
        'HISTORY':None,'save_json':lambda *a:None,'save_csv':lambda *a:None}
    notebook=json.loads((ROOT/'notebooks/experiments'/filename).read_text(encoding='utf-8'))
    for cell in notebook['cells']:
        if cell['cell_type']!='code': continue
        for node in ast.parse(''.join(cell['source'])).body:
            if isinstance(node,ast.FunctionDef) and node.name not in ['sha','save_json','save_csv']:
                exec(compile(ast.Module(body=[node],type_ignores=[]),filename,'exec'),ns)
    return ns


@pytest.mark.parametrize('module,filename',[
    (imputed,'history_demand_imputed_3fold_report.ipynb'),
    (causal,'history_demand_causal_methods_report.ipynb'),
    (monthly,'monthly_demand_forecast_report.ipynb')])
def test_room_labels_match_original_notebook(frames,module,filename):
    daily,bookings=frames;engine=module.Experiment(daily,bookings)
    original=notebook_functions(module,filename,daily,bookings)
    expected,imputer=original['room_labels']('2015-09-01','2015-10-01')
    actual,fitted=engine.room_labels('2015-09-01','2015-10-01')
    pd.testing.assert_frame_equal(actual,expected)
    assert fitted==imputer


def test_baseline_matches_notebook_and_future_poison(frames):
    daily,bookings=frames;engine=imputed.Experiment(daily,bookings)
    ns=notebook_functions(imputed,'history_demand_imputed_3fold_report.ipynb',daily,bookings)
    labels,imputer=engine.room_labels('2015-09-01','2015-10-01')
    series=labels.set_index('full_date').target_estimated
    stats=engine.history_stats(series)
    expected,_=ns['fit_baseline'](series,stats,'2015-09-01')
    actual,_=engine.fit_baseline(series,stats,'2015-09-01')
    assert actual==expected
    metadata={'training_cutoff':'2015-09-01','imputation_policy':'imputed_history',
              'availability_assumptions':{'label_delay_days':0}}
    state={'params':actual,'imputer':imputer}
    dates,values,_=daily_prediction(metadata,state,daily,bookings,'2015-09-10')
    for h,value in enumerate(values,1):
        assert value==ns['baseline']('B4_weekday',series,stats,pd.Timestamp('2015-09-10'),h,expected['reference'],expected['correction'])[0]
    changed=daily.copy();changed.loc[changed.full_date.gt('2015-09-10'),'target_guests']=999999
    changed_bookings=bookings.copy();changed_bookings.loc[changed_bookings.full_date.gt('2015-09-10'),'total_guests']=999999
    assert daily_prediction(metadata,state,changed,changed_bookings,'2015-09-10')[1]==values
    assert dates==list(pd.date_range('2015-09-11',periods=7))
    with pytest.raises(ForecastInputError): daily_prediction(metadata,state,daily,bookings,'2015-08-01')
    with pytest.raises(ForecastInputError): daily_prediction(metadata,state,daily,bookings,'2015-09-10',8)


def test_causal_features_and_delay_match_notebook(frames):
    daily,bookings=frames;engine=causal.Experiment(daily,bookings)
    ns=notebook_functions(causal,'history_demand_causal_methods_report.ipynb',daily,bookings)
    expected=ns['causal_history'](daily)
    pd.testing.assert_series_equal(engine.HISTORY,expected)
    pairs=pd.DataFrame([(pd.Timestamp('2015-09-10'),h,pd.Timestamp('2015-09-10')+h*causal.DAY) for h in range(1,8)],columns=['origin','horizon','target_date'])
    pd.testing.assert_frame_equal(engine.features(engine.HISTORY,pairs),ns['features'](expected,pairs))
    altered=daily.copy();altered.loc[altered.full_date.ge('2015-09-10'),['target_guests','observed_total_guests']]=999999
    altered_bookings=bookings.copy();altered_bookings.loc[altered_bookings.full_date.ge('2015-09-10'),'total_guests']=999999
    meta={'training_cutoff':'2015-09-01','imputation_policy':'causal_history','availability_assumptions':{'label_delay_days':1}}
    state={'correction':np.zeros((7,7)).tolist()}
    result=daily_prediction(meta,state,daily,bookings,'2015-09-10')
    assert result[1]==daily_prediction(meta,state,altered,altered_bookings,'2015-09-10')[1]
    assert result[2]==pd.Timestamp('2015-09-09')
    np.testing.assert_allclose(result[1],engine.features(engine.HISTORY,pairs).mean_14)


def test_train_only_room_means_and_scaling(frames):
    daily,bookings=frames;engine=imputed.Experiment(daily,bookings)
    cutoff=pd.Timestamp('2015-08-15');before=engine.fit_room_imputer(cutoff)
    bookings.loc[bookings.full_date.gt(cutoff),'total_guests']=100000
    assert imputed.Experiment(daily,bookings).fit_room_imputer(cutoff)==before
    model=engine.make_ml_model('M0_linear')
    model.fit(pd.DataFrame({'x':[1.,np.nan,3.]}),[1,2,3])
    assert model.steps[0][1].statistics_[0]==2
    x=model[:-1].transform(pd.DataFrame({'x':[99999.]}))
    assert x[0,0]>100
    assert model.steps[0][1].statistics_[0]==2


def test_parallel_tree_execution_preserves_the_algorithm(frames,monkeypatch):
    from ml.demand_forecast.execution import CausalExperiment
    daily,bookings=frames
    serial=causal.Experiment(daily,bookings).make_model('A3_residual_extra_trees',{'min_samples_leaf':14})
    monkeypatch.setenv('DWDSS_TREE_JOBS','6')
    parallel=CausalExperiment(daily,bookings).make_model('A3_residual_extra_trees',{'min_samples_leaf':14})
    rng=np.random.default_rng(42);x=rng.normal(size=(180,5));y=rng.normal(size=180)
    serial.fit(x,y);parallel.fit(x,y)
    np.testing.assert_allclose(serial.predict(x),parallel.predict(x),rtol=0,atol=1e-12)


def test_monthly_units_and_calendar_length(frames):
    daily,bookings=frames;engine=monthly.Experiment(daily,bookings)
    months=pd.period_range('2015-03','2016-02',freq='M')
    train=pd.DataFrame({'target':months.days_in_month*10.,'rate':10.},index=months)
    assert engine.predict_month('M0_last_month_rate',train,pd.Period('2016-03'))==310.
    with pytest.raises(AssertionError):engine.predict_month('M0_last_month_rate',train,pd.Period('2016-04'))


def test_three_chronological_fold_boundaries():
    daily=pd.DataFrame({'full_date':pd.date_range('2015-07-01','2017-08-31')})
    result=folds(daily)
    assert [r['train_end'] for r in result]==['2015-12-23','2016-06-15','2016-12-07']
    assert result[-1]['eval_end']=='2017-05-31'


def test_thresholds_require_56_complete_days_and_preserve_zero():
    daily=pd.DataFrame({'full_date':pd.date_range('2017-01-01',periods=60),
        'target_guests':[0.]*60,'guest_data_status':['COMPLETE']*60})
    latest=daily.full_date.iloc[55];rule=thresholds(daily,latest)
    assert rule['sufficient_history'] and rule['low_threshold']==0 and rule['high_threshold']==0
    assert classify(0,rule)=='HIGH'  # Documented HIGH-first inclusive boundary.
    daily.loc[10,'guest_data_status']='PARTIAL';daily.loc[10,'target_guests']=np.nan
    rule=thresholds(daily,latest)
    assert rule['complete_days_available']==55 and rule['high_threshold'] is None
    assert classify(200,rule)=='INSUFFICIENT_HISTORY'
    daily.loc[56:,'target_guests']=99999
    assert thresholds(daily,latest)==rule


def test_artifact_versions_integrity_and_registry(tmp_path):
    meta={'model_id':'x','kind':'daily','data_version':'v1','default':True}
    save_bundle(tmp_path/'x',meta,{'correction':1})
    from pipeline.source_to_staging.common import sha256
    (tmp_path/'registry.json').write_text(json.dumps({'models':[{'folder':'x','kind':'daily','metadata_sha256':sha256(tmp_path/'x/metadata.json')}]}))
    assert resolve(None,'v1','daily',tmp_path)[0]['model_id']=='x'
    with pytest.raises(ValueError): load_bundle(tmp_path/'x','v2')
    with pytest.raises(ValueError): resolve('missing','v1','daily',tmp_path)
    with pytest.raises(ValueError): resolve('x','v1','monthly',tmp_path)
    with (tmp_path/'x/state.joblib').open('ab') as f:f.write(b'changed')
    with pytest.raises(ValueError): entries('v1','daily',tmp_path)


@pytest.mark.skipif(os.getenv('DWDSS_INTEGRATION')!='1',reason='Requires the published local Mart and trained artifacts')
def test_published_mart_to_api_and_saved_models():
    from backend.app.main import create_app
    from ml.demand_forecast.predict import inputs
    from backend.app.schemas.dss import DailyForecastResponse,MonthlyForecastResponse
    client=TestClient(create_app())
    models=client.get('/api/dss/models');assert models.status_code==200,models.text
    daily_models=[m for m in models.json()['models'] if m['kind']=='daily']
    assert len(daily_models)==3
    for m in daily_models:
        response=client.get('/api/dss/demand-forecast',params={'model_name':m['id'],'as_of_date':'2017-08-24'})
        assert response.status_code==200,response.text
        parsed=DailyForecastResponse.model_validate(response.json())
        assert len(parsed.forecasts)==7
        assert parsed.summary.total_predicted_guests_7d==sum(r.predicted_guest_count for r in parsed.forecasts)
        assert parsed.forecasts[0].forecast_date.isoformat()=='2017-08-25'
        assert all(r.predicted_room_nights is None for r in parsed.forecasts)
        assert max(r.full_date for r in parsed.recent_history)<=parsed.dss_threshold_rule.latest_label_date
    response=client.get('/api/dss/monthly-demand-forecast',params={'as_of_date':'2017-08-31'})
    assert response.status_code==200,response.text
    parsed=MonthlyForecastResponse.model_validate(response.json());assert parsed.forecast_month=='2017-09'
    meta,state=resolve('monthly_last_month_rate',parsed.data_version,'monthly')
    daily,bookings=inputs(meta);engine=monthly.Experiment(daily,bookings)
    labels,_=engine.monthly_labels(pd.Timestamp('2017-08-31'),pd.Timestamp('2017-08-31'))
    original=notebook_functions(monthly,'monthly_demand_forecast_report.ipynb',daily,bookings)
    assert parsed.predicted_guests==original['predict_month']('M0_last_month_rate',labels,pd.Period('2017-09'))
    assert client.get('/api/dss/demand-forecast?model_name=monthly_last_month_rate').status_code==422
    assert client.get('/api/dss/demand-forecast?horizon=8').status_code==422
    assert client.get('/api/dss/monthly-demand-forecast?as_of_date=2017-08-24').status_code==422
    assert client.get('/api/dss/demand-forecast?as_of_date=2016-01-01').status_code==422


def test_api_missing_artifacts_returns_error_not_forecast(tmp_path,monkeypatch):
    from backend.app.main import create_app
    from backend.app.api.metadata import get_db
    class FakeConnection:
        def execute(self,*args):return self
        def fetchone(self):return {'data_version':'missing'}
    app=create_app();app.dependency_overrides[get_db]=lambda:FakeConnection()
    monkeypatch.setenv('DWDSS_MODEL_DIR',str(tmp_path))
    response=TestClient(app).get('/api/dss/demand-forecast')
    assert response.status_code==503 and 'forecasts' not in response.json()
