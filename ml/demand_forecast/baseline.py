"""Seasonal-naive forecast without a fitted estimator."""
from datetime import timedelta
from .contracts import DemandError, HORIZON, nonnegative

def seasonal_naive(history, cutoff):
    days = [cutoff + timedelta(days=h - 7) for h in range(1, HORIZON + 1)]
    if any(day not in history or history[day] is None for day in days):
        raise DemandError("INSUFFICIENT_HISTORY", "Seasonal naive needs seven consecutive COMPLETE history days")
    return [nonnegative(history[day]) for day in days]
