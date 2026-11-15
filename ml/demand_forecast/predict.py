"""Inference from saved calibration. No fitting or notebook execution in requests."""
import argparse
import json
import os
import numpy as np
import pandas as pd
from . import imputed, causal
from .data import load_snapshot
from .registry import resolve
from pipeline.source_to_staging.common import sha256

class ForecastInputError(ValueError):
    pass

def inputs(metadata):
    path = os.getenv('DWDSS_SNAPSHOT_DIR', metadata['snapshot'])
    from pathlib import Path
    if sha256(Path(path) / 'input_manifest.json') != metadata['input_manifest_sha256']:
        raise ValueError('Artifact snapshot manifest mismatch')
    daily, bookings, provenance = load_snapshot(path)
    if provenance['data_version'] != metadata['data_version']:
        raise ValueError('Artifact snapshot dataset mismatch')
    return daily, bookings

def daily_prediction(metadata, state, daily, bookings, cutoff, horizon=7):
    cutoff = pd.Timestamp(cutoff)
    delay = metadata['availability_assumptions']['label_delay_days']
    latest = cutoff - pd.Timedelta(days=delay)
    if cutoff < pd.Timestamp(metadata.get('selection_available_from', metadata['training_cutoff'])):
        raise ForecastInputError('Cutoff precedes validation selection availability')
    if horizon not in range(1,8) or cutoff != cutoff.normalize():
        raise ForecastInputError('Daily horizon must be 1 to 7 with a calendar-date cutoff')
    if latest < pd.Timestamp(metadata['training_cutoff']) or cutoff > daily.full_date.max():
        raise ForecastInputError('Cutoff outside saved model availability and published history')
    frame = daily[daily.full_date.le(latest)].copy()
    available_bookings = bookings[bookings.full_date.le(latest)].copy()
    variant = metadata['imputation_policy']
    dates = [cutoff + pd.Timedelta(days=h) for h in range(1,horizon+1)]
    if variant == 'causal_history':
        engine = causal.Experiment(frame, available_bookings)
        series = engine.HISTORY
        mean = float(series.rolling(14,min_periods=3).mean().loc[latest])
        values = [max(0., mean + state['correction'][h-1][t.day_of_week]) for h,t in enumerate(dates,1)]
    else:
        engine = imputed.Experiment(frame, available_bookings)
        series = frame.target_guests.astype(float).copy()
        if variant == 'imputed_history':
            additions = engine.room_estimates(state['imputer'], latest).groupby('full_date').estimated_guests.sum()
            mask = engine.eligible_imputation(frame)
            series.loc[mask] = frame.loc[mask,'observed_total_guests'].astype(float) + frame.loc[mask,'full_date'].map(additions).fillna(0.)
        series.index = pd.DatetimeIndex(frame.full_date)
        stats = engine.history_stats(series)
        params = state['params']
        values = [engine.baseline('B4_weekday',series,stats,cutoff,h,params['reference'],params['correction'])[0]
                  for h in range(1,horizon+1)]
    if not np.isfinite(values).all():
        raise ForecastInputError('Insufficient usable history for this origin')
    return dates, values, latest

def predict(model_id, data_version, cutoff, horizon=7, kind='daily'):
    metadata,state = resolve(model_id,data_version,kind)
    daily,bookings = inputs(metadata)
    if kind == 'monthly':
        origin = state['origins'].get(str(pd.Timestamp(cutoff).date()))
        if origin is None or pd.Timestamp(cutoff) < pd.Timestamp('2017-05-31'):
            raise ForecastInputError('Monthly cutoff must be a saved month-end origin (2016-06 to 2017-08)')
        return metadata, origin
    dates,values,latest = daily_prediction(metadata,state,daily,bookings,cutoff,horizon)
    return metadata, {'dates':[str(d.date()) for d in dates],'predictions':values,'latest_label_date':str(latest.date())}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-id');p.add_argument('--data-version',required=True);p.add_argument('--cutoff',required=True)
    p.add_argument('--horizon',type=int,default=7);p.add_argument('--kind',choices=['daily','monthly'],default='daily')
    a=p.parse_args();m,r=predict(a.model_id,a.data_version,a.cutoff,a.horizon,a.kind)
    print(json.dumps({'model_id':m['model_id'],'model_version':m['model_version'],'forecast':r},default=str))

if __name__ == '__main__': main()
