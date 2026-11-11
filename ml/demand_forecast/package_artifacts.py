"""Attach reproducible benchmark evidence and environment metadata before serving."""
import importlib.metadata
import json
import os
from pathlib import Path
import pandas as pd
from .evaluation import clean
from pipeline.source_to_staging.common import sha256


def package(output):
    output = Path(output)
    registry = json.loads((output / 'registry.json').read_text(encoding='utf-8'))
    for entry in registry['models']:
        path = output / entry['folder'] / 'metadata.json'
        metadata = json.loads(path.read_text(encoding='utf-8'))
        metadata['environment'] = {p: importlib.metadata.version(p) for p in ['numpy', 'pandas', 'scikit-learn', 'joblib']}
        metadata['execution'] = {'tree_jobs': int(os.getenv('DWDSS_TREE_JOBS', '1')) if metadata['imputation_policy'] == 'causal_history' else 1, 'random_state': 42,
            'note': 'Tree worker count affects execution only; serial/parallel numerical parity is tested.'}
        metadata['selection_available_from'] = '2017-06-01' if metadata['imputation_policy'] == 'causal_history' else '2017-05-31'
        if metadata['kind'] == 'daily':
            protocol = 'causal' if metadata['imputation_policy'] == 'causal_history' else 'imputed'
            metrics = pd.read_csv(output / (protocol + '_validation_metrics.csv'))
            horizon = pd.read_csv(output / (protocol + '_validation_horizon.csv'))
            mask = metrics.variant.eq(metadata['imputation_policy']) & metrics.population.eq('ALL_ESTIMATED')
            rows = []
            for algorithm, group in metrics[mask].groupby('model', sort=False):
                h = horizon[horizon.variant.eq(metadata['imputation_policy']) & horizon.population.eq('ALL_ESTIMATED') & horizon.model.eq(algorithm)]
                active = algorithm == metadata['algorithm']
                rows.append(dict(model_name=metadata['model_id'] if active else algorithm, model_label=algorithm,
                    is_baseline=algorithm.startswith('B'), is_selected=active, available_for_inference=active,
                    overall_mae=float(group.MAE.mean()), overall_rmse=float(group.RMSE.mean()),
                    horizon_mae={str(int(k)): float(v) for k, v in h.groupby('horizon').MAE.mean().items()},
                    metric_protocol=metadata['metric_protocol'], population='ALL_ESTIMATED'))
            metadata['benchmark_comparison'] = rows
            metadata['feature_schema'] = (['history_mean_14_min3', 'horizon', 'target_weekday', 'train_residual_correction']
                if protocol == 'causal' else ['history_mean_14', 'history_count_14', 'history_mean_28', 'history_count_28',
                    'train_weekday_mean', 'horizon', 'target_weekday', 'train_residual_correction'])
        path.write_text(json.dumps(clean(metadata), indent=2, allow_nan=False), encoding='utf-8')
        entry['metadata_sha256'] = sha256(path)
    (output / 'registry.json').write_text(json.dumps(registry, indent=2), encoding='utf-8')
    checkpoint = output / 'checkpoint.json'
    if checkpoint.exists():
        prior = json.loads(checkpoint.read_text(encoding='utf-8'))
        prior.update(models=registry['models'], completed=['imputed', 'causal', 'monthly'])
        checkpoint.write_text(json.dumps(prior, indent=2), encoding='utf-8')


if __name__ == '__main__':
    import argparse
    from .artifacts import artifact_root
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=artifact_root())
    package(parser.parse_args().output)
