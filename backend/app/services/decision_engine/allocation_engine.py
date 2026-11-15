"""Versioned allocation of abstract weekly resource units from saved forecasts."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from .allocation_policies import POLICIES, display, policies
from .historical_context import day, read_history, weekday_allocation_reference

POLICY_FILE = Path(__file__).with_name('allocation_policy.json')


def load_allocation_policy():
    path = Path(os.getenv('DWDSS_ALLOCATION_POLICY', POLICY_FILE))
    raw = path.read_bytes()
    policy = json.loads(raw)
    if (policy.get('policy_version') != 'allocation-v1'
            or policy.get('selected_policy') not in POLICIES
            or policy.get('selected_policy') == 'blended' and policy.get('lambda') not in (0.25, 0.5, 0.75)):
        raise ValueError('Invalid allocation policy')
    return policy, hashlib.sha256(raw).hexdigest()


def _action(delta):
    if delta >= 2:
        return 'Review relative readiness for this above-equal-share day.'
    if delta <= -2:
        return 'Review whether resources can shift from this below-equal-share day.'
    return None


def allocate(rows, history, latest, data_version, model_version, budget_units=100, policy=None,
             policy_hash=None, as_of_date=None):
    amount = Decimal(str(budget_units))
    if not amount.is_finite() or amount <= 0 or amount > 10000 or amount.as_tuple().exponent < -2:
        raise ValueError('budget_units must be >0, <=10000 and have at most two decimal places')
    if len(rows) != 7:
        return {'status': 'unavailable', 'reason': 'Seven forecast days required', 'daily_allocation': []}
    dates = [day(row['forecast_date']) for row in rows]
    if as_of_date is not None and dates[0] != day(as_of_date) + timedelta(days=1):
        raise ValueError('Forecast starts outside T+1')
    if any(right - left != timedelta(days=1) for left, right in zip(dates, dates[1:])):
        raise ValueError('Forecast horizon must be seven consecutive calendar days')
    references, quality = weekday_allocation_reference(history, dates, latest)
    if policy is None:
        try:
            policy, policy_hash = load_allocation_policy()
        except (OSError, ValueError, KeyError, TypeError):
            policy = None
    version_ok = policy is not None and policy.get('data_version') == data_version
    selected = policy['selected_policy'] if version_ok else 'uniform'
    lam = policy.get('lambda') if version_ok and selected == 'blended' else None
    shares_by_policy, fallbacks = policies([row['predicted_guest_count'] for row in rows], references,
                                            lam if lam is not None else 0.5)
    shares, units = display(shares_by_policy[selected], amount)
    daily = []
    for i, (row, share, unit) in enumerate(zip(rows, shares, units)):
        comparison = (share - Decimal(1) / 7) * 100
        daily.append({
            'date': dates[i], 'predicted_guests': row['predicted_guest_count'],
            'allocation_share': float(share), 'allocation_pct': float(share * 100),
            'allocation_units': float(unit),
            'comparison_with_uniform_pct_points': float(comparison),
            'review_action': _action(float(comparison)),
        })
    evaluation = policy.get('validation_results') if version_ok else None
    return {
        'status': 'ready', 'policy_version': 'allocation-v1',
        'selected_policy': selected, 'budget_units': float(amount), 'lambda': lam,
        'daily_allocation': daily,
        'policy_evaluation': {
            'metric': 'MRR', 'validation_results': evaluation,
            'selected_policy_reason': policy.get('selected_policy_reason') if version_ok else
                'Policy unavailable or data version changed; safe uniform allocation',
            'availability': 'available' if evaluation and evaluation.get('status') == 'available' else 'unavailable',
        },
        'metadata': {'data_version': data_version, 'model_version': model_version,
                     'effective_history_cutoff': day(latest), 'policy_sha256': policy_hash if version_ok else None,
                     'historical_quality': quality, 'fallbacks': fallbacks,
                     'units_meaning': 'relative abstract units, not staff, rooms, money or hours',
                     'evaluation_population': 'causal development proxy; saved-model holdout is descriptive only'},
    }


def resource_allocation(conn, rows, metadata, latest, version, budget_units=100, as_of_date=None):
    history = read_history(conn, version, latest)
    return allocate(rows, history, latest, version, metadata['model_version'], budget_units,
                    as_of_date=as_of_date)
