"""Quality-gated offline demand training. Guest-mix/cancellation/DSS are out of scope."""
import argparse
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ml.demand_forecast.contracts import DemandError
from ml.demand_forecast.data import extract_snapshot, load_snapshot, write_json
from ml.demand_forecast.train import DEFAULT_CONFIG, load_config
from ml.demand_forecast.workflow import run_experiment

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task",choices=["demand"],required=True)
    parser.add_argument("--config",type=Path,default=DEFAULT_CONFIG)
    parser.add_argument("--dw-config",type=Path)
    parser.add_argument("--dbname")
    parser.add_argument("--snapshot",type=Path,help="Previously exported quality-gated snapshot JSON, never a raw CSV")
    parser.add_argument("--output-dir",type=Path,default=None)
    args=parser.parse_args(argv)
    output=args.output_dir or ROOT/"artifacts/metrics"/f"demand_{uuid.uuid4().hex}"
    if output.exists():
        parser.error("Output directory already exists; choose a fresh directory")
    workflow_started=False
    try:
        config=load_config(args.config)
        snapshot=load_snapshot(args.snapshot) if args.snapshot else extract_snapshot(args.dw_config,args.dbname)
        if snapshot.source_kind != "postgresql":
            raise DemandError("FIXTURE_NOT_OFFICIAL", "Training CLI accepts official PostgreSQL snapshots only")
        workflow_started=True
        result=run_experiment(snapshot,config,output)
        print(f'{result["status"]}: {output}')
        return 0 if result["status"]=="completed" else 1
    except (DemandError,ValueError,OSError,KeyError) as exc:
        output.mkdir(parents=True,exist_ok=True)
        failure={"status":"failed" if workflow_started else "blocked",
                 "error_code":getattr(exc,"code","INVALID_INPUT"),
                 "message":str(exc),"training_workflow_started":workflow_started}
        if hasattr(exc,"quality"):
            failure["quality"]=exc.quality
        write_json(output/"failure.json",failure)
        print(f'{failure["error_code"]}: {failure["message"]}; evidence: {output}')
        return 1

if __name__=="__main__":
    raise SystemExit(main())
