"""Startup orchestration safety tests; no Docker or database mutations."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('startup', ROOT / 'scripts/start_app.py')
startup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(startup)


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / '.env').write_text('POSTGRES_PASSWORD=test-only-secret\n', encoding='utf-8')
        folder = self.root / 'docs/data_dictionary'
        folder.mkdir(parents=True)
        raw = self.root / 'data/raw/input.csv'
        raw.parent.mkdir(parents=True)
        raw.write_bytes(b'input\n')
        self.raw = raw
        (folder / 'operations_source_set.json').write_text(json.dumps({'sources': {
            'booking': {'file': 'data/raw/input.csv', 'sha256': hashlib.sha256(raw.read_bytes()).hexdigest()}
        }}), encoding='utf-8')
        self.models = self.root / 'artifacts/ml_serving/models'
        self.snapshot = self.models.parent / 'snapshot'
        self.models.mkdir(parents=True)
        self.snapshot.mkdir()

    def test_env_is_preserved_and_password_not_logged(self):
        before = (self.root / '.env').read_bytes()
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(output):
            startup.ensure_env(self.root)
        self.assertEqual((self.root / '.env').read_bytes(), before)
        self.assertNotIn('test-only-secret', output.getvalue())

    def test_raw_checksum_mismatch_stops_before_docker(self):
        self.raw.write_bytes(b'changed')
        with patch.object(startup.shutil, 'which', return_value='docker'), patch.object(startup, 'execute') as execute:
            with self.assertRaisesRegex(ValueError, 'checksum'):
                startup.start(self.root)
            execute.assert_not_called()

    def test_model_paths_cannot_escape_artifact_directory(self):
        with self.assertRaises(ValueError):
            startup.write_override(self.root, self.root, {'models': '../../outside', 'snapshot': str(self.snapshot)})

    def fake_execute(self, commands):
        def run(command, root):
            commands.append(command)
            if 'scripts/prepare_app.py' in command:
                output = root / command[command.index('--report-dir') + 1]
                output.mkdir(parents=True)
                (output / 'prepared.json').write_text(json.dumps({
                    'status': 'completed', 'model_status': 'reused', 'data_version': 'v1',
                    'models': 'artifacts/ml_serving/models', 'snapshot': 'artifacts/ml_serving/snapshot',
                    'daily_cutoff': '2017-08-24', 'monthly_cutoff': '2017-08-31',
                }))
        return run

    def test_full_order_and_selected_artifacts_are_passed_to_build(self):
        commands = []
        with patch.object(startup.shutil, 'which', return_value='docker'), \
             patch.object(startup, 'execute', side_effect=self.fake_execute(commands)), \
             patch.object(startup, 'wait_for_app', return_value={'health': 'passed'}) as ready, \
             contextlib.redirect_stdout(io.StringIO()):
            result = startup.start(self.root, with_tests=True)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['data_version'], 'v1')
        self.assertIn('--with-tests', commands[3])
        self.assertIn('pipeline', commands[3])
        self.assertIn('--build', commands[4])
        self.assertIn('--no-deps', commands[4])
        self.assertIn('--renew-anon-volumes', commands[4])
        self.assertNotIn('down', [arg for command in commands for arg in command])
        override = json.loads(next((self.root / 'artifacts/startup').glob('*/compose.json')).read_text())
        self.assertEqual(override['services']['backend']['build']['args']['MODEL_ARTIFACT_PATH'], 'artifacts/ml_serving/models')
        ready.assert_called_once()

    def test_preparation_failure_prevents_app_build_and_readiness(self):
        commands = []
        def fail(command, root):
            commands.append(command)
            if 'scripts/prepare_app.py' in command:
                raise RuntimeError('quality gate failed')
        with patch.object(startup.shutil, 'which', return_value='docker'), \
             patch.object(startup, 'execute', side_effect=fail), \
             patch.object(startup, 'wait_for_app') as ready, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'quality gate'):
                startup.start(self.root)
        ready.assert_not_called()
        self.assertEqual(len(commands), 4)
        summary = json.loads(next((self.root / 'artifacts/startup').glob('*/summary.json')).read_text())
        self.assertEqual(summary['status'], 'failed')

    def test_readiness_rejects_another_data_version(self):
        with patch.object(startup, 'get_json', return_value={'db_connected': True,
                'mart_published': True, 'matches_active_dw': True, 'data_version': 'stale'}), \
             patch.object(startup.time, 'monotonic', side_effect=[0, 0, 3]), patch.object(startup.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'readiness failed'):
                startup.wait_for_app('http://backend', 'http://frontend', {'data_version': 'v1',
                    'daily_cutoff': '2017-08-24', 'monthly_cutoff': '2017-08-31'}, timeout=1)


if __name__ == '__main__':
    unittest.main()
