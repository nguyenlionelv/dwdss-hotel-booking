"""Run exported demand inference without retraining or DSS classification."""
import argparse
from datetime import timedelta
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ml.demand_forecast.artifacts import load_bundle
from ml.demand_forecast.contracts import DemandError,local_date
from ml.demand_forecast.data import load_snapshot,extract_snapshot,write_json
from ml.demand_forecast.predict import forecast_demand

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of-date",required=True)
    parser.add_argument("--bundle",type=Path,required=True)
    parser.add_argument("--snapshot",type=Path)
    parser.add_argument("--dw-config",type=Path)
    parser.add_argument("--dbname")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    if args.output and args.output.exists():
        parser.error("Output file exists; choose a new file")
    try:
        bundle=load_bundle(args.bundle)
        snapshot=load_snapshot(args.snapshot) if args.snapshot else extract_snapshot(args.dw_config,args.dbname)
        if snapshot.source_kind!="postgresql":
            raise DemandError("FIXTURE_NOT_OFFICIAL","CLI inference requires an official snapshot")
        cutoff=local_date(args.as_of_date)
        calendar=[r for r in snapshot.calendar if cutoff<r.full_date<=cutoff+timedelta(days=7)]
        result=forecast_demand(bundle,snapshot,calendar,cutoff)
        payload=result.to_dict()
        if args.output:
            write_json(args.output,payload)
        print(json.dumps(payload,allow_nan=False))
        return 0 if result.status=="ok" else 1
    except (DemandError,ValueError,OSError,KeyError) as exc:
        print(json.dumps({"status":"unavailable","reason_code":getattr(exc,"code","INVALID_INPUT"),"message":str(exc)}))
        return 1

if __name__=="__main__":
    raise SystemExit(main())
