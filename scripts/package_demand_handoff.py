"""Build a small serving handoff, or opt into the complete research evidence."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / "artifacts/metrics/demand_feature_versions_20261105"
DEFAULT_EVIDENCE = ROOT / "artifacts/metrics/demand_dss_20261105"
SERVING_MODULES = ("artifacts.py", "baseline.py", "contracts.py", "data.py", "dss.py",
                   "features.py", "predict.py", "service.py", "dss_fixtures.py")


def verify_package(path: str | Path) -> dict:
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or "handoff_manifest.json" not in names:
            raise ValueError("Missing manifest or duplicate archive paths")
        for entry in archive.infolist():
            name = entry.orig_filename  # ZipInfo normalizes Windows separators in .filename.
            if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name or ":" in name:
                raise ValueError("Unsafe archive path")
        manifest = json.loads(archive.read("handoff_manifest.json"))
        if manifest.get("format") != "demand-phase4-handoff-v1":
            raise ValueError("Unsupported handoff format")
        expected = manifest["files_sha256"]
        if set(names) != set(expected) | {"handoff_manifest.json"}:
            raise ValueError("Archive inventory differs from manifest")
        for name, checksum in expected.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != checksum:
                raise ValueError(f"Checksum mismatch: {name}")
        return {"passed": True, "files_verified": len(expected), "selected_model": manifest["selected_model"]}


def build_package(run_dir: str | Path, evidence_dir: str | Path, destination: str | Path,
                  *, profile: str = "serving") -> dict:
    run, evidence, destination = Path(run_dir).resolve(), Path(evidence_dir).resolve(), Path(destination)
    if destination.exists():
        raise FileExistsError("Choose a new handoff archive path")
    if profile not in {"serving", "research"}:
        raise ValueError("Choose serving or research profile")
    required = ["snapshot.json", "bundles/selected/manifest.json"]
    if profile == "research":
        required.extend(["metrics.json", "frozen_plan.json", "report.md"])
    for name in required:
        if not (run / name).is_file():
            raise ValueError(f"Incomplete accepted run: {name}")
    verification = evidence / "release_verification.json"
    if not verification.is_file():
        verification = evidence / "verification.json"
    if not verification.is_file():
        raise ValueError("DSS verification evidence is required")
    selected = json.loads((run / "bundles/selected/manifest.json").read_text(encoding="utf-8"))["manifest"]
    if profile == "serving" and (selected["model_name"] != "seasonal_naive" or selected.get("files_sha256", {})):
        raise ValueError("The serving profile is for the accepted Seasonal Naive model; use research for learned bundles")
    files = {}

    def add(path, name):
        if path.is_symlink():
            raise ValueError("Symlinks are not allowed in a handoff package")
        if name in files:
            raise ValueError(f"Duplicate package path: {name}")
        files[name] = path.read_bytes()

    add(run / "bundles/selected/manifest.json", "runtime/model/manifest.json")
    add(run / "snapshot.json", "runtime/snapshot.json")
    add(verification, "runtime/verification.json")
    for filename in SERVING_MODULES:
        relative = f"ml/demand_forecast/{filename}"
        add(ROOT / relative, relative)
    for relative in ["ml/requirements-serving.txt", "ml/.python-version", "scripts/forecast_dss.py",
                     "scripts/package_demand_handoff.py", "docs/ml/REPORT.md",
                     "docs/ml/demand_dss_response.schema.json", "docs/ml/examples/demand_dss_real.json",
                     "docs/ml/examples/demand_dss_synthetic.json"]:
        add(ROOT / relative, relative)
    guide = (ROOT / "docs/ml/README.md").read_text(encoding="utf-8")
    for target in ["REPORT.md", "demand_dss_response.schema.json", "examples/demand_dss_real.json", "examples/demand_dss_synthetic.json"]:
        guide = guide.replace(f"]({target})", f"](docs/ml/{target})")
    files["README.md"] = guide.encode("utf-8")
    files["docs/ml/REPORT.md"] = files["docs/ml/REPORT.md"].replace(b"](README.md)", b"](../../README.md)")
    if profile == "research":
        for folder in [run, evidence]:
            for path in sorted(folder.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    add(path, f"artifacts/metrics/{folder.name}/{path.relative_to(folder).as_posix()}")
        for folder in [ROOT / "ml/demand_forecast", ROOT / "tests/ml"]:
            for path in sorted(folder.rglob("*")):
                name = path.relative_to(ROOT).as_posix()
                if path.is_file() and path.suffix in {".py", ".json"} and "__pycache__" not in path.parts and name not in files:
                    add(path, name)
        for relative in ["ml/requirements.txt", "ml/requirements-dev.txt", "scripts/forecast_demand.py",
                         "scripts/verify_demand_dss.py", "scripts/compare_demand_features.py",
                         "scripts/verify_demand_metrics.py", "scripts/train_models.py", "scripts/build_demand_features.py"]:
            add(ROOT / relative, relative)
    manifest = {"format": "demand-phase4-handoff-v1", "profile": profile,
                "entrypoint": "README.md", "model_path": "runtime/model", "snapshot_path": "runtime/snapshot.json",
                "accepted_run": f"artifacts/metrics/{run.name}" if profile == "research" else None,
                "dss_evidence": f"artifacts/metrics/{evidence.name}" if profile == "research" else None,
                "selected_model": {key: selected[key] for key in ["model_name", "model_version", "feature_version", "data_version", "runtime"]},
                "files_sha256": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
                "scope": "Accepted serving inputs and runtime source; research profile additionally includes complete experiment evidence and tests.",
                "verification_note": "Checksums establish transfer integrity, not publisher authenticity. Load only trusted bundles."}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "x", compression=ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        archive.writestr("handoff_manifest.json", json.dumps(manifest, indent=2))
    return verify_package(destination)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--dss-evidence-dir", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--profile", choices=["serving", "research"], default="serving")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.verify:
        result = verify_package(args.verify)
    else:
        if args.output is None:
            parser.error("Provide --verify ZIP or --output ZIP")
        result = build_package(args.run_dir, args.dss_evidence_dir, args.output, profile=args.profile)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
