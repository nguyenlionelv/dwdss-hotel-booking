"""Calibrated, error-aware advisory rules. No capacity or staffing decisions."""
ACTIONS = {
    'ABOVE_TYPICAL_DEMAND': 'Review reception and housekeeping readiness.',
    'BELOW_TYPICAL_DEMAND': 'Review shift and resource allocation.',
    'DEMAND_SURGE': 'Review staffing continuity across adjacent days.',
    'DEMAND_DROP': 'Reassess supply preparation and workload allocation.',
}
TITLES = {
    'ABOVE_TYPICAL_DEMAND': 'Above typical demand', 'BELOW_TYPICAL_DEMAND': 'Below typical demand',
    'DEMAND_SURGE': 'Unusual demand increase', 'DEMAND_DROP': 'Unusual demand decrease',
}


def actionable(candidate, errors, policy):
    if 'insight_thresholds' in policy:
        return demand_insight(candidate, errors, policy)
    h = candidate['horizon']
    if h not in errors:
        return None, 'ERROR_EVIDENCE_UNAVAILABLE'
    error = errors[h]['mae']
    if candidate['analysis'] == 'transition':
        if h - 1 not in errors:
            return None, 'ERROR_EVIDENCE_UNAVAILABLE'
        # Conservative sum of error scales, not an independence assumption or interval.
        error += errors[h - 1]['mae']
    threshold = policy['thresholds'][candidate['analysis']]
    if candidate['standardized_deviation'] <= threshold:
        return None, 'WITHIN_TYPICAL_RANGE' if candidate['analysis'] == 'weekday' else 'STABLE_DEMAND'
    if candidate['absolute_deviation'] <= error:
        return None, 'DEVIATION_WITHIN_MODEL_MAE'
    if candidate['analysis'] == 'weekday':
        signal = 'ABOVE_TYPICAL_DEMAND' if candidate['deviation_guests'] > 0 else 'BELOW_TYPICAL_DEMAND'
        percent = f" ({candidate['deviation_pct']:+.1f}%)" if candidate['deviation_pct'] is not None else ''
        evidence = (f"{candidate['predicted_guests']:.1f} forecast vs {candidate['historical_reference']:.1f} "
                    f"typical {candidate['forecast_date'].strftime('%A')}{percent}.")
    else:
        # A smaller-than-usual increase is not a demand drop, and vice versa.
        change = candidate['forecast_change']
        if change > 0 and candidate['deviation_guests'] > 0:
            signal = 'DEMAND_SURGE'
        elif change < 0 and candidate['deviation_guests'] < 0:
            signal = 'DEMAND_DROP'
        else:
            return None, 'CHANGE_DIRECTION_NOT_ACTIONABLE'
        evidence = (f"{change:+.1f} forecast guests vs {candidate['historical_reference']:+.1f} "
                    f"typical change into {candidate['forecast_date'].strftime('%A')}.")
    statistical_ratio = candidate['standardized_deviation'] / threshold
    strength = min(statistical_ratio, candidate['absolute_deviation'] / error) if error else statistical_ratio
    return {**candidate, 'signal': signal, 'title': TITLES[signal], 'priority': 'REVIEW',
            'recommended_action': ACTIONS[signal], 'evidence': evidence, 'strength': strength,
            'model_error_scale': error, 'error_population': 'COMPLETE_ONLY',
            'calibrated_standardized_threshold': threshold}, None


def demand_insight(candidate, errors, policy):
    """Describe expected demand; actions await actual forecast/outcome validation."""
    if candidate['analysis'] != 'weekday':
        return None, 'TRANSITION_ADVISORY_NOT_VALIDATED'
    threshold = policy['insight_thresholds']['weekday']
    if candidate['standardized_deviation'] <= threshold:
        return None, 'WITHIN_INSIGHT_RANGE'
    above = candidate['deviation_guests'] > 0
    signal = 'ABOVE_TYPICAL_DEMAND' if above else 'BELOW_TYPICAL_DEMAND'
    percent = f" ({candidate['deviation_pct']:+.1f}%)" if candidate['deviation_pct'] is not None else ''
    error = errors.get(candidate['horizon'], {}).get('mae')
    return {**candidate, 'signal': signal, 'title': 'Expected demand above reference' if above else 'Expected demand below reference',
        'category': 'DEMAND_INSIGHT', 'priority': 'INSIGHT', 'recommended_action': None,
        'evidence': f"{candidate['predicted_guests']:.1f} forecast vs {candidate['historical_reference']:.1f} typical {candidate['forecast_date'].strftime('%A')}{percent}.",
        'strength': candidate['standardized_deviation']/threshold,
        'model_error_scale': error, 'error_population': 'COMPLETE_ONLY' if error is not None else None,
        'calibrated_standardized_threshold': threshold}, None


def rank_insights(candidates):
    ranked = sorted(candidates, key=lambda c: (-c['strength'], -c['absolute_deviation'], c['forecast_date'], c['signal']))
    selected, dates, actions = [], set(), set()
    for candidate in ranked:
        key = candidate.get('recommended_action') or candidate['signal']
        if candidate['forecast_date'] in dates or key in actions:
            continue
        selected.append(candidate)
        dates.add(candidate['forecast_date'])
        actions.add(key)
        if len(selected) == 3:
            break
    return selected
