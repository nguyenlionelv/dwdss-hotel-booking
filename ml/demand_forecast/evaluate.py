"""Inspect saved validation and holdout metrics, retaining their protocol units."""
import argparse
import pandas as pd
from .artifacts import artifact_root
from .evaluation import folds, clean, selected_metrics, HOLDOUT

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifacts',type=Path,default=artifact_root())
    args=p.parse_args()
    for name in ('imputed','causal','monthly'):
        for partition in ('validation','holdout'):
            path=args.artifacts/(name+'_'+partition+'_metrics.csv')
            print(name,partition,'guests/month' if name=='monthly' else 'guests/daily prediction')
            print(pd.read_csv(path).to_string(index=False))

from pathlib import Path
if __name__ == '__main__': main()
