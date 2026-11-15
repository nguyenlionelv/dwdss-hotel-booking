"""Causality, available-case alignment, safe suppression and evidence-backed rules."""
from copy import deepcopy
from datetime import date, timedelta
import pytest
from backend.app.services.decision_engine.historical_context import HistoricalContext, read_history
from backend.app.services.decision_engine.demand_analysis import deviations, horizon_errors
from backend.app.services.decision_engine.decision_rules import actionable, rank_insights
from backend.app.services.decision_engine.recommendation_service import evaluate, load_policy, decision_support

LATEST = date(2017,8,24)

@pytest.fixture
def policy():
    policy={**load_policy()[0], 'data_version':'test'}
    policy.pop('insight_thresholds',None)  # Regression tests for original advisory gates.
    return policy

@pytest.fixture
def rows():
    return [dict(full_date=LATEST-timedelta(days=i), target_guests=100+(i%7)*8+(i//7)%5,
                 guest_data_status='COMPLETE') for i in range(112)]

def test_53_available_days_and_truthful_stats(rows,policy):
    for i in (2,8,30):
        rows[i].update(target_guests=None,guest_data_status='PARTIAL')
    ctx=HistoricalContext(rows,LATEST,policy)
    summary=ctx.summary()
    assert summary['sample_count']==53 and summary['supported']
    assert summary['coverage']==53/56
    assert summary['mean']==pytest.approx(sum(r['target_guests'] for r in rows[:56] if r['target_guests'] is not None)/53)
    assert all(ctx.reference(w) is not None for w in range(7))

def test_future_actuals_and_order_cannot_change_context(rows,policy):
    expected=HistoricalContext(rows,LATEST,policy).summary()
    poisoned=rows+[dict(full_date=LATEST+timedelta(days=1),target_guests=999999,guest_data_status='COMPLETE')]
    assert HistoricalContext(list(reversed(poisoned)),LATEST,policy).summary()==expected

def test_zero_null_nan_and_partial_are_distinct(rows,policy):
    rows[0]['target_guests']=0
    rows[1]['target_guests']=None
    rows[2]['target_guests']=float('nan')
    rows[3]['guest_data_status']='PARTIAL'
    ctx=HistoricalContext(rows,LATEST,policy)
    assert ctx.known[LATEST]==0
    assert len(ctx.window(56))==53

def test_weekday_alignment_and_no_gap_bridging(rows,policy):
    ctx=HistoricalContext(rows,LATEST,policy)
    monday=ctx.reference(0)
    expected=[r['target_guests'] for r in rows[:56] if r['full_date'].weekday()==0]
    assert monday.center==pytest.approx(sum(expected)/len(expected))
    rows[0].update(target_guests=None,guest_data_status='PARTIAL')
    ctx=HistoricalContext(rows,LATEST,policy)
    transition=ctx.reference((LATEST+timedelta(days=1)).weekday(),True)
    known=ctx.window(transition.window_days)
    pairs=[v-known[d-timedelta(days=1)] for d,v in known.items() if d.weekday()==(LATEST+timedelta(days=1)).weekday() and d-timedelta(days=1) in known]
    assert transition.count==len(pairs) and transition.center==pytest.approx(sum(pairs)/len(pairs))

def test_extended_window_then_suppression(rows,policy):
    for row in rows[:21]:
        if row['full_date'].weekday()==0:
            row.update(target_guests=None,guest_data_status='PARTIAL')
    assert HistoricalContext(rows,LATEST,policy).reference(0).window_days==112
    for row in rows:
        if row['full_date'].weekday()==0:
            row.update(target_guests=None,guest_data_status='PARTIAL')
    ctx=HistoricalContext(rows,LATEST,policy)
    assert ctx.reference(0) is None
    assert ctx.reference(1) is not None

def test_missing_day_placement_changes_groups_safely(rows,policy):
    a,b=deepcopy(rows),deepcopy(rows)
    for i in (0,7,14): a[i].update(target_guests=None,guest_data_status='PARTIAL')
    for i in (0,1,2): b[i].update(target_guests=None,guest_data_status='PARTIAL')
    ca,cb=HistoricalContext(a,LATEST,policy),HistoricalContext(b,LATEST,policy)
    assert ca.summary()['sample_count']==cb.summary()['sample_count']==53
    assert ca.reference(LATEST.weekday()).window_days==112
    assert cb.reference(LATEST.weekday()).window_days==56

def test_zero_variability_is_suppressed(rows,policy):
    for row in rows: row['target_guests']=0
    ctx=HistoricalContext(rows,LATEST,policy)
    assert ctx.summary()['mean']==0 and ctx.summary()['std']==0
    assert ctx.reference(0) is None

def metric_metadata(mae=10):
    return {'model_version':'saved', 'validation_metrics':{'horizon':[
        dict(horizon=h,MAE=mae,scorable_n=40,population='COMPLETE_ONLY') for h in range(1,8)]}}

def forecasts():
    return [dict(forecast_date=LATEST+timedelta(days=h),predicted_guest_count=500 if h%2 else 0) for h in range(1,8)]

def test_error_gate_missing_metrics_and_population(policy):
    assert len(horizon_errors(metric_metadata(),policy))==7
    meta=metric_metadata()
    for m in meta['validation_metrics']['horizon']: m['population']='ALL_ESTIMATED'
    assert horizon_errors(meta,policy)=={}
    for m in meta['validation_metrics']['horizon']: m.update(population='COMPLETE_ONLY',scorable_n=1)
    assert horizon_errors(meta,policy)=={}

def test_evidence_ranking_at_most_three_and_no_future_poison(rows,policy):
    result=evaluate(rows,forecasts(),metric_metadata(),LATEST,'test',policy)
    assert result['state']=='ACTIONABLE' and 1<=len(result['insights'])<=3
    for insight in result['insights']:
        assert insight['evidence'] and insight['recommended_action']
        assert insight['absolute_deviation']>insight['model_error_scale']
        assert insight['standardized_deviation']>insight['calibrated_standardized_threshold']
    poisoned=rows+[dict(full_date=LATEST+timedelta(days=1),target_guests=1e9,guest_data_status='COMPLETE')]
    f=forecasts()
    for r in f: r['actual_guest_count']=1e9
    assert evaluate(poisoned,f,metric_metadata(),LATEST,'test',policy)==result
    assert not evaluate(rows,f,metric_metadata(10000),LATEST,'test',policy)['insights']
    assert not evaluate(rows,f,{},LATEST,'test',policy)['insights']

def test_normal_seasonality_not_volatility(rows,policy):
    ctx=HistoricalContext(rows,LATEST,policy)
    f=[dict(forecast_date=LATEST+timedelta(days=h),predicted_guest_count=ctx.reference((LATEST+timedelta(days=h)).weekday()).center) for h in range(1,8)]
    assert max(r['predicted_guest_count'] for r in f)-min(r['predicted_guest_count'] for r in f)>40
    assert not evaluate(rows,f,metric_metadata(),LATEST,'test',policy)['insights']

def test_all_four_advisory_rules_require_evidence(rows,policy):
    for i,row in enumerate(rows): row['target_guests']+=(i*13)%11
    comparisons,_=deviations(HistoricalContext(rows,LATEST,policy),forecasts())
    supported=[actionable(c,horizon_errors(metric_metadata(),policy),policy)[0] for c in comparisons]
    supported=[s for s in supported if s]
    assert {s['signal'] for s in supported}=={'ABOVE_TYPICAL_DEMAND','BELOW_TYPICAL_DEMAND','DEMAND_SURGE','DEMAND_DROP'}
    ranked=rank_insights(supported)
    assert len({s['forecast_date'] for s in ranked})==len(ranked)
    assert len({s['recommended_action'] for s in ranked})==len(ranked)
    assert all(s['strength']>1 for s in ranked)

def test_no_transition_across_forecast_gap(rows,policy):
    f=[forecasts()[0],forecasts()[2]]
    comparisons,_=deviations(HistoricalContext(rows,LATEST,policy),f)
    assert all(c['analysis']=='weekday' for c in comparisons)

def test_policy_availability_and_version(rows,policy):
    assert evaluate(rows,forecasts(),metric_metadata(),LATEST,'wrong',policy)['metadata']['status']=='POLICY_DATA_VERSION_MISMATCH'
    assert evaluate(rows,forecasts(),metric_metadata(),date(2017,1,1),'test',policy)['metadata']['status']=='POLICY_NOT_YET_AVAILABLE'

def test_db_query_bounded_to_label_cutoff():
    class Connection:
        def execute(self,sql,args):
            assert 'data_version=%s' in sql and 'BETWEEN %s AND %s' in sql
            assert args==('version',LATEST-timedelta(days=111),LATEST)
            return self
        def fetchall(self): return []
    assert read_history(Connection(),'version',LATEST)==[]

def test_bad_policy_neutral_without_history_query(monkeypatch,tmp_path):
    monkeypatch.setenv('DWDSS_DECISION_POLICY',str(tmp_path/'missing.json'))
    result=decision_support(None,[],{},LATEST,'test')
    assert result['state']=='NEUTRAL' and result['insights']==[]

def test_duplicate_dates_rejected(rows,policy):
    with pytest.raises(ValueError,match='Duplicate'):
        HistoricalContext(rows+[rows[0]],LATEST,policy)

def test_calibration_does_not_use_holdout():
    import json
    from pathlib import Path
    report=json.loads(Path('artifacts/dss_v2/calibration.json').read_text())
    assert not report['holdout_used_for_selection']
    assert report['policy']['validation_end']=='2017-05-31'
    trial=next(t for t in report['trials'] if t['min_complete_56']==50)
    assert not trial['eligible']
    selected=next(t for t in report['trials'] if t['min_complete_56']==report['policy']['min_complete_56'])
    assert selected['eligible']

def test_descriptive_insights_are_not_mae_gated_or_operational_actions(rows):
    policy={**load_policy()[0],'data_version':'test'}
    result=evaluate(rows,forecasts(),{},LATEST,'test',policy)
    assert result['state']=='INSIGHTS'
    assert result['insights']
    for insight in result['insights']:
        assert insight['category']=='DEMAND_INSIGHT' and insight['priority']=='INSIGHT'
        assert insight['recommended_action'] is None and insight['model_error_scale'] is None
        assert insight['analysis']=='weekday'
        assert 'forecast vs' in insight['evidence']
    inflated=evaluate(rows,forecasts(),metric_metadata(10000),LATEST,'test',policy)
    assert [i['signal'] for i in inflated['insights']]==[i['signal'] for i in result['insights']]
    poisoned=rows+[dict(full_date=LATEST+timedelta(days=1),target_guests=1e9,guest_data_status='COMPLETE')]
    assert evaluate(poisoned,forecasts(),{},LATEST,'test',policy)==result

def test_revised_policy_is_locked_on_development_and_discloses_probe():
    import json
    from pathlib import Path
    report=json.loads(Path('artifacts/dss_v2/sensitivity_validation.json').read_text())
    policy=load_policy()[0]
    assert report['holdout_used_for_selection'] is False and report['holdout_already_inspected']
    assert 'probe' in policy['insight_calibration']
    assert report['selected']['threshold']==policy['insight_thresholds']['weekday']
    assert report['selected']['validation']['false_positive_rate']<=.10
    assert policy['operational_advisories_validated'] is False
