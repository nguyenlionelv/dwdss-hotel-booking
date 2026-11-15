"""Pure seven-day allocation policies; no training or database access."""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_FLOOR

POLICIES = ("uniform", "historical_weekday", "forecast_proportional", "blended")
LAMBDA_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
SHARE_SCALE = 1_000_000  # integer microshares: exact sum=1 in API decimals


def _valid(values, *, allow_negative=False):
    return len(values) == 7 and all(
        isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
        and math.isfinite(float(value)) and (allow_negative or value >= 0) for value in values
    )


def normalize(values, *, clip_negative=False):
    if not _valid(values, allow_negative=clip_negative):
        return None
    clipped = [max(Decimal(0), Decimal(str(value))) if clip_negative else Decimal(str(value)) for value in values]
    total = sum(clipped)
    if total <= 0:
        return None
    return tuple(value / total for value in clipped)


def uniform():
    return (Decimal(1) / Decimal(7),) * 7


def policies(forecasts, references, lam):
    if not 0 <= lam <= 1:
        raise ValueError("lambda must be in [0,1]")
    u = uniform()
    h = normalize(references) if references is not None else None
    f = normalize(forecasts, clip_negative=True)
    forecast_fallback = None
    historical_fallback = None
    if h is None:
        h = u
        historical_fallback = "uniform: insufficient or zero historical weekday reference"
    if f is None:
        f = h
        forecast_fallback = "historical_weekday" if historical_fallback is None else "uniform"
    weight = Decimal(str(lam))
    blend = tuple(weight * a + (1 - weight) * b for a, b in zip(f, h))
    return dict(zip(POLICIES, (u, h, f, blend))), {
        "historical_fallback": historical_fallback,
        "forecast_fallback": forecast_fallback,
    }


def apportion(shares, total_ticks):
    """Largest remainder, stable index tie-break; exact displayed totals."""
    raw = [share * total_ticks for share in shares]
    base = [int(value.to_integral_value(rounding=ROUND_FLOOR)) for value in raw]
    remaining = total_ticks - sum(base)
    order = sorted(range(7), key=lambda i: (-(raw[i] - base[i]), i))
    for i in order[:remaining]:
        base[i] += 1
    return base


def display(shares, budget):
    amount = Decimal(str(budget))
    if not amount.is_finite() or amount <= 0 or amount > 10000 or amount.as_tuple().exponent < -2:
        raise ValueError("budget must be >0, <=10000 and have at most two decimal places")
    micro = apportion(shares, SHARE_SCALE)
    cents = apportion(shares, int(amount * 100))
    return [Decimal(value) / SHARE_SCALE for value in micro], [Decimal(value) / 100 for value in cents]
