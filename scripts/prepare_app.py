"""Container-side preparation: verified pipeline, compatible ML and build inputs."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.source_to_staging.common import connect, sha256, source_set


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, default=str)
        handle.write('\n')


def command(*args):
    result = subprocess.run([sys.executable, *map(str, args)], cwd=ROOT)
    if result.returncode:
        raise RuntimeError(f'Preparation step failed: {args[0]}; exit {result.returncode}')


def inspect_database():
    # Inspect before any migration; never reset or adopt credentials for a volume.
    with connect() as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        tables = conn.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('staging','dw','mart') ORDER BY 1,2").fetchall()
        return {'database': conn.execute('SELECT current_database()').fetchone()[0],
                'tables_before': [{'schema': schema, 'table': table} for schema, table in tables]}


def compatible_models(models, snapshot, version, fingerprint):
    import pandas as pd
    from ml.demand_forecast.data import load_snapshot
    from ml.demand_forecast.registry import entries
    from ml.demand_forecast.predict import daily_prediction

    daily, bookings, provenance = load_snapshot(snapshot)
    if provenance['data_version'] != version or provenance['source_set_fingerprint'] != fingerprint:
        raise ValueError('ML input snapshot differs from published data')
    candidates = entries(version, root=models)
    if {m['kind'] for m, _ in candidates} != {'daily', 'monthly'}:
        raise ValueError('Daily and monthly artifacts are required')
    for kind in ('daily', 'monthly'):
        if sum(m['kind'] == kind and m.get('default') is True for m, _ in candidates) != 1:
            raise ValueError('Each forecasting kind requires exactly one default')
    cutoff = daily.full_date.max()
    for metadata, state in candidates:
        if sha256(snapshot / 'input_manifest.json') != metadata['input_manifest_sha256']:
            raise ValueError('Artifact input manifest differs from snapshot')
        if sha256(ROOT / metadata['notebook']) != metadata['notebook_sha256']:
            raise ValueError('Source notebook changed since training')
        for package, version_pin in metadata.get('environment', {}).items():
            if importlib.metadata.version(package) != version_pin:
                raise ValueError('Model dependency version changed')
        if metadata['kind'] == 'daily':
            daily_prediction(metadata, state, daily, bookings, cutoff)
        elif str(daily.full_date.max().date()) not in state['origins']:
            raise ValueError('Monthly artifact has no final month-end origin')
    return {'model_ids': [m['model_id'] for m, _ in candidates],
            'daily_cutoff': str(cutoff.date()), 'monthly_cutoff': str(daily.full_date.max().date())}


def select_models(version, fingerprint, report_dir, tree_jobs):
    from ml.demand_forecast.data import export_snapshot
    from ml.demand_forecast.training import train

    base = ROOT / 'artifacts/ml_serving'
    candidates = [(base / 'models', base / 'snapshot')]
    candidates.extend((release / 'models', release / 'snapshot')
                      for release in sorted((base / 'releases').glob('*'), reverse=True) if release.is_dir())
    rejected = []
    for models, snapshot in candidates:
        try:
            details = compatible_models(models, snapshot, version, fingerprint)
            return models, snapshot, {'status': 'reused', **details}
        except (OSError, ValueError, KeyError, AssertionError, TypeError, ImportError) as exc:
            rejected.append({'models': str(models.relative_to(ROOT)), 'reason': type(exc).__name__})
    save(report_dir / 'model_candidates.json', rejected)
    release = base / 'releases' / ('run_' + uuid4().hex)
    models, snapshot = release / 'models', release / 'snapshot'
    print('No compatible artifacts: exporting and training a new ML release. This can take several minutes.', flush=True)
    export_snapshot(snapshot)
    os.environ['DWDSS_TREE_JOBS'] = str(tree_jobs)
    train(snapshot, models)
    details = compatible_models(models, snapshot, version, fingerprint)
    return models, snapshot, {'status': 'trained', **details}


def prepare(report_dir, *, with_tests=False, tree_jobs=6):
    report_dir = Path(report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=False)
    step = 'source_verification'
    try:
        _, _, fingerprint = source_set()
        save(report_dir / 'sources.json', {'passed': True, 'fingerprint': fingerprint})
        step = 'database_inspection'
        save(report_dir / 'database_before.json', inspect_database())
        step = 'staging_migration'
        command('scripts/setup_db.py', '--report', report_dir / 'staging_migration.json')
        step = 'staging_load'
        command('scripts/run_pipeline.py', '--to', 'staging', '--report', report_dir / 'staging_load.json')
        step = 'staging_quality'
        command('pipeline/quality/staging_checks.py', '--report', report_dir / 'staging_quality.json')
        step = 'dw_mart'
        flags = ['--with-tests'] if with_tests else []
        command('scripts/run_pipeline.py', '--to', 'dw', '--with-mart', '--output-dir', report_dir / 'dw', *flags)
        summary = json.loads((report_dir / 'dw/summary.json').read_text(encoding='utf-8'))
        if summary.get('status') != 'completed' or not summary.get('verified') or not summary.get('mart_verified'):
            raise ValueError('DW/Mart workflow did not verify its publication')
        step = 'models'
        models, snapshot, details = select_models(summary['data_version'], fingerprint, report_dir, tree_jobs)
        model_status = details.pop('status')
        step = 'dss_policies'
        from scripts.prepare_dss import prepare_policies
        policies = report_dir / 'policies'
        policy_details = prepare_policies(models, snapshot, policies, summary['data_version'])
        result = {'status': 'completed', 'model_status': model_status,
                  'data_version': summary['data_version'], 'run_id': summary['run_id'],
                  'models': models.relative_to(ROOT).as_posix(), 'snapshot': snapshot.relative_to(ROOT).as_posix(),
                  'policies': policies.relative_to(ROOT).as_posix(), 'dss_policies': policy_details, **details}
        save(report_dir / 'prepared.json', result)
        return result
    except Exception as exc:
        save(report_dir / 'failed.json', {'status': 'failed', 'step': step, 'error_type': type(exc).__name__})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-dir', type=Path, required=True)
    parser.add_argument('--with-tests', action='store_true')
    parser.add_argument('--tree-jobs', type=int, choices=range(1, 13), default=6)
    args = parser.parse_args()
    try:
        result = prepare(args.report_dir, with_tests=args.with_tests, tree_jobs=args.tree_jobs)
        print(json.dumps(result))
        return 0
    except Exception as exc:
        # Driver exceptions may include connection settings; keep credentials out.
        print(f'Preparation failed ({type(exc).__name__}). Inspect reports and PostgreSQL settings; no database reset was attempted.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
