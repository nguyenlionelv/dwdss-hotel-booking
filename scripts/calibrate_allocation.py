"""Select allocation policy on causal development proxy; audit saved holdout separately.

Never trains or rewrites the ML model artifacts. Existing saved daily models are
not available for pre-selection validation origins, so proxy results must not be
described as saved-model validation accuracy.
"""

from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path
from statistics import mean

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.decision_engine.allocation_evaluator import choose_policy, score_origin, summarize  # noqa: E402
from backend.app.services.decision_engine.historical_context import weekday_allocation_reference  # noqa: E402
from ml.demand_forecast.registry import entries  # noqa: E402
from ml.demand_forecast.predict import daily_prediction, inputs  # noqa: E402

OUT = ROOT / 'artifacts/allocation'
POLICY = ROOT / 'backend/app/services/decision_engine/allocation_policy.json'


def eligible_actuals(daily):
    return {date.date(): float(value) for date, value, status in
            daily[['full_date', 'target_guests', 'guest_data_status']].itertuples(index=False, name=None)
            if status == 'COMPLETE' and pd.notna(value) and float(value) >= 0}


def history_rows(daily):
    return daily[['full_date', 'target_guests', 'guest_data_status']].to_dict('records')


def proxy_forecast(rows, dates, latest, references):
    """A predefined causal recent-level probe, not a saved-model replay."""
    known = [(pd.Timestamp(row['full_date']).date(), float(row['target_guests'])) for row in rows
             if row['guest_data_status'] == 'COMPLETE' and pd.notna(row['target_guests'])
             and 0 <= float(row['target_guests']) and pd.Timestamp(row['full_date']).date() <= latest]
    recent14 = [value for day, value in known if latest - timedelta(days=13) <= day <= latest]
    recent56 = [value for day, value in known if latest - timedelta(days=55) <= day <= latest]
    if len(recent14) < 10 or len(recent56) < 42:
        return None
    adjustment = mean(recent14) - mean(recent56)
    return [max(0, reference + adjustment) for reference in references]


def development(daily, rows, actuals):
    calibration, validation = [], []
    for origin in pd.date_range('2016-07-01', '2017-05-24'):
        cutoff = origin.date()
        latest = cutoff - timedelta(days=1)  # conservative causal-model label delay
        dates = [cutoff + timedelta(days=h) for h in range(1, 8)]
        actual = [actuals.get(target) for target in dates]
        if any(value is None for value in actual) or sum(actual) <= 0:
            continue
        references, _ = weekday_allocation_reference(rows, dates, latest)
        if references is None:
            continue
        forecast = proxy_forecast(rows, dates, latest, references)
        if forecast is None:
            continue
        scores = score_origin(forecast, references, actual)
        if scores is None:
            continue
        row = {'origin': cutoff.isoformat(), 'scores': scores,
               'forecast_mae': mean(abs(a - f) for a, f in zip(actual, forecast))}
        (calibration if cutoff < pd.Timestamp('2017-01-01').date() else validation).append(row)
    return calibration, validation


def holdout(model_entries, policy, snapshot=None):
    from ml.demand_forecast.data import load_snapshot
    models = []
    for metadata, state in model_entries:
        if snapshot is None:
            daily, bookings = inputs(metadata)
        else:
            daily, bookings, _ = load_snapshot(snapshot)
        actuals, rows = eligible_actuals(daily), history_rows(daily)
        scored, maes = [], []
        for origin in pd.date_range('2017-06-01', '2017-08-24'):
            dates, values, latest = daily_prediction(metadata, state, daily, bookings, origin)
            actual = [actuals.get(target.date()) for target in dates]
            if any(value is None for value in actual) or sum(actual) <= 0:
                continue
            references, _ = weekday_allocation_reference(rows, dates, latest.date())
            if references is None:
                continue
            scores = score_origin(values, references, actual)
            if scores is None:
                continue
            scored.append({'origin': origin.date().isoformat(), 'scores': scores})
            maes.append(mean(abs(a - f) for a, f in zip(actual, values)))
        selected = policy['selected_policy']
        key = f"blended_{policy['lambda']:g}" if selected == 'blended' else selected
        result = summarize(scored, key)
        result['mean_forecast_mae_on_same_eligible_origins'] = mean(maes) if maes else None
        models.append({'model_id': metadata['model_id'], 'label_delay_days':
                       metadata['availability_assumptions']['label_delay_days'],
                       'metrics': result})
    return {'status': 'descriptive_only', 'holdout_already_inspected': True,
            'not_used_for_policy_selection': True, 'models': models}


def calibrate(models=None, snapshot=None, output=None, policy_path=None):
    from ml.demand_forecast.data import load_snapshot
    models = Path(models or ROOT / 'artifacts/ml_serving/models')
    snapshot = Path(snapshot or ROOT / 'artifacts/ml_serving/snapshot')
    output = Path(output or OUT)
    policy_path = Path(policy_path or POLICY)
    registry = json.loads((models / 'registry.json').read_text(encoding='utf-8'))
    first_folder = registry['models'][0]['folder']
    version = json.loads((models / first_folder / 'metadata.json').read_text(encoding='utf-8'))['data_version']
    model_entries = entries(version, 'daily', root=models)
    daily, _, provenance = load_snapshot(snapshot)
    if provenance['data_version'] != version:
        raise ValueError('Snapshot/registry version mismatch')
    from pipeline.source_to_staging.common import sha256
    if any(m['input_manifest_sha256'] != sha256(snapshot / 'input_manifest.json') for m, _ in model_entries):
        raise ValueError('Snapshot/model manifest mismatch')
    rows, actuals = history_rows(daily), eligible_actuals(daily)
    calibration, validation = development(daily, rows, actuals)
    selected, lam, reason = choose_policy(validation)
    key = f'blended_{lam:g}' if selected == 'blended' else selected
    validation_result = summarize(validation, key)
    calibration_result = summarize(calibration, key)
    if validation_result['status'] != 'available':
        raise ValueError('Cannot select allocation policy without eligible validation windows')
    validation_result['mean_proxy_forecast_mae'] = mean(row['forecast_mae'] for row in validation)
    policy = {'policy_version': 'allocation-v1', 'data_version': version,
              'selected_policy': selected, 'lambda': lam,
              'selected_policy_reason': reason,
              'validation_results': validation_result,
              'calibration_results': calibration_result,
              'candidate_lambdas': [0, 0.25, 0.5, 0.75, 1.0],
              'selection_tolerance_mean_mrr': 0.002,
              'development_forecast_source': 'causal recent-level proxy, not saved-model validation forecasts',
              'development_label_delay_days': 1,
              'selection_uses_holdout': False,
              'holdout_already_inspected': True,
              'limitations': ['Saved final models have no archived per-origin pre-selection validation predictions.',
                              'Proxy selection does not establish model-specific validation superiority.',
                              'Overlapping seven-day origins are dependent.']}
    output.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(json.dumps(policy, indent=2) + '\n', encoding='utf-8')
    (output / 'validation.json').write_text(json.dumps({'calibration': calibration_result,
        'validation': validation_result, 'policy': {k: v for k, v in policy.items() if k not in ('validation_results', 'calibration_results')}},
        indent=2) + '\n', encoding='utf-8')
    descriptive = holdout(model_entries, policy, snapshot)
    (output / 'holdout_descriptive.json').write_text(json.dumps(descriptive, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'selected_policy': selected, 'lambda': lam,
                      'validation': validation_result, 'holdout': descriptive}, indent=2))
    return policy


if __name__ == '__main__':
    calibrate()
