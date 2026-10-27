"""Run DW preflight, migration, load, quality and rerun with one command."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def verify_reports(output: Path) -> dict:
    """Require successful checks and one unchanged published version across steps."""
    preflight = json.loads((output / "inputs/preflight.json").read_text(encoding="utf-8"))
    loaded = json.loads((output / "first_load.json").read_text(encoding="utf-8"))
    quality = json.loads((output / "quality_report.json").read_text(encoding="utf-8"))
    rerun = json.loads((output / "rerun.json").read_text(encoding="utf-8"))
    if preflight.get("passed") is not True or quality.get("passed") is not True or quality.get("errors"):
        raise ValueError("Preflight or independent quality checks did not pass")
    if loaded.get("status") not in ("published", "no-op") or rerun.get("status") != "no-op":
        raise ValueError("Load must publish or reuse DW; rerun must be no-op")
    for key in ("run_id", "data_version"):
        if not loaded.get(key) or any(report.get(key) != loaded[key] for report in (quality, rerun)):
            raise ValueError("DW version changed between load, quality and rerun; inspect the reports")
    quality_dw = quality.get("dw_quality",quality)
    if any(report.get("counts") != loaded.get("counts") for report in (quality_dw, rerun)):
        raise ValueError("DW counts differ between load, quality and rerun")
    mart = {}
    if "dw_quality" in quality:
        first_mart,last_mart = loaded.get("mart",{}),rerun.get("mart",{})
        if any(report.get("passed") is not True for report in (first_mart,last_mart)):
            raise ValueError("Operations Mart checks did not pass on load and rerun")
        for key in ("run_id","data_version","build_fingerprint","counts"):
            if any(report.get(key) != quality.get(key) for report in (first_mart,last_mart)):
                raise ValueError("Mart version/counts changed between load, quality and rerun")
        mart = {"mart_verified":True,"mart_counts":quality["counts"],"mart_build_fingerprint":quality["build_fingerprint"]}
    return {"run_id": loaded["run_id"], "data_version": loaded["data_version"],
            "load_status": loaded["status"], "verified": True, **mart}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "pipeline/config/dw_operations.json")
    parser.add_argument("--dbname", help="Override POSTGRES_DB for DW commands")
    parser.add_argument("--output-dir", type=Path, help="New evidence directory; existing directories are refused")
    parser.add_argument("--with-tests", action="store_true", help="Run the pipeline test suite after DW checks")
    parser.add_argument("--with-mart", action="store_true", help="Install and verify Operations Mart together with DW")
    args = parser.parse_args(argv)
    output = (args.output_dir or ROOT / "artifacts/dw/operations" / ("run_" + uuid4().hex)).resolve()
    config = args.config.resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError:
        print("Cannot create evidence directory; choose a new writable --output-dir", file=sys.stderr)
        return 1

    selected = ["--config", str(config)]
    database = ["--dbname", args.dbname] if args.dbname else []
    steps = [
        ("preflight", ["scripts/check_dw_inputs.py", *selected, *database,
                       "--output-dir", str(output / "inputs")], "inputs/preflight.json"),
        ("migration", ["scripts/setup_db.py", "--schema", "dw", *database,
                       "--report", str(output / "migration.json")], "migration.json"),
        ("load", ["scripts/run_pipeline.py", "--to", "dw", *selected, *database,
                  "--report", str(output / "first_load.json")], "first_load.json"),
        ("quality", ["pipeline/quality/mart_checks.py" if args.with_mart else "pipeline/quality/dw_checks.py", *selected, *database,
                     "--report", str(output / "quality_report.json")], "quality_report.json"),
        ("rerun", ["scripts/run_pipeline.py", "--to", "dw", *selected, *database,
                   "--report", str(output / "rerun.json")], "rerun.json"),
    ]
    if args.with_mart:
        steps.insert(2,("mart_migration",["scripts/setup_db.py","--schema","mart",*database,
                                        "--report",str(output/"mart_migration.json")],"mart_migration.json"))
    if args.with_tests:
        test_temp = ROOT / "artifacts/tests" / ("dw_" + uuid4().hex)
        steps.append(("tests", ["-m", "pytest", "-q", "tests/pipeline", "--basetemp", str(test_temp),
                                "--tb=short", "--junitxml", str(output / "pytest.xml")], "pytest.xml"))
    summary = {"status": "running", "output_dir": str(output), "steps": [], "tests_run": False}
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    exit_code = 0
    step = "preflight"
    print(f"DW reports: {output}", flush=True)
    try:
        for index, (step, command, report_file) in enumerate(steps, start=1):
            print(f"[{index}/{len(steps)}] {step}", flush=True)
            record = {"name": step, "report": report_file, "exit_code": None}
            summary["steps"].append(record)
            if step == "tests":
                summary["tests_run"] = True
            child = subprocess.run([sys.executable, *command], cwd=ROOT, env=environment,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
            record["exit_code"] = child.returncode
            if step == "tests" and child.stdout:
                print(child.stdout, end="", flush=True)
            if child.returncode != 0:
                summary.update(status="failed", failed_step=step,
                               error=f"Command failed with exit code {child.returncode}; inspect {report_file}")
                if step != "tests" and child.stdout:
                    print(child.stdout, end="", file=sys.stderr)
                exit_code = 1
                break
            if step == "rerun":
                step = "verification"
                summary.update(verify_reports(output))
        else:
            summary["status"] = "completed"
    except KeyboardInterrupt:
        summary.update(status="interrupted", failed_step=step, error="Execution interrupted; inspect completed reports")
        exit_code = 130
    except (OSError, ValueError, KeyError):
        summary.update(status="failed", failed_step=step,
                       error="Command could not complete or reports were inconsistent; inspect the step reports")
        exit_code = 1
    try:
        with (output / "summary.json").open("x", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except OSError:
        print("Could not save summary.json; existing step reports and DB publications are retained", file=sys.stderr)
        exit_code = 1
    print(json.dumps(summary, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
