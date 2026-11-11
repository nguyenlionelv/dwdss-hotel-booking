"""Reusable DSS v2 service, with truthful internal status and a neutral fallback."""
from collections import Counter
from datetime import timedelta
import hashlib
import json
import logging
import os
from pathlib import Path
from .historical_context import HistoricalContext, day, finite, read_history
from .demand_analysis import deviations, horizon_errors
from .decision_rules import actionable, rank_insights

LOGGER = logging.getLogger(__name__)
DEFAULT_POLICY = Path(__file__).with_name('policy.json')


def load_policy():
    path = Path(os.getenv('DWDSS_DECISION_POLICY', DEFAULT_POLICY))
    raw = path.read_bytes()
    policy = json.loads(raw)
    if policy['policy_version'] != 'dss-v2' or not 1 <= policy['min_complete_56'] <= 56:
        raise ValueError('Invalid DSS v2 policy')
    if any(finite(policy['thresholds'][key]) is None or policy['thresholds'][key] <= 0
           for key in ('weekday', 'transition')):
        raise ValueError('Uncalibrated DSS v2 thresholds')
    if not 2 <= policy['min_group_56'] <= 8 or not 2 <= policy['min_group_112'] <= 16 or policy['min_error_samples'] < 1:
        raise ValueError('Invalid DSS v2 sample requirements')
    if 'insight_thresholds' in policy:
        value = finite(policy['insight_thresholds'].get('weekday'))
        if value is None or value <= 0:
            raise ValueError('Invalid insight threshold')
    return policy, hashlib.sha256(raw).hexdigest()


def neutral(status, **metadata):
    return {'policy_version': 'dss-v2', 'state': 'NEUTRAL', 'insights': [],
            'metadata': {'status': status, **metadata}}


def evaluate(rows, forecasts, metadata, latest, version, policy, policy_hash='test'):
    latest = day(latest)
    trace = {'data_version': version, 'model_version': metadata.get('model_version'),
             'policy_sha256': policy_hash, 'rule_version': policy['rule_version'],
             'history_end': latest.isoformat(), 'history_start': (latest - timedelta(days=111)).isoformat()}
    if version != policy['data_version']:
        return neutral('POLICY_DATA_VERSION_MISMATCH', **trace)
    if latest < day(policy['validation_end']):
        return neutral('POLICY_NOT_YET_AVAILABLE', **trace)
    context = HistoricalContext(rows, latest, policy)
    comparisons, unsupported = deviations(context, forecasts)
    errors = horizon_errors(metadata, policy)
    candidates = []
    suppressions = Counter(item['reason'] for item in unsupported)
    for comparison in comparisons:
        insight, reason = actionable(comparison, errors, policy)
        if insight:
            candidates.append(insight)
        else:
            suppressions[reason] += 1
    selected = rank_insights(candidates)
    state = ('INSIGHTS' if 'insight_thresholds' in policy else 'ACTIONABLE') if selected else 'NEUTRAL'
    return {'policy_version': 'dss-v2', 'state': state, 'insights': selected,
            'metadata': {'status': 'READY', **trace, 'available_case_56': context.summary(),
                'comparisons': comparisons, 'suppressions': dict(suppressions),
                'reliability': errors, 'limitations': [
                    'Demand insights describe expected differences; operational advisories are not validated.',
                    'MAE is an error scale, not a prediction interval or confidence level.',
                    'Publication timing is assumed; no operational capacity or staffing outcomes are available.']}}


def decision_support(conn, forecasts, metadata, latest, version):
    try:
        policy, fingerprint = load_policy()
    except (OSError, ValueError, KeyError, TypeError):
        LOGGER.warning('DSS v2 policy unavailable; forecasts remain available')
        return neutral('POLICY_UNAVAILABLE', data_version=version)
    rows = read_history(conn, version, latest)
    try:
        return evaluate(rows, forecasts, metadata, latest, version, policy, fingerprint)
    except (ValueError, KeyError, TypeError):
        LOGGER.warning('DSS v2 historical context invalid; forecasts remain available')
        return neutral('HISTORICAL_CONTEXT_UNAVAILABLE', data_version=version, policy_sha256=fingerprint)
