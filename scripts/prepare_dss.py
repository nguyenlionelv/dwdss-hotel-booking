"""Calibrate DSS against the selected immutable ML release, then verify serving."""
import json
from pathlib import Path

from pipeline.source_to_staging.common import sha256


def prepare_policies(models, snapshot, output, version):
    from ml.demand_forecast.data import load_snapshot

    models, snapshot, output = map(Path, (models, snapshot, output))
    daily, bookings, provenance = load_snapshot(snapshot)
    if provenance['data_version'] != version:
        raise ValueError('DSS snapshot differs from published data version')

    from ml.demand_forecast.registry import entries
    from ml.demand_forecast.predict import daily_prediction
    from scripts.calibrate_dss import calibrate
    from scripts.validate_dss_sensitivity import run as sensitivity
    from scripts.calibrate_allocation import calibrate as allocation
    from backend.app.services.decision_engine.recommendation_service import evaluate
    from backend.app.services.decision_engine.allocation_engine import allocate

    candidates = entries(version, 'daily', root=models)
    if not candidates or any(m['input_manifest_sha256'] != sha256(snapshot / 'input_manifest.json')
                             for m, _ in candidates):
        raise ValueError('DSS models differ from selected snapshot')
    binding = {'input_manifest_sha256': sha256(snapshot / 'input_manifest.json'),
               'model_registry_sha256': sha256(models / 'registry.json')}
    output.mkdir(parents=True, exist_ok=False)
    decision_path, allocation_path = output / 'policy.json', output / 'allocation_policy.json'
    calibrate(snapshot / 'daily_input.csv', decision_path, output / 'calibration.json')
    decision = sensitivity(output / 'calibration.json', snapshot / 'daily_input.csv',
                           output / 'sensitivity_validation.json', decision_path)
    resource = allocation(models, snapshot, output, allocation_path)
    hashes = {}
    for name, policy, path in [('decision', decision, decision_path), ('allocation', resource, allocation_path)]:
        if policy['data_version'] != version:
            raise ValueError('Calibrated DSS policy differs from selected release')
        policy['release_binding'] = binding
        path.write_text(json.dumps(policy, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        hashes[name] = sha256(path)
    cutoff = daily.full_date.max()
    rows = daily.to_dict('records')
    checks = []
    for metadata, state in candidates:
        dates, values, latest = daily_prediction(metadata, state, daily, bookings, cutoff)
        forecasts = [{'forecast_date': d.date(), 'predicted_guest_count': v} for d, v in zip(dates, values)]
        insights = evaluate(rows, forecasts, metadata, latest, version, decision, hashes['decision'])
        resources = allocate(forecasts, rows, latest, version, metadata['model_version'],
                             policy=resource, policy_hash=hashes['allocation'], as_of_date=cutoff)
        if insights['metadata']['status'] != 'READY' or resources['policy_evaluation']['availability'] != 'available':
            raise ValueError('Prepared DSS policies are not ready for selected daily models')
        checks.append({'model_id': metadata['model_id'], 'model_version': metadata['model_version'],
                       'decision_status': insights['metadata']['status'], 'insight_count': len(insights['insights']),
                       'allocation_policy': resources['selected_policy']})
    result = {'status': 'ready', 'data_version': version, **binding,
              'decision_sha256': hashes['decision'], 'allocation_sha256': hashes['allocation'],
              'selected_allocation_policy': resource['selected_policy'], 'models': checks}
    (output / 'readiness.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result
