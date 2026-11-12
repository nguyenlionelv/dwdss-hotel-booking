"""Registry entries identify verified artifacts, never placeholder model names."""
import json
from pathlib import Path
from .artifacts import artifact_root, load_bundle
from pipeline.source_to_staging.common import sha256

def entries(data_version, kind=None, root=None):
    root = Path(root or artifact_root())
    registry = json.loads((root / 'registry.json').read_text(encoding='utf-8'))
    result = []
    for entry in registry['models']:
        if kind and entry['kind'] != kind:
            continue
        folder = root / entry['folder']
        if sha256(folder / 'metadata.json') != entry['metadata_sha256']:
            raise ValueError('Registry metadata checksum mismatch')
        result.append(load_bundle(folder, data_version))
    return result

def resolve(model_id, data_version, kind, root=None):
    candidates = entries(data_version, kind, root)
    if model_id is None:
        model_id = next((m['model_id'] for m, _ in candidates if m.get('default')), None)
    for metadata, state in candidates:
        if metadata['model_id'] == model_id:
            return metadata, state
    raise ValueError('Unsupported or unavailable ' + kind + ' model')
