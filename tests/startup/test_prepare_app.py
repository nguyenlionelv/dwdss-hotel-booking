"""Verify model reuse/new-release behavior and fail-fast pipeline sequencing."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('prepare', ROOT / 'scripts/prepare_app.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.models = self.root / 'artifacts/ml_serving/models'
        self.models.mkdir(parents=True)
        self.sentinel = self.models / 'retained.txt'
        self.sentinel.write_text('existing model release')
        self.reports = self.root / 'reports'
        self.reports.mkdir()

    def test_compatible_models_are_reused_without_training(self):
        with patch.object(prepare, 'ROOT', self.root), \
             patch.object(prepare, 'compatible_models', return_value={'model_ids': ['daily', 'monthly']}), \
             patch('ml.demand_forecast.data.export_snapshot') as export, \
             patch('ml.demand_forecast.training.train') as train:
            models, snapshot, result = prepare.select_models('v1', 'source1', self.reports, 6)
        export.assert_not_called()
        train.assert_not_called()
        self.assertEqual(models, self.models)
        self.assertEqual(result['status'], 'reused')

    def test_stale_models_train_in_new_release_and_preserve_old_artifacts(self):
        def export(snapshot):
            snapshot.mkdir(parents=True)
        def train(snapshot, models):
            models.mkdir()
        with patch.object(prepare, 'ROOT', self.root), \
             patch.object(prepare, 'compatible_models', side_effect=[ValueError('old version'), {'model_ids': ['fresh']}]), \
             patch('ml.demand_forecast.data.export_snapshot', side_effect=export) as export_mock, \
             patch('ml.demand_forecast.training.train', side_effect=train) as train_mock, \
             contextlib.redirect_stdout(io.StringIO()):
            models, snapshot, result = prepare.select_models('v2', 'source2', self.reports, 6)
        self.assertEqual(result['status'], 'trained')
        self.assertNotEqual(models, self.models)
        self.assertTrue(models.is_relative_to(self.models.parent / 'releases'))
        self.assertEqual(self.sentinel.read_text(), 'existing model release')
        export_mock.assert_called_once_with(snapshot)
        train_mock.assert_called_once_with(snapshot, models)

    def test_quality_failure_stops_before_dw_or_model_work(self):
        calls = []
        def command(*args):
            calls.append(args)
            if args[0] == 'pipeline/quality/staging_checks.py':
                raise RuntimeError('quality failed')
        output = self.root / 'preparation'
        with patch.object(prepare, 'source_set', return_value=('v1', {}, 'fingerprint')), \
             patch.object(prepare, 'inspect_database', return_value={}), \
             patch.object(prepare, 'command', side_effect=command), \
             patch.object(prepare, 'select_models') as select:
            with self.assertRaisesRegex(RuntimeError, 'quality failed'):
                prepare.prepare(output)
        self.assertEqual(len(calls), 3)
        select.assert_not_called()
        self.assertEqual(json.loads((output / 'failed.json').read_text())['step'], 'staging_quality')

    def test_snapshot_version_mismatch_is_rejected_before_loading_models(self):
        with patch('ml.demand_forecast.data.load_snapshot', return_value=(None, None, {'data_version': 'old', 'source_set_fingerprint': 's'})), \
             patch('ml.demand_forecast.registry.entries') as entries:
            with self.assertRaisesRegex(ValueError, 'differs'):
                prepare.compatible_models(self.models, self.root / 'snapshot', 'new', 's')
        entries.assert_not_called()


if __name__ == '__main__':
    unittest.main()
