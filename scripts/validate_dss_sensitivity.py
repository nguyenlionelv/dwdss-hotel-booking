"""Development-only context sensitivity experiment; no model fitting or future model replay.

Saved models were selected through May 2017. Replaying those parameters before
selection would leak future information. Use an explicitly labeled causal
14-day-level + same-weekday-reference probe, not purported saved-model forecasts.
"""
import sys,json,csv,hashlib
from pathlib import Path
from datetime import date,timedelta
from statistics import mean
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.services.decision_engine.historical_context import HistoricalContext,day
from scripts.calibrate_dss import quantile

def samples(rows,policy):
    known={day(r['full_date']):float(r['target_guests']) for r in rows if r['guest_data_status']=='COMPLETE' and r['target_guests'] not in ('',None)}
    out=[]
    for latest in sorted(known):
        if not date(2015,10,21)<=latest<=date(2017,5,24):continue
        context=HistoricalContext(rows,latest,policy)
        window=context.window(56); recent=context.window(14)
        if len(recent)<10 or not context.summary()['supported']:continue
        shift=mean(recent.values())-mean(window.values())
        removed=max(window)
        stressed=HistoricalContext([r for r in rows if day(r['full_date'])!=removed],latest,policy)
        for h in range(1,8):
            target=latest+timedelta(days=h)
            ref=context.reference(target.weekday());alt=stressed.reference(target.weekday())
            if ref is None or target not in known:continue
            forecast=max(0,ref.center+shift)
            z=abs(forecast-ref.center)/ref.variability
            actual_z=abs(known[target]-ref.center)/ref.variability
            signed=(known[target]-ref.center)*(forecast-ref.center)>0
            out.append(dict(origin=str(latest),horizon=h,weekday=target.weekday(),z=z,
                stressed_z=abs(forecast-alt.center)/alt.variability if alt else None,
                # A realized same-weekday departure beyond one historical SD.
                event=actual_z>1, direction_correct=signed))
    return out

def metrics(rows,threshold):
    n=len(rows);alert=[r['z']>threshold for r in rows]
    tp=sum(a and r['event'] and r['direction_correct'] for a,r in zip(alert,rows))
    # Alert correctness requires both realized departure and matching direction.
    fp=sum(alert)-tp; events=sum(r['event'] for r in rows)
    negatives=sum(not r['event'] for r in rows)
    false_positive=sum(a and not r['event'] for a,r in zip(alert,rows))
    flips=sum(a!=(r['stressed_z'] is not None and r['stressed_z']>threshold) for a,r in zip(alert,rows))
    keyed={(r['origin'],r['horizon']):a for r,a in zip(rows,alert)}
    adjacent=[a!=keyed[(str(day(r['origin'])+timedelta(days=1)),r['horizon']-1)] for r,a in zip(rows,alert) if (str(day(r['origin'])+timedelta(days=1)),r['horizon']-1) in keyed]
    return dict(n=n,alerts=sum(alert),detection_rate=sum(alert)/n if n else None,
        event_count=events,false_positive_rate=false_positive/negatives if negatives else None,
        unconfirmed_alert_fraction=fp/sum(alert) if sum(alert) else None,
        correct_direction_event_precision=tp/sum(alert) if sum(alert) else None,
        missingness_flip_rate=flips/n if n else None,
        adjacent_cutoff_flip_rate=sum(adjacent)/len(adjacent) if adjacent else None)

def run(calibration=None, snapshot=None, report_path=None, policy_path=None):
    calibration=Path(calibration or ROOT/'artifacts/dss_v2/calibration.json')
    snapshot=Path(snapshot or ROOT/'artifacts/ml_serving/snapshot/daily_input.csv')
    report_path=Path(report_path or ROOT/'artifacts/dss_v2/sensitivity_validation.json')
    policy_path=Path(policy_path or ROOT/'backend/app/services/decision_engine/policy.json')
    policy=json.loads(calibration.read_text(encoding='utf-8'))['policy']
    with snapshot.open(encoding='utf-8') as handle:
        rows=list(csv.DictReader(handle))
    records=samples(rows,policy)
    # Split by origin AND target: calibration targets end June 30, validation starts July 1.
    calibration=[r for r in records if day(r['origin'])+timedelta(days=r['horizon'])<=date(2016,6,30)]
    validation=[r for r in records if r['origin']>='2016-07-01']
    trials=[]
    for q in (.75,.85,.90,.95,.975):
        threshold=quantile([r['z'] for r in calibration],q)
        trials.append(dict(quantile=q,threshold=threshold,validation=metrics(validation,threshold)))
    # Prespecified descriptive-insight budget: <=10% FPR and <=5% missingness flips.
    # Highest detection among eligible trials. No minimum nonempty output requirement.
    eligible=[t for t in trials if t['validation']['false_positive_rate']<=.10 and t['validation']['missingness_flip_rate']<=.05]
    selected=max(eligible,key=lambda t:t['validation']['detection_rate']) if eligible else None
    if selected:
        policy.update(rule_version='weekday-insight-advisory-v2', insight_thresholds={'weekday':selected['threshold']},
            operational_advisories_validated=False,
            insight_calibration='causal-level-probe-v1; not saved-model development forecasts',
            insight_validation_end='2017-05-31',holdout_already_inspected=True)
    report=dict(protocol='causal-level-probe-v1',holdout_used_for_selection=False,holdout_already_inspected=True,
        event_definition='COMPLETE target differs from causal same-weekday mean by >1 sample SD; direction checked separately',
        trials=trials,selected=selected,calibration_n=len(calibration),validation_n=len(validation),
        by_weekday={str(w):metrics([r for r in validation if r['weekday']==w],selected['threshold']) for w in range(7)} if selected else {},
        by_horizon={str(h):metrics([r for r in validation if r['horizon']==h],selected['threshold']) for h in range(1,8)} if selected else {},
        limitations=['Probe validation is not validation of the saved models; pre-selection saved-model replay would leak.',
            'Overlapping origins are dependent; one-SD event is a statistical definition, not an operational outcome.',
            'Existing holdout has already been inspected. Subsequent results are descriptive, not unbiased.'])
    report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if not selected:
        raise ValueError('No insight threshold passed development validation; do not publish policy')
    policy_path.write_text(json.dumps(policy,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(selected=selected,trials=trials),indent=2))
    return policy

if __name__=='__main__':run()
