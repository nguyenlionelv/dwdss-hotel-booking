"""The one-command runner stops on failure and preserves the published version."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import run_dw


def fake_commands(monkeypatch, output, *, failure=None, changed_version=False):
    calls = []

    def execute(command, **kwargs):
        calls.append((command, kwargs))
        step = ("preflight", "migration", "load", "quality", "rerun", "tests")[len(calls) - 1]
        counts = {"fact_booking": 6}
        version = {"run_id": "same-run", "data_version": "same-version", "counts": counts}
        reports = {
            "preflight": ("inputs/preflight.json", {"passed": True}),
            "migration": ("migration.json", {"schema": "dw", "status": "no-op"}),
            "load": ("first_load.json", {"status": "published", **version}),
            "quality": ("quality_report.json", {"passed": True, "errors": [], **version}),
            "rerun": ("rerun.json", {"status": "no-op", **version}),
        }
        if step in reports:
            file, data = reports[step]
            if changed_version and step == "quality":
                data["data_version"] = "another-version"
            target = output / file
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(data), encoding="utf-8")
        return subprocess.CompletedProcess(command, 1 if failure == step else 0, stdout="", stderr="")

    monkeypatch.setattr(run_dw.subprocess, "run", execute)
    return calls


def test_run_all_steps_and_forward_config_database_and_python(tmp_path, monkeypatch):
    output = tmp_path / "reports with spaces"
    config = tmp_path / "config with spaces.json"
    calls = fake_commands(monkeypatch, output)
    assert run_dw.main(["--output-dir", str(output), "--config", str(config), "--dbname", "fixture_db"]) == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "completed" and summary["verified"] is True
    assert summary["run_id"] == "same-run" and summary["tests_run"] is False
    assert [s["name"] for s in summary["steps"]] == ["preflight", "migration", "load", "quality", "rerun"]
    for command, options in calls:
        assert command[0] == sys.executable and options["cwd"] == run_dw.ROOT
        assert command[command.index("--dbname") + 1] == "fixture_db"
        if "--config" in command:
            assert command[command.index("--config") + 1] == str(config.resolve())


@pytest.mark.parametrize("failure", ["preflight", "migration", "load", "quality", "rerun"])
def test_stop_at_first_failed_command(tmp_path, monkeypatch, failure):
    output = tmp_path / "reports"
    calls = fake_commands(monkeypatch, output, failure=failure)
    assert run_dw.main(["--output-dir", str(output), "--with-tests"]) == 1
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "failed" and summary["failed_step"] == failure
    assert summary["steps"][-1]["exit_code"] == 1 and summary["tests_run"] is False
    assert len(calls) == ["preflight", "migration", "load", "quality", "rerun"].index(failure) + 1


def test_existing_output_is_never_overwritten(tmp_path, monkeypatch):
    output = tmp_path / "reports"
    output.mkdir()
    evidence = output / "summary.json"
    evidence.write_text("existing evidence", encoding="utf-8")
    calls = fake_commands(monkeypatch, output)
    assert run_dw.main(["--output-dir", str(output)]) == 1
    assert calls == [] and evidence.read_text(encoding="utf-8") == "existing evidence"


def test_changed_version_is_failure_and_tests_do_not_start(tmp_path, monkeypatch):
    output = tmp_path / "reports"
    calls = fake_commands(monkeypatch, output, changed_version=True)
    assert run_dw.main(["--output-dir", str(output), "--with-tests"]) == 1
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["failed_step"] == "verification" and summary["status"] == "failed"
    assert len(calls) == 5 and summary["tests_run"] is False


@pytest.mark.parametrize("failed", [False, True])
def test_optional_tests_use_isolated_temp_and_propagate_failure(tmp_path, monkeypatch, failed):
    output = tmp_path / "reports"
    calls = fake_commands(monkeypatch, output, failure="tests" if failed else None)
    assert run_dw.main(["--output-dir", str(output), "--with-tests"]) == int(failed)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["tests_run"] is True and summary["verified"] is True
    command = calls[-1][0]
    assert command[1:4] == ["-m", "pytest", "-q"] and "--tb=short" in command
    temporary = Path(command[command.index("--basetemp") + 1])
    assert temporary.parent == run_dw.ROOT / "artifacts/tests" and not temporary.exists()
    assert command[command.index("--junitxml") + 1] == str(output / "pytest.xml")


def test_real_cli_invalid_config_stops_before_database_commands(tmp_path):
    config = json.loads((run_dw.ROOT / "pipeline/config/dw_operations.json").read_text(encoding="utf-8"))
    config["mappings"]["country"]["sha256"] = "0" * 64
    config_file = tmp_path / "invalid.json"
    config_file.write_text(json.dumps(config), encoding="utf-8")
    output = tmp_path / "reports"
    child = subprocess.run([sys.executable, str(run_dw.ROOT / "scripts/run_dw.py"), "--config", str(config_file),
                            "--output-dir", str(output)], capture_output=True, text=True, cwd=run_dw.ROOT)
    assert child.returncode == 1
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["failed_step"] == "preflight" and len(summary["steps"]) == 1
    assert not (output / "migration.json").exists()


@pytest.mark.parametrize("error,expected_status,expected_exit", [
    (OSError("launch failed"), "failed", 1), (KeyboardInterrupt(), "interrupted", 130),
])
def test_launch_failure_or_interruption_is_recorded(tmp_path, monkeypatch, error, expected_status, expected_exit):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(run_dw.subprocess, "run", fail)
    output = tmp_path / "reports"
    assert run_dw.main(["--output-dir", str(output)]) == expected_exit
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == expected_status and summary["failed_step"] == "preflight"
