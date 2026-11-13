# DSS v2: context-aware advisory decisions

**Current revision:** the sensitivity audit separates descriptive Demand Insights
from Operational Advisories. See [the sensitivity report](dss_v2_sensitivity.md)
for the current threshold, validation limits and before/after results. The original
MAE-gated policy below is retained as the baseline design, not the active insight rule.

The daily API now adds `decision_support` to its existing response. A separate Python
engine combines saved forecasts, current Mart history and locked validation rules.
React renders the engine's titles, dates, evidence and advisory actions. It performs
no max/min selection, anomaly calculation or recommendation generation.

## Data and as-of convention

`latest_label_date = as_of_date - model.label_delay_days`: the saved causal model
has a one-day delay; the other two daily models have zero delay. History ends at
that label date, inclusive. The primary reference is the 56 calendar dates
`[latest_label_date - 55, latest_label_date]`; the fallback contains 112 dates.
The engine reads only that bounded range from `mart.daily_hotel_operations`,
filtered by the currently published `data_version`, using the API's existing
read-only repeatable-read transaction. It never uses forecast-row actuals.

Only nonnegative finite `target_guests` on COMPLETE dates enter statistics.
PARTIAL, MISSING and NULL targets are excluded, without zero filling or imputation.
An observed zero remains zero. Duplicate historical dates invalidate context.
Transitions require both actual consecutive calendar dates to be COMPLETE and
inside the reference window; a missing date never joins its neighbors into a pair.

At cutoff **2017-08-24**, all three models have **53 valid dates in 56 calendar
days**. The zero-delay models have mean 146.9434 and sample standard deviation
30.9792; the causal model's one-day-earlier window has mean 147.1132 and standard
deviation 30.9203. These statistics are available internally even though the
legacy strict tier rule remains unavailable on that window.

## Reference statistics and formulas

For forecast date `t`, use the sample mean `mu_w` and sample standard deviation
`s_w` of COMPLETE historical dates with `weekday(date) = weekday(t)`.
Compute signed difference `d = forecast(t) - mu_w`, absolute difference `abs(d)`,
percentage `100*d/mu_w`, and standardized absolute deviation `z = abs(d)/s_w`.
Percentage is NULL when the reference mean is zero.

For adjacent forecast dates, compute change `c = forecast(t)-forecast(t-1)`
and percentage `100*c/forecast(t-1)`, or NULL for a zero denominator.
Historical changes are grouped by the weekday of their **destination date**.
Let their sample mean and standard deviation be `mu_delta` and `s_delta`.
The transition statistic is `abs(c-mu_delta)/s_delta`. Comparing changes to their
weekday transition reference accounts for ordinary weekly seasonality.

Both analyses first try 56 days, requiring at least six group observations;
otherwise they try 112 days, requiring at least ten group observations.
The whole-window support floor is 42/56, or 84/112. Zero variance triggers the
fallback, then suppression if still unsupported. One unsupported weekday or
transition does not suppress other supported comparisons.

## Calibration and support selection

Reproduce with `python scripts/calibrate_dss.py`. It reads the existing canonical
snapshot and writes only the DSS policy and calibration report; it does not train
models or modify source data. The shipping policy is
`backend/app/services/decision_engine/policy.json`, configurable through
`DWDSS_DECISION_POLICY`. It pins the published data version and records the input
snapshot SHA-256. New versions require explicit recalibration; a mismatched or
unavailable policy produces neutral advisories while preserving forecasts.

All rule selection uses dates **2015-10-21 through 2017-05-31**:

- Calibration ends 2016-06-30, after a 112-day warmup.
- Chronological validation runs 2016-07-01 through 2017-05-31.
- Each target date is evaluated against history ending the previous day.
- Candidates are support floors 42, 46, 50, 53 and 56; group sizes remain six/ten.
- Threshold candidates are empirical calibration quantiles .90, .95, .975 and .99
  of standardized absolute deviations, separately for weekdays and transitions.
- Select the least conservative candidate with validation tail frequency <=5%,
  with at least 60 observations in each calibration and validation population.
- Select the highest support floor retaining >=85% of permissive validation
  comparisons and <=5% alert-or-support flips when the latest known historical
  day is removed with the target held fixed.

These criteria are encoded before candidate evaluation. No June-August 2017
holdout values select the policy. The policy is unavailable before the validation
end date. Historical tail validation evaluates the context reference, not ML
forecast accuracy or business outcomes.

| Minimum COMPLETE / 56 | Validation comparison retention | Result |
|---|---:|---|
| 42 | 100.00% | Selected; deletion flips 0% in both analyses |
| 46 | 99.80% | Rejected; weekday deletion flips 5.23% |
| 50 | 52.58% | Rejected; deletion flips 38.19% weekday / 43.80% transition |
| 53 | 2.98% | Rejected; insufficient validation population |
| 56 | 0.00% | Rejected; insufficient validation population |

The requested **50/56 candidate was tested and rejected**, rather than silently
approved. The selected 42/56 floor permits more missingness, but still requires
six same-weekday values or ten in the extended window. This is a measured
availability/stability tradeoff on this dataset, not a universal statistical rule.

| Analysis | Calibration n | Validation n | Selected quantile | z threshold | Validation exceedance |
|---|---:|---:|---:|---:|---:|
| Same weekday | 239 | 288 | .975 | 3.829081 | 5/288 = 1.74% |
| Weekday transition | 227 | 216 | .95 | 3.455279 | 6/216 = 2.78% |

