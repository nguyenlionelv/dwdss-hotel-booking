"""Reject wrong release inputs before calibrating or publishing any DSS files."""
import os
import json
import shutil
import pytest
from scripts.prepare_dss import prepare_policies


def test_wrong_snapshot_version_cannot_generate_policies(tmp_path, monkeypatch):
    monkeypatch.setattr('ml.demand_forecast.data.load_snapshot',
                        lambda _: (None, None, {'data_version': 'old'}))
    with pytest.raises(ValueError, match='snapshot differs'):
        prepare_policies(tmp_path/'models', tmp_path/'snapshot', tmp_path/'policies', 'new')
    assert not (tmp_path/'policies').exists()


@pytest.mark.skipif(os.getenv('DWDSS_INTEGRATION') != '1', reason='Requires local trained models and snapshot')
def test_calibrate_nondefault_release_without_rewriting_reference_artifacts(tmp_path):
    from pipeline.source_to_staging.common import ROOT, sha256
    source = ROOT/'artifacts/ml_serving'
    snapshot, models = tmp_path/'snapshot', tmp_path/'models'
    shutil.copytree(source/'snapshot', snapshot)
    shutil.copytree(source/'models', models)
    # Simulate identical observations published under a different dataset identity.
    # This fixture changes identity only; production must always rerun calibration.
    version = 'integration-new-data-version'
    provenance = json.loads((snapshot/'provenance.json').read_text())
    old_version = provenance['data_version']
    for name in ('daily_input.csv', 'provenance.json', 'quality.json'):
        p = snapshot/name
        p.write_text(p.read_text(encoding='utf-8').replace(old_version, version), encoding='utf-8')
    manifest_path = snapshot/'input_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest_path.write_text(json.dumps({name: sha256(snapshot/name) for name in manifest}), encoding='utf-8')
    registry_path = models/'registry.json'
    registry = json.loads(registry_path.read_text())
    for entry in registry['models']:
        p = models/entry['folder']/'metadata.json'
        metadata = json.loads(p.read_text())
        metadata.update(data_version=version, snapshot=str(tmp_path/'must-not-use-this-snapshot'),
                        input_manifest_sha256=sha256(manifest_path))
        p.write_text(json.dumps(metadata), encoding='utf-8')
        entry['metadata_sha256'] = sha256(p)
    registry_path.write_text(json.dumps(registry), encoding='utf-8')
    reference = ROOT/'backend/app/services/decision_engine'
    before = {name: sha256(reference/name) for name in ('policy.json', 'allocation_policy.json')}
    result = prepare_policies(models, snapshot, tmp_path/'policies', version)
    assert result['status'] == 'ready' and result['data_version'] == version
    assert result['selected_allocation_policy'] == 'historical_weekday'
    assert len(result['models']) == 3 and all(m['decision_status'] == 'READY' for m in result['models'])
    for name, digest in before.items():
        assert sha256(reference/name) == digest
        policy = json.loads((tmp_path/'policies'/name).read_text())
        assert policy['data_version'] == version
        assert policy['release_binding']['input_manifest_sha256'] == sha256(manifest_path)
        if name == 'policy.json':
            assert policy['snapshot_sha256'] == sha256(snapshot/'daily_input.csv')
    allocation = json.loads((tmp_path/'policies/allocation_policy.json').read_text())
    assert allocation['validation_results']['eligible_origins'] > 0
