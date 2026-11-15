"""Read-only gate audit of saved models. Previously inspected holdout, not a fresh test."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import json
from collections import Counter
import numpy as np
import pandas as pd
from ml.demand_forecast.registry import entries
from ml.demand_forecast.predict import inputs,daily_prediction
from backend.app.services.decision_engine.historical_context import HistoricalContext
from backend.app.services.decision_engine.demand_analysis import deviations,horizon_errors

def distribution(values):
    return dict(zip(('min','p25','median','p75','p95','max'),map(float,np.quantile(values,[0,.25,.5,.75,.95,1])))) if values else None

def audit(policy):
    counts=Counter(); groups={}; distributions={k:[] for k in ('absolute_deviation','standardized_deviation','threshold','mae_scale')}
    for meta,state in entries(policy['data_version'],'daily'):
        daily,bookings=inputs(meta); rows=daily.to_dict('records'); errors=horizon_errors(meta,policy)
        for cutoff in pd.date_range('2017-06-01','2017-08-24'):
            dates,values,latest=daily_prediction(meta,state,daily,bookings,cutoff)
            forecasts=[dict(forecast_date=t.date(),predicted_guest_count=v) for t,v in zip(dates,values)]
            comparisons,unsupported=deviations(HistoricalContext(rows,latest,policy),forecasts)
            counts['origins']+=1;counts['candidate_comparisons']+=13
            counts['insufficient_support']+=len(unsupported);counts['supported_comparisons']+=len(comparisons)
            for c in comparisons:
                g=groups.setdefault(c['analysis'],Counter());g['supported']+=1
                error=errors[c['horizon']]['mae']
                if c['analysis']=='transition': error+=errors[c['horizon']-1]['mae']
                statistical=c['standardized_deviation']>policy['thresholds'][c['analysis']]
                reliable=c['absolute_deviation']>error
                for target in (counts,g):
                    target['historical_pass']+=statistical; target['mae_pass_independent']+=reliable
                    target['both_pass']+=statistical and reliable
                for key,value in [('absolute_deviation',c['absolute_deviation']),('standardized_deviation',c['standardized_deviation']),('threshold',policy['thresholds'][c['analysis']]),('mae_scale',error)]:distributions[key].append(value)
    return dict(counts=dict(counts),by_analysis={k:dict(v) for k,v in groups.items()},
                distributions={k:distribution(v) for k,v in distributions.items()},
                holdout_already_inspected=True)

if __name__=='__main__':
    source=ROOT/'artifacts/dss_v2/calibration.json'
    policy=json.loads(source.read_text())['policy']
    result=audit(policy)
    out=ROOT/'artifacts/dss_v2/sensitivity_audit.json'
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
