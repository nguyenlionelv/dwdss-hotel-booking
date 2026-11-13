"""Chronological protocols and population-specific metrics."""
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

def folds(daily):
    dates = pd.DatetimeIndex(daily.loc[daily.full_date.le('2017-05-31'), 'full_date'])
    return [dict(fold=f'F{i}', train_end=str(dates[t[-1]].date()),
                 eval_start=str(dates[v[0]].date()), eval_end=str(dates[v[-1]].date()))
            for i, (t, v) in enumerate(TimeSeriesSplit(n_splits=3).split(dates), 1)]

HOLDOUT = dict(fold='Holdout', train_end='2017-05-31', eval_start='2017-06-01', eval_end='2017-08-31')

def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value

def selected_metrics(metrics, model, variant):
    return clean(metrics[metrics.model.eq(model) & metrics.variant.eq(variant)].to_dict('records'))
