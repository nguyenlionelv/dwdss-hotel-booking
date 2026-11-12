"""Descriptive holdout QA of locked DSS policy and existing saved forecasts; no fitting."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
from ml.demand_forecast.registry import entries
from ml.demand_forecast.predict import inputs, daily_prediction
from backend.app.services.decision_engine.recommendation_service import load_policy, evaluate
from backend.app.services.decision_engine.historical_context import HistoricalContext, day


def run():
    policy, fingerprint = load_policy()
    # Hash every saved model file and notebook before/after to detect unintended writes.
    protected = [p for folder in ('artifacts/ml_serving/models','notebooks') for p in (ROOT/folder).rglob('*') if p.is_file()]
    def hashes():
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    before = hashes()
    report = {'policy_sha256': fingerprint, 'selection_uses_holdout': False, 'holdout_already_inspected': True, 'models': []}
    for meta, state in entries(policy['data_version'], 'daily'):
        daily, bookings = inputs(meta)
        rows = daily.to_dict('records')
        actuals = {day(r['full_date']): float(r['target_guests']) for r in rows
                   if r['guest_data_status']=='COMPLETE' and pd.notna(r['target_guests'])}
        counts = Counter({key:0 for key in ('origins','origins_with_insights','insights',
            'missingness_changed_origins','scorable_insights','unscorable_insights',
            'direction_unconfirmed_proxy','tail_unconfirmed_proxy')})
        origins = []; suppressions = Counter()
        for cutoff in pd.date_range('2017-06-01','2017-08-24'):
            dates, values, latest = daily_prediction(meta,state,daily,bookings,cutoff)
            forecasts = [dict(forecast_date=t.date(),predicted_guest_count=v) for t,v in zip(dates,values)]
            result = evaluate(rows,forecasts,meta,latest,policy['data_version'],policy,fingerprint)
            # One known day removed, with all forecasts frozen, isolates context sensitivity.
            known = HistoricalContext(rows,latest,policy).window(56)
            removed = max(known, default=None)
            stressed = evaluate([r for r in rows if day(r['full_date']) != removed],forecasts,meta,latest,policy['data_version'],policy,fingerprint)
            identity = lambda r: {(str(i['forecast_date']),i['signal']) for i in r['insights']}
            counts['origins'] += 1
            counts['origins_with_insights'] += bool(result['insights'])
            counts['missingness_changed_origins'] += identity(result) != identity(stressed)
            suppressions.update(result['metadata'].get('suppressions',{}))
            for insight in result['insights']:
                counts['insights'] += 1
                t = day(insight['forecast_date'])
                actual = actuals.get(t)
                if insight['analysis']=='transition':
                    previous = actuals.get(day(insight['previous_forecast_date']))
                    actual = actual-previous if actual is not None and previous is not None else None
                if actual is None:
                    counts['unscorable_insights'] += 1
                    continue
                counts['scorable_insights'] += 1
                residual = actual-insight['historical_reference']
                correct_direction = residual*insight['deviation_guests'] > 0
                realized_tail = abs(residual)/insight['variability'] > insight['calibrated_standardized_threshold']
                counts['direction_unconfirmed_proxy'] += not correct_direction
                counts['tail_unconfirmed_proxy'] += not realized_tail
            if result['insights'] or str(cutoff.date())=='2017-08-24':
                origins.append(dict(cutoff=str(cutoff.date()),history=result['metadata'].get('available_case_56'),
                                    insights=result['insights']))
        report['models'].append(dict(model_id=meta['model_id'],counts=dict(counts),suppressions=dict(suppressions),selected_origins=origins))
    assert hashes()==before, 'Saved model or notebook changed'
    report['protected_files_unchanged'] = True
    report['limitations'] = ['Overlapping seven-day origins are dependent.',
        'Unconfirmed direction/tail proxies are not operational false alarms or business impact.',
        'Partial actuals are unscorable; missingness stress removes only the latest known day.',
        'No saved validation residual distribution exists; MAE gates are not uncertainty intervals.']
    out = ROOT/'artifacts/dss_v2/sensitivity_holdout.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,default=str)+'\n',encoding='utf-8')
    print(json.dumps([{k:v for k,v in m.items() if k!='selected_origins'} for m in report['models']],indent=2))


if __name__=='__main__':
    run()
