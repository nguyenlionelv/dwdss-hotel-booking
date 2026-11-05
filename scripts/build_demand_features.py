"""Extract an official snapshot and export versioned demand features, without DB writes."""
import argparse
from pathlib import Path
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ml.demand_forecast.contracts import DemandError,FEATURE_VERSION
from ml.demand_forecast.data import extract_snapshot,save_snapshot,write_json
from ml.demand_forecast.workflow import export_features

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dw-config",type=Path)
    parser.add_argument("--dbname")
    parser.add_argument("--output-dir",type=Path)
    args=parser.parse_args(argv)
    output=args.output_dir or ROOT/"artifacts/metrics"/f"features_{uuid.uuid4().hex}"
    if output.exists(): parser.error("Choose a new output directory")
    output.mkdir(parents=True)
    try:
        snapshot=extract_snapshot(args.dw_config,args.dbname)
        save_snapshot(snapshot,output/"snapshot.json")
        table=export_features(snapshot,output/"demand_features.csv")
        write_json(output/"summary.json",{"status":"completed","feature_version":FEATURE_VERSION,
                   "data_version":snapshot.data_version,"snapshot_hash":snapshot.snapshot_hash,
                   "rows":len(table),"train_ready_rows":int(table.train_ready.sum())})
        print(output)
        return 0
    except (DemandError,ValueError,OSError,KeyError) as exc:
        write_json(output/"failure.json",{"status":"blocked","error_code":getattr(exc,"code","INVALID_INPUT"),
                                         "message":str(exc),"quality":getattr(exc,"quality",None)})
        print(f"Feature build blocked: {getattr(exc,'code','INVALID_INPUT')}; evidence: {output}")
        return 1

if __name__=="__main__":
    raise SystemExit(main())
