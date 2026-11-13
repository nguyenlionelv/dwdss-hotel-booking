"""Comparable weekday/weekday-transition deviations and forecast error evidence."""
from collections import defaultdict
from datetime import timedelta
from statistics import mean
from .historical_context import day, finite


def horizon_errors(metadata, policy):
    groups = defaultdict(list)
    for metric in metadata.get('validation_metrics', {}).get('horizon', []):
        value = finite(metric.get('MAE'))
        n = finite(metric.get('scorable_n'))
        if metric.get('population') == 'COMPLETE_ONLY' and value is not None and value >= 0 and n and n > 0:
            groups[int(metric['horizon'])].append((value, n))
    return {h: {'mae': mean(value for value, _ in values),
                'sample_count': sum(n for _, n in values), 'population': 'COMPLETE_ONLY'}
            for h, values in groups.items() if sum(n for _, n in values) >= policy['min_error_samples']}


def deviations(context, rows):
    """Analysis candidates include supported neutral comparisons, before action rules."""
    results, unsupported = [], []
    previous = None
    for horizon, row in enumerate(rows, 1):
        current = day(row['forecast_date'])
        value = finite(row.get('predicted_guest_count'))
        if value is None or value < 0:
            previous = None
            unsupported.append({'horizon': horizon, 'reason': 'PREDICTION_UNAVAILABLE'})
            continue
        reference = context.reference(current.weekday())
        if reference:
            difference = value - reference.center
            results.append({'analysis': 'weekday', 'forecast_date': current, 'horizon': horizon,
                'predicted_guests': value, 'historical_reference': reference.center,
                'deviation_guests': difference, 'absolute_deviation': abs(difference),
                'deviation_pct': 100 * difference / reference.center if reference.center else None,
                'standardized_deviation': abs(difference) / reference.variability,
                'variability': reference.variability, 'sample_count': reference.count,
                'reference_window_days': reference.window_days})
        else:
            unsupported.append({'horizon': horizon, 'analysis': 'weekday', 'reason': 'REFERENCE_UNSUPPORTED'})
        if previous and current - previous['date'] == timedelta(days=1):
            reference = context.reference(current.weekday(), transition=True)
            if reference:
                change = value - previous['value']
                difference = change - reference.center
                results.append({'analysis': 'transition', 'forecast_date': current, 'horizon': horizon,
                    'previous_forecast_date': previous['date'], 'predicted_guests': value,
                    'forecast_change': change,
                    'forecast_change_pct': 100 * change / previous['value'] if previous['value'] else None,
                    'historical_reference': reference.center, 'deviation_guests': difference,
                    'absolute_deviation': abs(difference),
                    'deviation_pct': None, 'standardized_deviation': abs(difference) / reference.variability,
                    'variability': reference.variability, 'sample_count': reference.count,
                    'reference_window_days': reference.window_days})
            else:
                unsupported.append({'horizon': horizon, 'analysis': 'transition', 'reason': 'REFERENCE_UNSUPPORTED'})
        previous = {'date': current, 'value': value}
    return results, unsupported