Full candidate measurements are in `artifacts/dss_v2/calibration.json`.

## Model reliability and recommendation rules

The engine reuses the selected model's saved validation **COMPLETE_ONLY** MAE by
horizon, averaged equally across its chronological folds. It requires at least
30 scorable records in total for that horizon. ALL_ESTIMATED and IMPUTED_ONLY
metrics cannot substitute for canonical error evidence. No validation residual
distribution is saved, so none is invented.

A weekday insight requires both `z > weekday_threshold` and
`abs(d) > horizon_MAE`. A transition requires its calibrated z threshold and
`abs(c-mu_delta) > MAE_h + MAE_(h-1)`. The sum is a conservative error-scale gate,
not an independence assumption, confidence percentage or prediction interval.
Missing error evidence suppresses the affected insight only.

Above/below weekday differences map to ABOVE_TYPICAL_DEMAND and
BELOW_TYPICAL_DEMAND. Positive changes that exceed their normal transition map
to DEMAND_SURGE; negative changes below their normal transition map to DEMAND_DROP.
A smaller positive change is not labeled a drop. Neutral comparisons and reasons
remain internal metadata; they are not action cards.

Rank candidates by the smaller of their statistical-threshold ratio and their
model-error ratio, then absolute deviation, date and signal for deterministic ties.
This prioritizes evidence that clears both gates. Keep at most three cards,
deduplicating dates and action text. Ranking is a transparent evidence heuristic;
operational relevance is limited to the four advisory mappings in the task, and
has no validated monetary or staffing utility.

Every insight includes its forecast, historical reference, differences, group
sample count/window, variability, calibrated threshold, model error scale, date,
numeric evidence and review action. Response metadata includes data/model/rule
versions, policy hash, causal history boundaries, counts/coverage, comparison
results and suppression reasons. Actions request a review; they never prescribe
headcount, inventory, cost or automatic scheduling.

## Backtest, integration and UI verification

Run `python scripts/backtest_dss.py` after locking the policy. It uses existing
saved inference for **85 daily origins from 2017-06-01 through 2017-08-24**, each
forecasting seven days, for each of the three models. It hashes model files and
notebooks before/after and asserts they were not changed. Results are in
`artifacts/dss_v2/backtest.json`.

| Saved model | Origins | Origins with insights | Insight count | Deletion-changed origins |
|---|---:|---:|---:|---:|
| imputed_canonical_history | 85 | 0 | 0 | 0 |
| imputed_imputed_history | 85 | 0 | 0 | 0 |
| causal_causal_history | 85 | 0 | 0 | 0 |

All supported forecast comparisons were within calibrated historical ranges.
There were 12 unsupported transition comparisons per imputed model and 14 for
the causal model. The task's example cutoff correctly returns `state=NEUTRAL`
and `insights=[]`, while still using all 53 valid historical observations.
There is **no estimate of holdout alert precision or false-alert rate** because
no alerts fired. A zero count does not establish perfect accuracy or useful
sensitivity. The script records unconfirmed actual direction/tail proxies for
future nonempty runs, counting partial actuals as unscorable.

Automated coverage includes 53/56 statistics, zero versus NULL, future poisoning,
missing-day placement, weekday alignment, true adjacent transitions, 112-day
fallback, zero variance, MAE gates, four supported advisory types, missing policy,
causal SQL boundaries and exact saved-model prediction/API-tier preservation.
All 40 backend/model/DSS tests, ten frontend client/geometry tests (including
the live API check), and the frontend production build pass. Browser checks
cover all three live models at 1440px and 390px CSS widths and presentation-only
three-insight fixtures. These fixtures are not evidence of real model signals.

Reproduce in PowerShell from the repository root:

```powershell
$env:PYTHONPATH='.;tests/warehouse;tests/pipeline'
$env:DWDSS_INTEGRATION='1'
python -m pytest tests/dss tests/ml tests/backend -q
$env:DWDSS_API_BASE_URL='http://localhost:8000'
node --test frontend/tests/*.test.mjs
npm --prefix frontend run build
```

The reusable Playwright check is `frontend/tests/operationalSupport.browser.js`.
The existing chart remains unchanged. The main UI displays only API insights or
the concise neutral state, with no coverage, missing-day or insufficient-history
badges. The strict legacy HIGH/NORMAL/LOW implementation and all previous forecast
response fields remain intact; the additive advisory policy does not relax tiers.

## Limits and maintenance

Rolling windows and seven-day origins overlap, so observations are dependent;
reported frequencies are descriptive, not independent-sample confidence bounds.
Six/ten group observations are small samples, and sparse or constant histories
may suppress real changes. The single-day deletion stress is deliberately narrow
and does not establish robustness to arbitrary missingness or MNAR processes.
Historical reference tails are false-alert proxies only; extreme actual demand
can be a real event. Validation selection has finite-sample optimism.

The conservative thresholds produced no holdout recommendations, which limits
assessment of sensitivity and action utility. Do not lower them using these
holdout results. Further policy changes need a new development/validation plan
and operational outcome data. The dataset provides no verified capacity,
staffing, intervention outcomes or true historical publication timestamps; saved
label-delay assumptions govern the simulation. No business impact is claimed.
