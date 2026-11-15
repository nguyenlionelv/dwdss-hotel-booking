"""Read-only DSS calibration. Never trains models or writes source/ML artifacts.

Historical actual exceedances are reference-tail proxies, not business false alerts.
All selection ends May 2017; the forecast holdout is evaluated only after locking policy.
"""
import argparse
import csv
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.services.decision_engine.historical_context import HistoricalContext, day

SNAPSHOT = ROOT / 'artifacts/ml_serving/snapshot/daily_input.csv'
POLICY = ROOT / 'backend/app/services/decision_engine/policy.json'
REPORT = ROOT / 'artifacts/dss_v2/calibration.json'
BASE = dict(policy_version='dss-v2', rule_version='weekday-transition-mae-v1',
            min_group_56=6, min_group_112=10, min_error_samples=30,
            calibration_end='2016-06-30', validation_end='2017-05-31')


def quantile(values, q):
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    return ordered[lower] + (ordered[min(lower + 1, len(ordered)-1)] - ordered[lower]) * (position-lower)


def observations(rows, support):
    policy = {**BASE, 'min_complete_56': support}
    values = {day(r['full_date']): float(r['target_guests']) for r in rows
              if r['guest_data_status'] == 'COMPLETE' and r['target_guests'] not in ('', None)}
    result = []
    first = min(values) + timedelta(days=112)
    for current, value in sorted(values.items()):
        if not first <= current <= date(2017, 5, 31):
            continue
        latest = current - timedelta(days=1)
        context = HistoricalContext(rows, latest, policy)
        # Remove one available day closest to cutoff: a deterministic missingness stress test.
        removed = max(context.window(56), default=None)
        stressed = HistoricalContext([r for r in rows if day(r['full_date']) != removed], latest, policy)
        for kind in ('weekday', 'transition'):
            if kind == 'transition' and current-timedelta(days=1) not in values:
                continue
            actual = value if kind == 'weekday' else value-values[current-timedelta(days=1)]
            reference = context.reference(current.weekday(), kind == 'transition')
            if reference is None:
                continue
            alternate = stressed.reference(current.weekday(), kind == 'transition')
            result.append(dict(date=current.isoformat(), analysis=kind,
                z=abs(actual-reference.center)/reference.variability,
                stressed_z=abs(actual-alternate.center)/alternate.variability if alternate else None))
    return result


def calibrate(snapshot=SNAPSHOT, policy_path=POLICY, report_path=REPORT):
    snapshot = Path(snapshot)
    with snapshot.open(encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    versions = {r['data_version'] for r in rows}
    assert len(versions) == 1
    candidates = {n: observations(rows, n) for n in (42, 46, 50, 53, 56)}
    # Prespecified objective: retain >=85% of permissive validation comparisons,
    # <=5% alert-or-support flips when one known day is removed; prefer higher support.
    # Threshold quantile: least conservative candidate whose validation exceedance <=5%.
    trials = []
    baseline = sum(r['date'] > BASE['calibration_end'] for r in candidates[42])
    for support, samples in candidates.items():
        thresholds, analyses = {}, {}
        for kind in ('weekday', 'transition'):
            calibration = [r['z'] for r in samples if r['analysis'] == kind and r['date'] <= BASE['calibration_end']]
            validation = [r for r in samples if r['analysis'] == kind and r['date'] > BASE['calibration_end']]
            if len(calibration) < 60 or len(validation) < 60:
                break
            options = []
            for q in (.90, .95, .975, .99):
                threshold = quantile(calibration, q)
                rate = sum(r['z'] > threshold for r in validation)/len(validation)
                options.append(dict(quantile=q, threshold=threshold, validation_tail_rate=rate))
            chosen = next((o for o in options if o['validation_tail_rate'] <= .05), None)
            if chosen is None:
                break
            threshold = chosen['threshold']
            flips = sum(r['stressed_z'] is None or (r['z'] > threshold) != (r['stressed_z'] > threshold) for r in validation)
            thresholds[kind] = threshold
            analyses[kind] = dict(calibration_n=len(calibration), validation_n=len(validation),
                                  options=options, selected=chosen, missingness_flip_rate=flips/len(validation))
        retention = sum(r['date'] > BASE['calibration_end'] for r in samples)/baseline
        eligible = len(thresholds) == 2 and retention >= .85 and all(a['missingness_flip_rate'] <= .05 for a in analyses.values())
        trials.append(dict(min_complete_56=support, retention=retention, eligible=eligible,
                           thresholds=thresholds, analyses=analyses))
    eligible = [t for t in trials if t['eligible']]
    if not eligible:
        raise ValueError('No candidate passed prespecified validation; do not publish policy')
    chosen = max(eligible, key=lambda t: t['min_complete_56'])
    policy = {**BASE, 'data_version': versions.pop(), 'min_complete_56': chosen['min_complete_56'],
              'thresholds': chosen['thresholds'], 'snapshot_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
              'selection': 'highest support with >=85% retention, <=5% missingness flips, <=5% validation tails'}
    report = dict(policy=policy, trials=trials, calibration_start=(min(day(r['full_date']) for r in rows)+timedelta(days=112)).isoformat(),
                  validation_start='2016-07-01', holdout_used_for_selection=False,
                  limitations=['Overlapping rolling windows are dependent.',
                    'Reference-tail frequency and single-day deletion flips are proxies, not operational false-alarm labels.',
                    'Selection measures historical context; separate saved-model holdout evaluation is descriptive.'])
    Path(policy_path).write_text(json.dumps(policy, indent=2)+'\n', encoding='utf-8')
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(policy=policy, trials=[{k:t[k] for k in ('min_complete_56','retention','eligible')} for t in trials]), indent=2))
    return policy


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    calibrate()
