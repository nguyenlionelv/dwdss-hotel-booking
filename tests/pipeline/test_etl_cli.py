"""Basic checks for the complete ETL runner: success and stopping on failure."""

import json
from pathlib import Path
import subprocess
import sys

from pipeline import workflow
from scripts import run_etl


def mock_commands(monkeypatch, output, *, fail_load=False):
    bundle = {"config": {"source_manifest": "manifest.json"}, "config_sha256": "config-hash",
              "source_set_fingerprint": "fingerprint", "sources": {}}
    monkeypatch.setattr(workflow, "load_config", lambda path: bundle)
    monkeypatch.setattr(workflow, "verify_sources", lambda sources: None)
    calls = []

    def execute(command, **kwargs):
        calls.append(command)
        assert command[0] == sys.executable
        assert command[command.index("--dbname") + 1] == "etl_test_db"
        if fail_load and "staging_load.json" in command[-1]:
            return subprocess.CompletedProcess(command, 1)
        snapshot = {"batch_id": "batch", "source_set_fingerprint": "fingerprint"}
        if "--report" in command:
            target = output / Path(command[-1]).name
            reports = {
                "staging_migration.json": {"status": "applied"},
                "staging_load.json": {"status": "published", **snapshot},
                "staging_quality.json": {"passed": True, "errors": [], **snapshot},
                "staging_rerun.json": {"status": "no-op", **snapshot},
            }
            target.write_text(json.dumps(reports[target.name]), encoding="utf-8")
        else:
            assert "--with-mart" in command
            target = output / "dw"
            target.mkdir()
            summary = {"status": "completed", "verified": True, "mart_verified": True,
                       "run_id": "run", "data_version": "version", "mart_counts": {"daily_hotel_operations": 3}}
            (target / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
            (target / "first_load.json").write_text(json.dumps({"staging_batch_id": "batch"}), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(workflow.subprocess, "run", execute)
    return calls


def test_full_etl_runs_staging_then_dw_and_mart(tmp_path, monkeypatch):
    output = tmp_path / "reports"
    calls = mock_commands(monkeypatch, output)
    assert run_etl.main(["--dbname", "etl_test_db", "--output-dir", str(output)]) == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "completed" and summary["mart_verified"] is True
    assert summary["staging_batch_id"] == "batch" and summary["data_version"] == "version"
    assert [s["name"] for s in summary["steps"]] == [
        "staging_migration", "staging_load", "staging_quality", "staging_rerun", "dw_mart"]
    assert len(calls) == 5


def test_failed_staging_load_stops_before_dw(tmp_path, monkeypatch):
    output = tmp_path / "reports"
    calls = mock_commands(monkeypatch, output, fail_load=True)
    assert run_etl.main(["--dbname", "etl_test_db", "--output-dir", str(output)]) == 1
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "failed" and summary["failed_step"] == "staging_load"
    assert summary["verified"] is False and len(calls) == 2
    assert not (output / "dw").exists()
