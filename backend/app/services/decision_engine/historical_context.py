"""Causal available-case history. Missing days never become zero or adjacent pairs."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import math
from statistics import mean, median, stdev


def day(value):
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def finite(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True)
class Reference:
    center: float
    variability: float
    count: int
    window_days: int
    start: date
    end: date


class HistoricalContext:
    def __init__(self, rows, latest, policy):
        self.latest, self.policy = day(latest), policy
        self.known = {}
        seen = set()
        for row in rows:
            current = day(row['full_date'])
            if current > self.latest:
                continue
            if current in seen:
                raise ValueError('Duplicate historical calendar date')
            seen.add(current)
            value = finite(row['target_guests'])
            if row['guest_data_status'] == 'COMPLETE' and value is not None and value >= 0:
                self.known[current] = value

    def window(self, days):
        start = self.latest - timedelta(days=days - 1)
        return {d: v for d, v in self.known.items() if start <= d <= self.latest}

    def summary(self):
        values = list(self.window(56).values())
        return {'calendar_days': 56, 'sample_count': len(values), 'coverage': len(values) / 56,
                'mean': mean(values) if values else None,
                'std': stdev(values) if len(values) > 1 else None,
                'supported': len(values) >= self.policy['min_complete_56']}

    def reference(self, weekday, transition=False):
        for days, minimum in [(56, self.policy['min_group_56']), (112, self.policy['min_group_112'])]:
            known = self.window(days)
            if len(known) < math.ceil(self.policy['min_complete_56'] * days / 56):
                continue
            values = []
            for current, value in known.items():
                if current.weekday() != weekday:
                    continue
                if transition:
                    previous = current - timedelta(days=1)
                    if previous in known:
                        values.append(value - known[previous])
                else:
                    values.append(value)
            if len(values) < minimum:
                continue
            variability = stdev(values)
            if variability > 0:
                return Reference(mean(values), variability, len(values), days,
                                 self.latest - timedelta(days=days - 1), self.latest)
        return None


def read_history(conn, version, latest):
    """Read the current Mart inside the API's existing read-only snapshot."""
    latest = day(latest)
    return conn.execute('''SELECT full_date,target_guests,guest_data_status
        FROM mart.daily_hotel_operations WHERE data_version=%s AND full_date BETWEEN %s AND %s
        ORDER BY full_date''', (version, latest - timedelta(days=111), latest)).fetchall()


def weekday_allocation_reference(rows, forecast_dates, latest):
    """Causal medians: 8 recent weekdays, >=6/8; then 12 weeks, >=8/12."""
    cutoff = day(latest)
    if len(forecast_dates) != 7:
        raise ValueError('Allocation requires exactly seven dates')
    known = {}
    for row in rows:
        current = day(row['full_date'])
        if current > cutoff:
            continue
        if current in known:
            raise ValueError('Duplicate historical date')
        value = finite(row['target_guests'])
        if row['guest_data_status'] == 'COMPLETE' and value is not None and value >= 0:
            known[current] = value
    references, details = [], []
    for target in forecast_dates:
        weekday = day(target).weekday()
        chosen = None
        for window, minimum in ((56, 6), (84, 8)):
            values = sorted((current, value) for current, value in known.items()
                            if cutoff - timedelta(days=window - 1) <= current <= cutoff
                            and current.weekday() == weekday)
            values = values[-(window // 7):]
            if len(values) >= minimum:
                chosen = (median(value for _, value in values), len(values), window)
                break
        if chosen is None:
            references.append(None)
            details.append({'date': day(target).isoformat(), 'weekday': weekday,
                            'sample_count': 0, 'window_days': None, 'status': 'UNSUPPORTED'})
        else:
            value, count, window = chosen
            references.append(value)
            details.append({'date': day(target).isoformat(), 'weekday': weekday,
                            'sample_count': count, 'window_days': window,
                            'status': '8_WEEK' if window == 56 else '12_WEEK_FALLBACK'})
    supported = all(value is not None for value in references) and sum(references) > 0
    return (references if supported else None), {
        'history_end': cutoff.isoformat(), 'reference_method': 'matching_weekday_median',
        'initial_window_days': 56, 'extended_window_days': 84,
        'complete_dates_56': sum(cutoff - timedelta(days=55) <= d <= cutoff for d in known),
        'weekday_support': details,
        'status': 'SUPPORTED' if supported else 'UNAVAILABLE',
    }
