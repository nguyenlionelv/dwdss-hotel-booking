"""Run the complete selected Raw -> Staging -> DW -> Operations Mart workflow."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from pipeline.source_to_staging.common import ROOT, StructuralError, verify_sources
from pipeline.staging_to_dw.config import DEFAULT_CONFIG, load_config, resolve_path


def verify_reports(output: Path, fingerprint: str) -> dict:
    """Require the same Staging snapshot throughout the completed DW/Mart workflow."""
    staged = json.loads((output / "staging_load.json").read_text(encoding="utf-8"))
    quality = json.loads((output / "staging_quality.json").read_text(encoding="utf-8"))
    rerun = json.loads((output / "staging_rerun.json").read_text(encoding="utf-8"))
    dw = json.loads((output / "dw/summary.json").read_text(encoding="utf-8"))
    loaded = json.loads((output / "dw/first_load.json").read_text(encoding="utf-8"))

    if staged.get("status") not in ("published", "no-op") or rerun.get("status") != "no-op":
        raise ValueError("Staging must publish or reuse a snapshot; rerun must be no-op")
    if quality.get("passed") is not True or quality.get("errors"):
        raise ValueError("Staging quality did not pass")
    batch = staged["batch_id"]
    if any(report.get("batch_id") != batch or report.get("source_set_fingerprint") != fingerprint
           for report in (staged, quality, rerun)):
        raise ValueError("Staging snapshot changed between load, quality and rerun")
    if (dw.get("status") != "completed" or dw.get("verified") is not True
            or dw.get("mart_verified") is not True):
        raise ValueError("DW/Mart workflow did not complete verification")
    if loaded.get("staging_batch_id") != batch:
        raise ValueError("DW was built from a different Staging snapshot")
    return {"verified": True, "mart_verified": True, "staging_batch_id": batch,
            "source_set_fingerprint": fingerprint, "run_id": dw["run_id"],
            "data_version": dw["data_version"], "mart_counts": dw["mart_counts"]}


def run(config_path: Path = DEFAULT_CONFIG, *, dbname: str | None = None,
        output_dir: Path | None = None) -> int:
    """Reuse existing CLIs, stop on failure, and retain a new evidence directory."""
    output = (output_dir or ROOT / "artifacts/etl" / ("run_" + uuid4().hex)).resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError:
        print("Cannot create evidence directory; choose a new writable --output-dir", file=sys.stderr)
        return 1

    summary = {"status": "running", "output_dir": str(output), "steps": [], "verified": False}
    step = "inputs"
    exit_code = 0
    print(f"ETL reports: {output}", flush=True)
    try:
        config = config_path.resolve()
        bundle = load_config(config)
        verify_sources(bundle["sources"])
        manifest = resolve_path(bundle["config"]["source_manifest"])
        inputs = {"config_sha256": bundle["config_sha256"], "manifest": str(manifest),
                  "source_set_fingerprint": bundle["source_set_fingerprint"],
                  "sources": {sid: {"file": spec["file"], "sha256": spec["sha256"]}
                              for sid, spec in bundle["sources"].items()}}
        (output / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")

        database = ["--dbname", dbname] if dbname else []
        steps = [
            ("staging_migration", ["scripts/setup_db.py", "--schema", "staging", *database,
                                   "--report", str(output / "staging_migration.json")]),
            ("staging_load", ["scripts/run_pipeline.py", "--to", "staging", "--manifest", str(manifest),
                              *database, "--report", str(output / "staging_load.json")]),
            ("staging_quality", ["pipeline/quality/staging_checks.py", *database,
                                 "--report", str(output / "staging_quality.json")]),
            ("staging_rerun", ["scripts/run_pipeline.py", "--to", "staging", "--manifest", str(manifest),
                               *database, "--report", str(output / "staging_rerun.json")]),
            ("dw_mart", ["scripts/run_pipeline.py", "--to", "dw", "--with-mart", "--config", str(config),
                         *database, "--output-dir", str(output / "dw")]),
        ]
        environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        for index, (step, command) in enumerate(steps, start=1):
            print(f"[{index}/{len(steps)}] {step}", flush=True)
            report = "dw/summary.json" if step == "dw_mart" else step + ".json"
            record = {"name": step, "report": report, "exit_code": None}
            summary["steps"].append(record)
            child = subprocess.run([sys.executable, *command], cwd=ROOT, env=environment,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
            record["exit_code"] = child.returncode
            if child.returncode != 0:
                summary.update(status="failed", failed_step=step,
                               error=f"Command failed with exit code {child.returncode}; inspect {report} and configuration")
                exit_code = 1
                break
        else:
            step = "verification"
            summary.update(verify_reports(output, bundle["source_set_fingerprint"]), status="completed")
    except KeyboardInterrupt:
        summary.update(status="interrupted", failed_step=step, error="Execution interrupted; inspect completed reports")
        exit_code = 130
    except (OSError, ValueError, KeyError, csv.Error, StructuralError) as exc:
        summary.update(status="failed", failed_step=step, error=str(exc))
        exit_code = 1

    try:
        with (output / "summary.json").open("x", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except OSError:
        print("Could not save summary.json; completed reports and DB publications are retained", file=sys.stderr)
        exit_code = 1
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return exit_code
