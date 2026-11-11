"""Offline training CLI for the verified notebook protocols."""
import argparse
from pathlib import Path
from .artifacts import artifact_root
from .data import export_snapshot
from .training import train
from pipeline.source_to_staging.common import ROOT

def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', type=Path, default=ROOT / 'artifacts/ml_serving/snapshot')
    p.add_argument('--output', type=Path, default=artifact_root())
    p.add_argument('--export', action='store_true')
    p.add_argument('--dbname')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--tree-jobs', type=int, choices=range(1, 13), default=1)
    args = p.parse_args()
    import os
    os.environ['DWDSS_TREE_JOBS'] = str(args.tree_jobs)
    if args.export:
        export_snapshot(args.snapshot, args.dbname)
    train(args.snapshot, args.output, args.resume)

if __name__ == '__main__':
    main()
