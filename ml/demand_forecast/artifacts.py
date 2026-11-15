"""Versioned, local trusted artifacts with checksum and dataset compatibility checks."""
import json
import os
from pathlib import Path
import joblib
from pipeline.source_to_staging.common import ROOT, sha256

def artifact_root():
    return Path(os.getenv('DWDSS_MODEL_DIR', ROOT / 'artifacts/ml_serving/models'))

def save_bundle(folder, metadata, state):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    joblib.dump(state, folder / 'state.joblib')
    metadata = {**metadata, 'state_sha256': sha256(folder / 'state.joblib')}
    (folder / 'metadata.json').write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding='utf-8')
    return metadata

def load_bundle(folder, data_version):
    folder = Path(folder)
    metadata = json.loads((folder / 'metadata.json').read_text(encoding='utf-8'))
    if metadata['data_version'] != str(data_version):
        raise ValueError('Model artifact data version differs from published Mart')
    if sha256(folder / 'state.joblib') != metadata['state_sha256']:
        raise ValueError('Model artifact checksum mismatch')
    return metadata, joblib.load(folder / 'state.joblib')
