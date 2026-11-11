"""One command: prepare verified data/models, build Docker images and start the app.

Requires Python 3.12+ and a running Docker Desktop/Engine with Compose v2.
No host Python packages are needed: preparation runs in a temporary container.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def ensure_env(root):
    path = root / '.env'
    if not path.exists():
        with path.open('x', encoding='utf-8') as handle:
            handle.write('POSTGRES_DB=hotel_dwdss\nPOSTGRES_USER=hotel_user\n'
                         f'POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n'
                         'POSTGRES_HOST=localhost\nPOSTGRES_PORT=5432\n')
        print('Created local .env with a generated password (not displayed).', flush=True)
    settings = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.lstrip().startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        settings[key.strip()] = value.strip().strip('"').strip("'")
    settings.update({key: value for key, value in os.environ.items()
                     if key.startswith('POSTGRES_') or key in ('FRONTEND_PORT', 'BACKEND_PORT')})
    if not settings.get('POSTGRES_PASSWORD'):
        raise ValueError('Set POSTGRES_PASSWORD in .env before starting.')
    return settings


def verify_raw(root):
    manifest = json.loads((root / 'docs/data_dictionary/operations_source_set.json').read_text(encoding='utf-8'))
    for source_id, source in manifest['sources'].items():
        path = root / source['file']
        if not path.is_file():
            raise ValueError(f'Missing pinned {source_id} raw file: {source["file"]}. Restore the source files using docs/data_dictionary/source_manifest_20261110.md.')
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != source['sha256']:
            raise ValueError(f'{source_id} raw checksum differs from the selected manifest. Verify provenance before selecting a different source.')
        if source.get('metadata_file') and not (root / source['metadata_file']).is_file():
            raise ValueError(f'Missing {source_id} acquisition metadata: {source["metadata_file"]}')


def checked_relative(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to((root / 'artifacts/ml_serving').resolve()) or not path.is_dir():
        raise ValueError('Prepared model paths must be existing directories inside artifacts/ml_serving.')
    return path.relative_to(root).as_posix()


def write_override(root, output, prepared):
    models = checked_relative(root, prepared['models'])
    snapshot = checked_relative(root, prepared['snapshot'])
    override = {'services': {'backend': {'build': {'args': {
        'MODEL_ARTIFACT_PATH': models, 'MODEL_SNAPSHOT_PATH': snapshot,
    }}}}}
    path = output / 'compose.json'
    path.write_text(json.dumps(override, indent=2), encoding='utf-8')
    return path


def compose_command(root):
    return ['docker', 'compose', '--project-directory', str(root), '--env-file', str(root / '.env'), '-f', str(root / 'docker-compose.yml')]


def execute(command, root):
    result = subprocess.run(command, cwd=root)
    if result.returncode:
        raise RuntimeError(f'Command failed (exit {result.returncode}): {" ".join(command)}')


def get_json(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.load(response)


def wait_for_app(backend, frontend, prepared, timeout=120):
    deadline = time.monotonic() + timeout
    last_error = 'Services have not become ready.'
    query = urllib.parse.urlencode({'as_of_date': prepared['daily_cutoff'], 'horizon': 7})
    monthly_query = urllib.parse.urlencode({'as_of_date': prepared['monthly_cutoff']})
    while time.monotonic() < deadline:
        try:
            health = get_json(backend + '/health')
            if not all(health.get(key) for key in ['db_connected', 'mart_published', 'matches_active_dw']):
                raise ValueError('Backend health has no matching published Mart.')
            if health.get('data_version') != prepared['data_version']:
                raise ValueError('Backend is serving a different data version.')
            for base in (backend, frontend):
                daily = get_json(base + '/api/dss/demand-forecast?' + query)
                if daily.get('data_version') != prepared['data_version'] or len(daily.get('forecasts', [])) != 7:
                    raise ValueError('Daily inference or frontend API proxy did not match the prepared release.')
            monthly = get_json(backend + '/api/dss/monthly-demand-forecast?' + monthly_query)
            if monthly.get('data_version') != prepared['data_version'] or monthly.get('kind') != 'monthly':
                raise ValueError('Monthly inference did not match the prepared release.')
            with urllib.request.urlopen(frontend, timeout=5) as response:
                if response.status != 200:
                    raise ValueError('Frontend did not return HTTP 200.')
            return {'health': 'passed', 'daily_inference': 'passed', 'monthly_inference': 'passed', 'frontend_proxy': 'passed'}
        except (OSError, ValueError, urllib.error.URLError) as exc:
            last_error = type(exc).__name__
            time.sleep(2)
    raise RuntimeError(f'App readiness failed ({last_error}). Inspect docker compose logs backend frontend.')


def port(settings, key, default):
    value = int(settings.get(key, default))
    if not 1 <= value <= 65535:
        raise ValueError(f'{key} must be a valid TCP port.')
    return value


def start(root=ROOT, *, with_tests=False, tree_jobs=6):
    root = Path(root).resolve()
    if not shutil.which('docker'):
        raise RuntimeError('Docker was not found. Install/start Docker Desktop with Compose v2.')
    settings = ensure_env(root)
    verify_raw(root)
    backend = f'http://127.0.0.1:{port(settings, "BACKEND_PORT", 8000)}'
    frontend = f'http://127.0.0.1:{port(settings, "FRONTEND_PORT", 5173)}'
    identifier = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:8]
    output = root / 'artifacts/startup' / identifier
    output.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'running', 'steps': [], 'output': str(output)}
    compose = compose_command(root)

    def run(name, command):
        print(f'\n[{len(summary["steps"]) + 1}] {name}', flush=True)
        summary['steps'].append(name)
        execute(command, root)

    try:
        run('Check Docker', ['docker', 'info', '--format', '{{.ServerVersion}}'])
        run('Start PostgreSQL (preserve existing volume)', [*compose, 'up', '-d', '--wait', '--wait-timeout', '120', 'db'])
        run('Build pipeline tools', [*compose, 'build', 'pipeline'])
        report_dir = output / 'preparation'
        flags = ['--with-tests'] if with_tests else []
        run('Verify and rerun pipeline; prepare compatible models', [*compose, 'run', '--rm', '--no-deps', '-T',
            'pipeline', 'python', 'scripts/prepare_app.py', '--report-dir', report_dir.relative_to(root).as_posix(),
            '--tree-jobs', str(tree_jobs), *flags])
        prepared = json.loads((report_dir / 'prepared.json').read_text(encoding='utf-8'))
        if prepared.get('status') != 'completed':
            raise ValueError('Pipeline/model preparation did not complete.')
        override = write_override(root, output, prepared)
        selected = [*compose, '-f', str(override)]
        run('Build images and start the application', [*selected, 'up', '-d', '--build', '--no-deps',
            '--force-recreate', '--renew-anon-volumes', '--wait', '--wait-timeout', '180', 'backend', 'frontend'])
        summary['steps'].append('Verify live app, inference and frontend proxy')
        checks = wait_for_app(backend, frontend, prepared)
        summary.update(status='completed', data_version=prepared['data_version'], model_status=prepared['model_status'],
                       checks=checks, frontend=frontend, api_docs=backend + '/docs')
        print(f'\nReady: {frontend}/dss/demand-forecast\nAPI: {backend}/docs\nReports: {output}', flush=True)
        return summary
    except (Exception, KeyboardInterrupt) as exc:
        summary.update(status='failed', failed_step=summary['steps'][-1] if summary['steps'] else 'preflight', error_type=type(exc).__name__)
        raise
    finally:
        (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-tests', action='store_true', help='Also run the existing Staging/DW/Mart integration suites')
    parser.add_argument('--tree-jobs', type=int, choices=range(1, 13), default=6)
    args = parser.parse_args()
    try:
        start(with_tests=args.with_tests, tree_jobs=args.tree_jobs)
        return 0
    except KeyboardInterrupt:
        print('Startup interrupted. Existing data and completed reports are retained.', file=sys.stderr)
        return 130
    except Exception as exc:
        print(f'Startup failed: {exc}\nNo database reset or volume deletion was attempted.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
