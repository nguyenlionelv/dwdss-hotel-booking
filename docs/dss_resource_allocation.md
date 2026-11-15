# DSS resource allocation (City Hotel)

## Decision and contract

`GET /api/dss/demand-forecast?as_of_date=2017-08-24&horizon=7&budget_units=100` keeps the existing forecast and DSS fields and adds `resource_allocation`. The weekly budget defaults to **100 abstract units**; it can be set to a positive amount up to 10,000 with two decimal places. Units express relative planning priority, not people, rooms, money, capacity or working hours. The service returns seven consecutive dates, original ML forecasts, daily shares, percentages, units, differences from an equal share, concise review actions, policy evidence and provenance. A shorter forecast horizon returns an explicit unavailable allocation.

For forecast demand `f_d`, historical matching-weekday median `r_d` and eligible actual demand `y_d`:

- Uniform: `p_d = 1/7`.
- Historical weekday: `p_d = r_d / sum(r)`.
- Forecast proportional: `p_d = max(0, f_d) / sum(max(0, f))`.
- Blend: `p_d = λ p_d^forecast + (1−λ) p_d^historical`, with a predefined grid `λ ∈ {0, .25, .5, .75, 1}`.
- Allocation: `a_d = B × p_d`. Largest-remainder apportionment uses integer millionths of a share and cents of a unit, so displayed shares sum to exactly 100.0000% and units to the requested budget.
- Misallocated Resource Ratio: `MRR = 0.5 × sum(|p_d − y_d/sum(y)|)`. Lower is better. It measures distribution mismatch, not staffing cost or financial loss. Forecast MAE remains a separate absolute-error measure.

The historical reference uses only `mart.daily_hotel_operations` records with `guest_data_status = COMPLETE`, nonnegative non-NULL `target_guests`, and date at or before the saved model's effective label cutoff. It takes the median of the closest eight matching weekdays in 56 days when at least six exist. Otherwise it extends to 12 weeks and requires eight matching weekdays. It does not impute missing labels or require all 56 days complete; the 2017-08-24 case with 53/56 complete days is supported. If a reference is unavailable, historical allocation falls back to uniform. A zero or unusable forecast total falls back to historical, then uniform. Fallbacks and historical support remain in backend metadata.

The chosen policy is loaded from the versioned `allocation_policy.json` artifact only when its Mart `data_version` matches the published version; otherwise the service uses uniform and marks evaluation unavailable. The artifact hash, model version, data version and effective history cutoff are returned. Model-specific label delay is supplied by the existing `daily_prediction` path (0 for the imputed variants, 1 for the causal variant). Future actuals are used only for retrospective scoring. No model was retrained or changed.

## Development evidence and limitation

The saved final models do **not** contain archived per-origin predictions from a pre-selection validation period. Their validation CSVs contain aggregate error metrics. Replaying their final fitted state on that development period would be an in-sample evaluation. To avoid claiming that as validation, `scripts/calibrate_allocation.py` uses a fixed, causal recent-level **proxy forecast** on historical development origins and labels its results accordingly. It does not calibrate on the previously inspected holdout. All four policies and all blend weights use the **same 58 seven-day validation origins** (2017-01-01 through 2017-05-24), each with seven COMPLETE, nonnegative actual labels and positive total demand. Overlapping origins are dependent, so dispersion across origins is descriptive, not an independent-sample confidence interval.

| Policy | Mean validation MRR | Median validation MRR |
| --- | ---: | ---: |
| Uniform | 0.11085 | 0.10925 |
| Historical weekday | **0.10222** | 0.09853 |
| Forecast proportional, causal proxy | 0.10287 | **0.09475** |
| Blend λ=.25 | 0.10235 | 0.09757 |
| Blend λ=.50 | 0.10250 | 0.09661 |
| Blend λ=.75 | 0.10267 | 0.09564 |

Historical weekday has the lowest mean MRR on this proxy validation, improving on uniform by 0.00862 MRR and winning on 65.5% of eligible origins. No interior blend improves on it by the predefined 0.002 mean-MRR margin, so `allocation-v1` selects the simpler historical policy. The proxy MAE is 23.67 guests per day on the same origins. This **does not demonstrate that the selected saved ML model improves allocation** over historical weekday. With this evidence, the active proposal uses historical weekday shares while preserving and exposing the model forecast and forecast-proportional policy metric. A model-specific pre-selection validation prediction archive would be needed to choose a forecast-driven policy on genuine saved-model validation evidence.

The already-inspected June–August 2017 holdout is summarized separately in `artifacts/allocation/holdout_descriptive.json`; it was **not** used to select policy or λ. Its 54 common complete seven-day origins show lower mean MRR for forecast proportional than historical for each saved model (approximately 0.0768–0.0774 versus 0.0822–0.0829), which is descriptive and cannot repair the missing untouched validation evidence. Saved-model MAE on those same origins is approximately 23.2–23.5 guests/day. The API's existing `model_comparison` also retains the model error metrics and their protocol labels.

## Reproduce and verify

From the repository root, with the existing snapshot and saved models present:

```powershell
python scripts/calibrate_allocation.py
$env:PYTHONPATH='.;tests/warehouse;tests/pipeline'
$env:DWDSS_INTEGRATION='1'
python -m pytest tests/dss/test_allocation.py tests/dss/test_api_integration.py -q
npm --prefix frontend run build
node --test frontend/tests/*.test.mjs
```

Calibration writes the policy, `artifacts/allocation/validation.json` and the separate descriptive holdout audit. The integration test needs a published local PostgreSQL Mart and the saved model artifacts. The pure tests cover all four policies, exact allocation totals, λ endpoints and midpoint, zero-demand fallback, 53/56 and 12-week history, future-row exclusion, MRR, deterministic output and the effective cutoff. The API integration test verifies unchanged ML predictions and existing DSS fields, seven-day allocation, model-specific cutoff, provenance and custom budget. The UI shows a seven-day allocation chart and validation comparison; DSS v2 insights remain secondary.
