import json
from zipfile import ZipFile, ZipInfo

import pytest

from scripts.package_demand_handoff import build_package, verify_package


def fixture_run(tmp_path):
    run, evidence = tmp_path / "run", tmp_path / "evidence"
    (run / "bundles/selected").mkdir(parents=True)
    evidence.mkdir()
    for name in ["snapshot.json", "metrics.json", "frozen_plan.json", "report.md"]:
        (run / name).write_text("{}", encoding="utf-8")
    manifest = {"model_name": "seasonal_naive", "model_version": "fixture", "feature_version": "demand-weekly-v1",
                "data_version": "fixture", "runtime": {}, "files_sha256": {}}
    (run / "bundles/selected/manifest.json").write_text(json.dumps({"manifest": manifest}), encoding="utf-8")
    (evidence / "verification.json").write_text('{"passed":true}', encoding="utf-8")
    return run, evidence


def test_package_inventory_and_checksums(tmp_path):
    run, evidence = fixture_run(tmp_path)
    destination = tmp_path / "handoff.zip"
    result = build_package(run, evidence, destination)
    assert result["passed"] and result["files_verified"] > 6
    assert verify_package(destination) == result
    with ZipFile(destination) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    assert "runtime/model/manifest.json" in contents and "runtime/snapshot.json" in contents
    assert "ml/requirements-serving.txt" in contents
    assert "ml/demand_forecast/train.py" not in contents
    assert not any(name.startswith(("tests/", "artifacts/metrics/")) for name in contents)
    assert {name for name in contents if name.endswith(".md")} == {"README.md", "docs/ml/REPORT.md"}
    contents["runtime/snapshot.json"] = b"corrupted"
    corrupted = tmp_path / "corrupt.zip"
    with ZipFile(corrupted, "w") as archive:
        for name, content in contents.items(): archive.writestr(name, content)
    with pytest.raises(ValueError, match="Checksum mismatch"):
        verify_package(corrupted)
    with pytest.raises(FileExistsError):
        build_package(run, evidence, destination)


def test_research_evidence_is_explicitly_opt_in(tmp_path):
    run, evidence = fixture_run(tmp_path)
    destination = tmp_path / "research.zip"
    result = build_package(run, evidence, destination, profile="research")
    assert result["passed"]
    with ZipFile(destination) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read("handoff_manifest.json"))
    assert manifest["profile"] == "research"
    assert "artifacts/metrics/run/metrics.json" in names
    assert "ml/demand_forecast/train.py" in names
    assert "scripts/verify_demand_metrics.py" in names
    assert not any("local_archive" in name or name == "task.md" for name in names)


def test_serving_profile_rejects_a_learned_bundle(tmp_path):
    run, evidence = fixture_run(tmp_path)
    path = run / "bundles/selected/manifest.json"
    raw = json.loads(path.read_text())
    raw["manifest"]["model_name"] = "linear_regression"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="accepted Seasonal Naive"):
        build_package(run, evidence, tmp_path / "wrong-model.zip")


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/drive", "a\\b"])
def test_package_rejects_unsafe_paths(tmp_path, name):
    destination = tmp_path / "unsafe.zip"
    with ZipFile(destination, "w") as archive:
        archive.writestr("handoff_manifest.json", "{}")
        entry = ZipInfo("placeholder")
        entry.filename = name  # Bypass Windows ZipInfo separator normalization to test raw archive names.
        archive.writestr(entry, "data")
    with pytest.raises(ValueError, match="Unsafe archive path"):
        verify_package(destination)
