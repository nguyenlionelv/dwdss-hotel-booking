"""Pure allocation invariants and causal reference selection."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.app.services.decision_engine.allocation_engine import allocate
from backend.app.services.decision_engine.allocation_evaluator import mrr, score_origin, choose_policy
from backend.app.services.decision_engine.allocation_policies import display, normalize, policies
from backend.app.services.decision_engine.historical_context import weekday_allocation_reference


def week(start=date(2017, 8, 25)):
    return [start + timedelta(days=i) for i in range(7)]


def history(end=date(2017, 8, 24), days=56, missing=()):
    return [dict(full_date=end - timedelta(days=i), target_guests=100 + (i % 7) * 10,
                 guest_data_status='MISSING' if i in missing else 'COMPLETE')
            for i in range(days)]


def test_four_policies_and_exact_display_totals():
    forecast = [10, 20, 30, 40, 50, 60, 70]
    refs = [10] * 7
    shares, fallbacks = policies(forecast, refs, .5)
    assert fallbacks == {'historical_fallback': None, 'forecast_fallback': None}
    assert all(share == Decimal(1) / 7 for share in shares['uniform'])
    assert shares['forecast_proportional'][0] == Decimal(10) / Decimal(280)
    assert float(shares['blended'][0]) == pytest.approx(float((shares['forecast_proportional'][0] + shares['historical_weekday'][0]) / 2))
    assert policies(forecast, refs, 0)[0]['blended'] == shares['historical_weekday']
    assert policies(forecast, refs, 1)[0]['blended'] == shares['forecast_proportional']
    for name, policy in shares.items():
        displayed, units = display(policy, 100)
        assert sum(displayed) == 1, name
        assert sum(units) == 100, name
        assert min(displayed) >= 0 and min(units) >= 0


def test_zero_forecast_and_missing_reference_safe_fallbacks():
    shares, fallback = policies([0] * 7, None, .5)
    assert fallback['forecast_fallback'] == 'uniform'
    assert fallback['historical_fallback']
    assert shares['forecast_proportional'] == shares['uniform']
    shares, fallback = policies([0] * 7, [1, 2, 3, 4, 5, 6, 7], .5)
    assert fallback['forecast_fallback'] == 'historical_weekday'
    shares, _ = policies([-1, 1, 1, 1, 1, 1, 1], None, .5)
    assert shares['forecast_proportional'][0] == 0
    assert normalize([1, None, 1, 1, 1, 1, 1]) is None


def test_53_of_56_complete_supported_and_future_poison_ignored():
    latest = date(2017, 8, 24)
    rows = history(missing=(0, 3, 10))
    refs, quality = weekday_allocation_reference(rows, week(), latest)
    assert refs is not None and len(refs) == 7
    assert quality['complete_dates_56'] == 53
    poisoned = rows + [dict(full_date=latest + timedelta(days=1), target_guests=1e9,
                            guest_data_status='COMPLETE')]
    assert weekday_allocation_reference(poisoned, week(), latest) == (refs, quality)
    sparse = history(missing=tuple(range(15)))
    assert weekday_allocation_reference(sparse, week(), latest)[0] is None


def test_twelve_week_causal_fallback():
    latest = date(2017, 8, 24)
    rows = history(days=84, missing=(0, 7, 14))
    refs, quality = weekday_allocation_reference(rows, week(), latest)
    assert refs is not None
    assert any(item['status'] == '12_WEEK_FALLBACK' for item in quality['weekday_support'])
    assert all(item['window_days'] in (56, 84) for item in quality['weekday_support'])


def test_mrr_and_policy_selection_on_identical_origins():
    perfect = normalize([1, 2, 3, 4, 5, 6, 7])
    assert mrr(perfect, [1, 2, 3, 4, 5, 6, 7]) == pytest.approx(0)
    assert mrr(normalize([1] * 7), [7, 0, 0, 0, 0, 0, 0]) == pytest.approx(6 / 7)
    assert mrr(perfect, [0] * 7) is None
    assert mrr(perfect, [None] * 7) is None
    scores = score_origin([1] * 7, [1, 2, 3, 4, 5, 6, 7], [1, 2, 3, 4, 5, 6, 7])
    selected, lam, _ = choose_policy([{'origin': '2017-01-01', 'scores': scores}])
    assert selected == 'historical_weekday' and lam is None


def test_engine_is_deterministic_and_respects_effective_cutoff():
    latest = date(2017, 8, 23)  # one-day reporting delay at origin 2017-08-24
    rows = [{'forecast_date': target.isoformat(), 'predicted_guest_count': 100 + i * 10}
            for i, target in enumerate(week())]
    hist = history(end=latest, days=84)
    policy = {'data_version': 'test', 'selected_policy': 'forecast_proportional',
              'validation_results': {'status': 'available'}, 'selected_policy_reason': 'test'}
    result = allocate(rows, hist, latest, 'test', 'model-v1', 100, policy, 'hash', date(2017, 8, 24))
    assert result == allocate(rows, hist, latest, 'test', 'model-v1', 100, policy, 'hash', date(2017, 8, 24))
    assert result['metadata']['effective_history_cutoff'] == latest
    assert sum(day['allocation_units'] for day in result['daily_allocation']) == 100
    assert sum(day['allocation_share'] for day in result['daily_allocation']) == 1
    assert [day['predicted_guests'] for day in result['daily_allocation']] == [row['predicted_guest_count'] for row in rows]
    assert allocate(rows[:3], hist, latest, 'test', 'model-v1')['status'] == 'unavailable'
