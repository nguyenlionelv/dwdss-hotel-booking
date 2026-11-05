from copy import deepcopy
from math import sqrt

import pytest

from scripts.verify_demand_metrics import check_score


def fixture_score():
    rows = [{"as_of_date": "2020-01-01", "horizon": 1, "predicted_guest_count": 4, "actual_guest_count": 1},
            {"as_of_date": "2020-01-01", "horizon": 2, "predicted_guest_count": 1, "actual_guest_count": 5}]
    # Independently computed errors +3 and -4.
    saved = {"mae": 3.5, "rmse": sqrt(12.5), "bias": -.5, "points": 2, "origins": 1,
             "by_horizon": {str(h): {"points": 1 if h <= 2 else 0,
                                      "mae": 3 if h == 1 else 4, "rmse": 3 if h == 1 else 4} for h in range(1, 8)}}
    return rows, saved


def test_independent_metric_recalculation():
    rows, saved = fixture_score()
    check_score(rows, saved)


def test_metric_tampering_is_detected():
    rows, saved = fixture_score()
    for mutate in ["overall", "horizon"]:
        invalid = deepcopy(saved)
        if mutate == "overall": invalid["mae"] = 0
        else: invalid["by_horizon"]["2"]["rmse"] = 0
        with pytest.raises(ValueError): check_score(rows, invalid)
