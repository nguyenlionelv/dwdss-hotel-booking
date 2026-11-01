"""The one-command runner stops on failure and preserves the published version."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import run_dw, run_pipeline
from pipeline.staging_to_dw import workflow


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

    monkeypatch.setattr(workflow.subprocess, "run", execute)
    return calls


@pytest.mark.parametrize("step", [[], ["--step", "all"]])
def test_run_all_steps_and_forward_config_database_and_python(tmp_path, monkeypatch, step):
    output = tmp_path / "reports with spaces"
    config = tmp_path / "config with spaces.json"
    calls = fake_commands(monkeypatch, output)
    assert run_pipeline.main(["--to", "dw", *step, "--output-dir", str(output), "--config", str(config), "--dbname", "fixture_db"]) == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "completed" and summary["verified"] is True
    assert summary["run_id"] == "same-run" and summary["tests_run"] is False
    assert [s["name"] for s in summary["steps"]] == ["preflight", "migration", "load", "quality", "rerun"]
    for command, options in calls:
        assert command[0] == sys.executable and options["cwd"] == workflow.ROOT
        assert command[command.index("--dbname") + 1] == "fixture_db"
        if "scripts/run_pipeline.py" in command:
            assert command[command.index("--step") + 1] == "load"
        if "--config" in command:
            assert command[command.index("--config") + 1] == str(config.resolve())


@pytest.mark.parametrize("failure", ["preflight", "migration", "load", "quality", "rerun"])
def test_stop_at_first_failed_command(tmp_path, monkeypatch, failure):
    output = tmp_path / "reports"
    calls = fake_commands(monkeypatch, output, failure=failure)
    assert run_pipeline.main(["--to", "dw", "--output-dir", str(output), "--with-tests"]) == 1
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
    assert run_pipeline.main(["--to", "dw", "--output-dir", str(output)]) == 1
    assert calls == [] and evidence.read_text(encoding="utf-8") == "existing evidence"


def test_changed_version_is_failure_and_tests_do_not_start(tmp_path, monkeypatch):
    output = tmp_path / "reports"
    calls = fake_commands(monkeypatch, output, changed_version=True)
    assert run_pipeline.main(["--to", "dw", "--output-dir", str(output), "--with-tests"]) == 1
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["failed_step"] == "verification" and summary["status"] == "failed"
    assert len(calls) == 5 and summary["tests_run"] is False


@pytest.mark.parametrize("failed", [False, True])
def test_optional_tests_use_isolated_temp_and_propagate_failure(tmp_path, monkeypatch, failed):
    output = tmp_path / "reports"
    calls = fake_commands(monkeypatch, output, failure="tests" if failed else None)
    monkeypatch.setattr(workflow, "ROOT", tmp_path)
    assert run_pipeline.main(["--to", "dw", "--output-dir", str(output), "--with-tests"]) == int(failed)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["tests_run"] is True and summary["verified"] is True
    command = calls[-1][0]
    assert command[1:4] == ["-m", "pytest", "-q"] and "--tb=short" in command
    assert command[4:7] == ["tests/pipeline", "tests/warehouse", "tests/marts"]
    temporary = Path(command[command.index("--basetemp") + 1])
    assert temporary.parent == workflow.ROOT / "artifacts/tests" and not temporary.exists()
    assert temporary.parent.is_dir()
    assert command[command.index("--junitxml") + 1] == str(output / "pytest.xml")


@pytest.mark.parametrize("entrypoint", [["scripts/run_pipeline.py", "--to", "dw"], ["scripts/run_dw.py"]])
def test_real_cli_invalid_config_stops_before_database_commands(tmp_path, entrypoint):
    config = json.loads((workflow.ROOT / "pipeline/config/dw_operations.json").read_text(encoding="utf-8"))
    config["mappings"]["country"]["sha256"] = "0" * 64
    config_file = tmp_path / "invalid.json"
    config_file.write_text(json.dumps(config), encoding="utf-8")
    output = tmp_path / "reports"
    child = subprocess.run([sys.executable, *entrypoint, "--config", str(config_file),
                            "--output-dir", str(output)], capture_output=True, text=True, cwd=workflow.ROOT)
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

    monkeypatch.setattr(workflow.subprocess, "run", fail)
    output = tmp_path / "reports"
    assert run_pipeline.main(["--to", "dw", "--output-dir", str(output)]) == expected_exit
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == expected_status and summary["failed_step"] == "preflight"


@pytest.mark.parametrize("changed",[None,"counts","build_fingerprint","data_version"])
def test_verify_mart_reports_rejects_inconsistent_snapshot(tmp_path,changed):
    dw = {"run_id":"run","data_version":"version","counts":{"fact_booking":6}}
    mart = {"run_id":"run","data_version":"version","counts":{"daily_hotel_operations":3},
            "build_fingerprint":"fingerprint","passed":True}
    reports = {"inputs/preflight.json":{"passed":True},
               "first_load.json":{**dw,"status":"published","mart":mart},
               "quality_report.json":{**mart,"dw_quality":dw,"errors":[]},
               "rerun.json":{**dw,"status":"no-op","mart":dict(mart)}}
    if changed:
        reports["rerun.json"]["mart"][changed] = "changed"
    for name,value in reports.items():
        path = tmp_path/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value),encoding="utf-8")
    if changed:
        with pytest.raises(ValueError,match="Mart version/counts"):
            workflow.verify_reports(tmp_path)
    else:
        assert workflow.verify_reports(tmp_path)["mart_verified"] is True


@pytest.mark.parametrize("arguments", [
    ["--with-mart"], ["--with-tests"], ["--output-dir", "unused"],
    ["--step", "load"], ["--step", "all"], ["--config", "unused.json"],
    ["--to", "dw", "--manifest", "unused.json"],
    ["--to", "dw", "--report", "unused.json"],
    ["--to", "dw", "--step", "load", "--with-mart"],
    ["--to", "dw", "--step", "load", "--with-tests"],
    ["--to", "dw", "--step", "load", "--output-dir", "unused"],
])
def test_invalid_options_fail_before_running_any_step(monkeypatch, arguments):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid arguments must not start a database operation or workflow")

    for name in ("run_staging", "load_dw", "run_dw_workflow"):
        monkeypatch.setattr(run_pipeline, name, unexpected)
    with pytest.raises(SystemExit) as error:
        run_pipeline.main(arguments)
    assert error.value.code == 2


@pytest.mark.parametrize("target,step", [("staging", []), ("dw", ["--step", "load"])])
def test_single_load_preserves_report_and_forwards_inputs(tmp_path, monkeypatch, target, step):
    source = tmp_path / "input.json"
    output = tmp_path / "result.json"
    calls = []

    def load(path, *, dbname):
        calls.append((path, dbname))
        return {"status": "published"}

    name, option = ("run_staging", "--manifest") if target == "staging" else ("load_dw", "--config")
    monkeypatch.setattr(run_pipeline, name, load)
    arguments = ["--to", target, *step, option, str(source), "--dbname", "fixture_db", "--report", str(output)]
    assert run_pipeline.main(arguments) == 0
    assert calls == [(source, "fixture_db")]
    original = output.read_bytes()
    assert json.loads(original)["status"] == "published"
    with pytest.raises(SystemExit) as error:
        run_pipeline.main(arguments)
    assert error.value.code == 2
    assert output.read_bytes() == original and len(calls) == 1


def test_legacy_runner_forwards_to_pipeline(monkeypatch):
    calls = []

    def execute(arguments):
        calls.append(arguments)
        return 7

    monkeypatch.setattr(run_dw, "pipeline_main", execute)
    assert run_dw.main(["--with-mart", "--with-tests"]) == 7
    assert calls == [["--to", "dw", "--with-mart", "--with-tests"]]


def test_mart_workflow_installs_before_load_and_selects_mart_quality(tmp_path, monkeypatch):
    calls = []

    def execute(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 1 if "pipeline/quality/mart_checks.py" in command else 0,
                                           stdout="", stderr="")

    monkeypatch.setattr(workflow.subprocess, "run", execute)
    output = tmp_path / "mart"
    assert run_pipeline.main(["--to", "dw", "--with-mart", "--output-dir", str(output)]) == 1
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert [step["name"] for step in summary["steps"]] == ["preflight", "migration", "mart_migration", "load", "quality"]
    assert calls[2][calls[2].index("--schema") + 1] == "mart"
    assert "pipeline/quality/mart_checks.py" in calls[-1]
    assert summary["failed_step"] == "quality"
