"""Offline reproduction, validation-only selection and artifact publication."""
import json
from pathlib import Path
from uuid import uuid4
import pandas as pd
from . import imputed, causal, monthly
from .artifacts import save_bundle
from .data import load_snapshot
from .evaluation import folds, HOLDOUT, clean, selected_metrics
from pipeline.source_to_staging.common import ROOT, sha256

def write_json(path, value):
    Path(path).write_text(json.dumps(clean(value), indent=2, allow_nan=False), encoding='utf-8')

def train(snapshot, output, resume=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=resume)
    daily, bookings, provenance = load_snapshot(snapshot)
    registry = []
    version = uuid4().hex[:12]
    checkpoint = output / 'checkpoint.json'
    completed = []
    if resume and checkpoint.exists():
        from .artifacts import load_bundle
        prior = json.loads(checkpoint.read_text())
        if prior['input_manifest_sha256'] != sha256(Path(snapshot) / 'input_manifest.json'):
            raise ValueError('Cannot resume on a different snapshot')
        registry, completed = prior['models'], prior['completed']
        for entry in registry:
            if sha256(output / entry['folder'] / 'metadata.json') != entry['metadata_sha256']:
                raise ValueError('Resume metadata changed')
            load_bundle(output / entry['folder'], provenance['data_version'])
        if set(completed) == {'imputed', 'causal', 'monthly'}:
            print('All protocols already completed; snapshot and fitted artifacts verified.', flush=True)
            return

    def save(model_id, kind, algorithm, variant, state, metrics, cutoff, notebook, default=False):
        metadata = {'model_id': model_id, 'kind': kind, 'model_version': model_id + '-' + version,
            'algorithm': algorithm, 'data_version': provenance['data_version'], 'training_cutoff': cutoff,
            'imputation_policy': variant, 'label_definition': provenance['label_definition'],
            'validation_metrics': metrics, 'default': default,
            'feature_schema': ['mean_14', 'horizon', 'target_weekday', 'train_residual_correction'] if kind == 'daily' else ['last_month_guest_rate', 'days_in_target_month'],
            'availability_assumptions': {'label_delay_days': 1 if variant == 'causal_history' else 0,
                'point_in_time_verified': False, 'estimated_labels_are_ground_truth': False},
            'notebook': notebook, 'notebook_sha256': sha256(ROOT / notebook),
            'snapshot': str(Path(snapshot).resolve()), 'input_manifest_sha256': sha256(Path(snapshot) / 'input_manifest.json'),
            'metric_protocol': 'three expanding folds, equal-fold ALL_ESTIMATED MAE' if kind == 'daily' else '11 rolling one-month validation origins, guests/month'}
        save_bundle(output / model_id, metadata, state)
        registry.append({'model_id': model_id, 'kind': kind, 'folder': model_id,
                         'metadata_sha256': sha256(output / model_id / 'metadata.json')})

    for name, module in [('imputed', imputed), ('causal', causal)]:
        if name in completed:
            continue
        print('Reproducing', name, flush=True)
        if name == 'causal':
            from .execution import CausalExperiment
            engine = CausalExperiment(daily, bookings)
        else:
            engine = module.Experiment(daily, bookings)
        parts = []
        for fold in folds(daily):
            state = engine.train_fold(fold) if name == 'imputed' else engine.train_bundle(fold)
            raw = engine.forecast_fold(state) if name == 'imputed' else engine.forecast_bundle(state)
            parts.append(engine.attach_truth(raw, state['labels']))
        validation = pd.concat(parts, ignore_index=True)
        metrics = engine.score_groups(validation)
        metrics.to_csv(output / (name + '_validation_metrics.csv'), index=False)
        engine.score_groups(validation, by_horizon=True).to_csv(output / (name + '_validation_horizon.csv'), index=False)
        ranking = metrics[metrics.population.eq('ALL_ESTIMATED')].pivot(index=['variant', 'model'], columns='fold', values='MAE')
        scores = ranking.mean(axis=1)
        selections = {variant: engine.select_model(scores.loc[variant], module.MODELS + module.ML_MODELS if name == 'imputed' else module.ORDER)
                      for variant in validation.variant.unique()}
        write_json(output / (name + '_selection.json'), selections)
        holdout = engine.train_fold(HOLDOUT) if name == 'imputed' else engine.train_bundle(HOLDOUT)
        raw = engine.forecast_fold(holdout) if name == 'imputed' else engine.forecast_bundle(holdout)
        engine.score_groups(engine.attach_truth(raw, holdout['labels'])).to_csv(output / (name + '_holdout_metrics.csv'), index=False)
        for variant, algorithm in selections.items():
            expected = 'B4_weekday' if name == 'imputed' else 'B4_matched'
            if algorithm != expected:
                raise ValueError(f'Validation selected {algorithm}; extend artifact adapter before publishing (expected {expected})')
            state = ({'params': holdout['states'][variant]['params'], 'imputer': holdout['imputer']}
                     if name == 'imputed' else {'correction': holdout['correction'].tolist()})
            cutoff = '2017-05-31' if name == 'imputed' else '2017-05-30'
            save(name + '_' + variant, 'daily', algorithm, variant, state,
                 {'populations': selected_metrics(metrics, algorithm, variant),
                  'horizon': selected_metrics(engine.score_groups(validation, True), algorithm, variant)},
                 cutoff, 'notebooks/experiments/history_demand_' + ('imputed_3fold' if name == 'imputed' else 'causal_methods') + '_report.ipynb', name == 'causal')
        completed.append(name)
        write_json(checkpoint, {'models': registry, 'completed': completed,
                   'input_manifest_sha256': sha256(Path(snapshot) / 'input_manifest.json')})

    print('Reproducing monthly', flush=True)
    engine = monthly.Experiment(daily, bookings)
    validation = pd.concat([engine.run_origin(m, 'validation') for m in pd.period_range('2016-07', '2017-05', freq='M')])
    metrics = engine.metrics(validation)
    best = metrics.MAE.min()
    algorithm = next(m for m in monthly.MODELS if metrics.set_index('model').at[m, 'MAE'] <= best * 1.01 + 1e-12)
    metrics.to_csv(output / 'monthly_validation_metrics.csv', index=False)
    if algorithm != 'M0_last_month_rate':
        raise ValueError('Monthly selection changed; extend serving adapter before publishing')
    test = pd.concat([engine.run_origin(m, 'holdout') for m in pd.period_range('2017-06', '2017-08', freq='M')])
    engine.metrics(test).to_csv(output / 'monthly_holdout_metrics.csv', index=False)
    origins = {}
    for month in pd.period_range('2016-06', '2017-08', freq='M'):
        cutoff = month.end_time.normalize()
        labels, imputer = engine.monthly_labels(cutoff, cutoff)
        if not (labels.calendar_days.to_numpy() == labels.index.days_in_month).all():
            raise ValueError('Incomplete calendar month')
        origins[str(cutoff.date())] = {'forecast_month': str(month + 1), 'training_cutoff': str(cutoff.date()),
            'predicted_guests': engine.predict_month(algorithm, labels, month + 1), 'imputer': imputer}
    save('monthly_last_month_rate', 'monthly', algorithm, 'room_type_mean', {'origins': origins},
         clean(metrics[metrics.model.eq(algorithm)].to_dict('records')), '2017-08-31',
         'notebooks/experiments/monthly_demand_forecast_report.ipynb', True)
    write_json(output / 'provenance.json', provenance)
    write_json(output / 'registry.json', {'models': registry})
    from .package_artifacts import package
    package(output)
    print('Published registry:', output / 'registry.json', flush=True)
