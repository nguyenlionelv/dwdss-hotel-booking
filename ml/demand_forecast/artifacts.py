"""Immutable, checksummed bundles with explicit schema, source and runtime identity."""
from copy import deepcopy
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import subprocess
import joblib

from .contracts import (FEATURE_VERSION, DemandError, ModelBundle, feature_spec, local_date, utc_now)
from .data import digest, write_json

MODELS = ("seasonal_naive", "linear_regression", "random_forest", "xgboost")
DEPENDENCIES = ("numpy", "pandas", "scipy", "scikit-learn", "joblib", "xgboost", "psycopg", "tzdata")

def runtime_versions():
    result = {"python": platform.python_version()}
    for name in DEPENDENCIES:
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = None
    return result

def code_identity():
    root = Path(__file__).resolve().parents[2]
    files = [*Path(__file__).parent.glob("*.py"), root/"scripts/train_models.py",
             root/"scripts/forecast_demand.py", root/"scripts/compare_demand_features.py",
             Path(__file__).parent/"config.json", Path(__file__).parent/"comparison_config.json"]
    hashes = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in files if p.exists()}
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                                  text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unknown"
    return {"revision": revision, "files_sha256": hashes, "content_sha256": digest(hashes)}

def make_bundle(snapshot, name, cutoff, model_version, *, estimator=None, parameters=None, metadata=None,
                feature_version=FEATURE_VERSION):
    if name not in MODELS:
        raise DemandError("UNKNOWN_MODEL", f"Unsupported model: {name}")
    spec = feature_spec(feature_version)
    return ModelBundle({
        "bundle_format": "demand-bundle-v1", "model_name": name, "model_version": model_version,
        "feature_version": spec.version, "feature_schema": spec.schema,
        "training_cutoff": str(cutoff), "data_version": snapshot.data_version,
        "source_checksums": dict(snapshot.source_checksums), "snapshot_hash": snapshot.snapshot_hash,
        "source_kind": snapshot.source_kind, "extracted_at": snapshot.extracted_at,
        "created_at": utc_now(), "parameters": parameters or {}, "runtime": runtime_versions(),
        "code": code_identity(), "metadata": metadata or {},
    }, estimator)

def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save_bundle(bundle, path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    manifest = deepcopy(bundle.manifest)
    if manifest["model_name"] != "seasonal_naive":
        if bundle.estimator is None:
            raise DemandError("MISSING_MODEL", "Cannot export a missing estimator")
        joblib.dump(bundle.estimator, path/"estimator.joblib")
        manifest["files_sha256"] = {"estimator.joblib": file_hash(path/"estimator.joblib")}
    else:
        manifest["files_sha256"] = {}
    write_json(path/"manifest.json", {"manifest": manifest, "manifest_sha256": digest(manifest)})
    return path

def load_bundle(path):
    path = Path(path)
    if not (path/"manifest.json").is_file():
        raise DemandError("MISSING_MODEL", "Bundle manifest does not exist")
    try:
        envelope = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
        manifest = envelope["manifest"]
        if digest(manifest) != envelope["manifest_sha256"]:
            raise DemandError("CORRUPT_ARTIFACT", "Manifest checksum mismatch")
        spec = feature_spec(manifest["feature_version"])
        if (manifest["bundle_format"] != "demand-bundle-v1" or manifest["model_name"] not in MODELS
                or manifest["feature_schema"] != spec.schema):
            raise DemandError("INCOMPATIBLE_FEATURES", "Unsupported bundle format or feature schema")
        local_date(manifest["training_cutoff"])
        if not isinstance(manifest["model_version"], str) or not manifest["model_version"]:
            raise DemandError("CORRUPT_ARTIFACT", "Bundle requires a model version")
        if not manifest["data_version"] or set(manifest["source_checksums"]) != {"booking","holiday","weather"}:
            raise DemandError("INVALID_PROVENANCE", "Bundle lacks source/data identity")
        expected_files = {"estimator.joblib"} if manifest["model_name"] != "seasonal_naive" else set()
        if set(manifest["files_sha256"]) != expected_files:
            raise DemandError("CORRUPT_ARTIFACT", "Unexpected bundle file inventory")
        for name, checksum in manifest["files_sha256"].items():
            if not (path/name).is_file() or file_hash(path/name) != checksum:
                raise DemandError("CORRUPT_ARTIFACT", "Estimator checksum mismatch")
        if expected_files:
            current = runtime_versions()
            required = ("numpy","pandas","scipy","scikit-learn","joblib")
            if manifest["model_name"] == "xgboost":
                required += ("xgboost",)
            if current["python"].split(".")[:2] != manifest["runtime"]["python"].split(".")[:2] or any(
                    current[k] != manifest["runtime"][k] for k in required):
                raise DemandError("INCOMPATIBLE_RUNTIME", "Use the dependency versions recorded in the bundle")
        try:
            estimator = joblib.load(path/"estimator.joblib") if expected_files else None
        except Exception as exc:
            raise DemandError("CORRUPT_ARTIFACT", "Estimator could not be deserialized") from exc
        if estimator is not None and getattr(estimator, "n_features_in_", None) != len(spec.names):
            raise DemandError("INCOMPATIBLE_FEATURES", "Estimator input width differs from manifest")
        return ModelBundle(manifest, estimator)
    except DemandError:
        raise
    except (OSError, ValueError, TypeError, KeyError, EOFError) as exc:
        raise DemandError("CORRUPT_ARTIFACT", "Malformed or unreadable model bundle") from exc
