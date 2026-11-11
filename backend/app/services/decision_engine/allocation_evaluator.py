"""Seven-day decision-quality evaluation, separate from forecast MAE."""

from __future__ import annotations

import math
from statistics import mean, median, pstdev

from .allocation_policies import LAMBDA_GRID, normalize, policies


def mrr(shares, actuals):
    if shares is None or len(shares) != 7 or any(not math.isfinite(float(x)) or x < 0 for x in shares):
        return None
    if abs(sum(float(x) for x in shares) - 1) > 1e-9:
        return None
    truth = normalize(actuals)
    if truth is None:
        return None
    return 0.5 * sum(abs(float(p) - float(q)) for p, q in zip(shares, truth))


def score_origin(forecasts, references, actuals):
    if normalize(actuals) is None:
        return None
    candidates, _ = policies(forecasts, references, 0.5)
    if normalize(forecasts, clip_negative=True) is None or references is None or normalize(references) is None:
        return None  # Same-origin comparison requires every policy genuinely available.
    scores = {name: mrr(shares, actuals) for name, shares in candidates.items() if name != 'blended'}
    for lam in LAMBDA_GRID:
        blend, _ = policies(forecasts, references, lam)
        scores[f'blended_{lam:g}'] = mrr(blend['blended'], actuals)
    return scores


def summarize(scored, selected):
    if not scored:
        return {'status': 'unavailable', 'reason': 'No seven-day origins with complete positive-sum actuals and supported policies'}
    names = tuple(scored[0]['scores'])
    if any(tuple(row['scores']) != names for row in scored):
        raise ValueError('Policies were not compared on identical origins')
    table = {name: [row['scores'][name] for row in scored] for name in names}
    if any(any(value is None for value in values) for values in table.values()):
        raise ValueError('Unscorable policy on shared origins')
    metrics = {}
    for name, values in table.items():
        ordered = sorted(values)
        metrics[name] = {
            'mean_mrr': mean(values), 'median_mrr': median(values),
            'std_mrr_across_origins': pstdev(values),
            'p10_mrr': ordered[int((len(ordered) - 1) * 0.1)],
            'p90_mrr': ordered[int((len(ordered) - 1) * 0.9)],
        }
    chosen = table[selected]
    for baseline in ('uniform', 'historical_weekday'):
        values = table[baseline]
        metrics[selected][f'mean_improvement_vs_{baseline}'] = mean(values) - mean(chosen)
        metrics[selected][f'win_rate_vs_{baseline}'] = sum(a < b for a, b in zip(chosen, values)) / len(chosen)
    return {'status': 'available', 'eligible_origins': len(scored),
            'first_origin': scored[0]['origin'], 'last_origin': scored[-1]['origin'],
            'selected': selected, 'policies': metrics,
            'overlapping_origins_independent': False}


def choose_policy(scored, tolerance=0.002):
    if not scored:
        return 'uniform', None, 'No evaluable development origins; safe uniform fallback'
    base = {name: mean(row['scores'][name] for row in scored)
            for name in ('uniform', 'historical_weekday', 'forecast_proportional')}
    simple = min(base, key=base.get)
    blends = {lam: mean(row['scores'][f'blended_{lam:g}'] for row in scored)
              for lam in LAMBDA_GRID if 0 < lam < 1}
    best_lam = min(blends, key=blends.get)
    if blends[best_lam] < base[simple] - tolerance:
        return 'blended', best_lam, f'Validation blend improves {simple} mean MRR by more than {tolerance:.3f}'
    return simple, None, f'Best simpler validation policy; blend did not improve mean MRR by more than {tolerance:.3f}'
