# Demand forecasting and DSS: accepted results

Read [README.md](README.md) to integrate the service. This report is for the project report, experiment review and optional reproduction; integration does not depend on reading the old investigation notes.

## Accepted state

| Item | Accepted value |
| --- | --- |
| Strategy | Seasonal Naive |
| Model version | selected-5404d277942e |
| Feature schema | demand-weekly-v1 |
| Data version | acce45d3-aae7-465e-80a4-e0f33fb1256c |
| Official run | artifacts/metrics/demand_feature_versions_20261105 |
| Official DSS evidence | artifacts/metrics/demand_dss_20261105 |
| Source quality | 57 DW/Mart checks passed |
| Core acceptance tests | 84 passed before documentation/package consolidation |
| Application state | Core service ready; FastAPI/frontend wiring not verified |

The run directories are immutable evidence, not source files to commit. Neither model fitting nor warehouse writes were performed for DSS or this consolidation. Historical model manifests retain the code/runtime hashes recorded at training; source changes for DSS do not rewrite that history.

## Changes a reviewer needs to understand

| Area | Files | Purpose |
| --- | --- | --- |
| Serving | `service.py`, `dss.py`, `predict.py`, `contracts.py`, `artifacts.py`, `data.py` | Forecast/DSS orchestration, rule calculation, schemas, provenance and validated data access |
| Feature/training | `features.py`, `train.py`, `baseline.py`, `workflow.py` | Version-specific eligibility, training-only preprocessing, baseline and chronological experiments |
| Comparison/reporting | `comparison.py`, `filtering.py`, `comparison_report.py`, two config JSON files | Nine primary candidates, controlled subsets, frozen selection and result generation |
| Entry points | `scripts/forecast_dss.py`, `package_demand_handoff.py` | The two commands relevant to a serving handoff |
| Research/verification | Remaining demand feature/train/compare/verify scripts and `tests/ml` | Reproduce/check experiments and regression behavior when needed |

Files in the first three rows are under `ml/demand_forecast/`. Training/report code remains separate from request-time inference; the default serving package includes only the runtime import closure, accepted inputs and response references. No backend/frontend files or other branches were changed. Existing unrelated `report.md` and the user's `task.md` were left alone.

## Data filtering and seasonal representation

79,330 reservation facts aggregate into **793 daily observations**. These grains differ; aggregation does not discard 78,537 reservations. Chronological partitions are:

| Partition | Inclusive dates | Calendar days | COMPLETE targets | PARTIAL targets |
| --- | --- | ---: | ---: | ---: |
| Train | 2015-07-01–2016-03-31 | 275 | 249 | 26 |
| Validation | 2016-04-01–2017-05-31 | 426 | 345 | 81 |
| Test | 2017-06-01–2017-08-31 | 92 | 85 | 7 |

No calendar dates are missing. The 793→275 step reserves 518 validation/test dates. Within training, eligibility is nested:

| Condition | Before | Newly excluded | Remaining |
| --- | ---: | ---: | ---: |
| COMPLETE, non-NULL target | 275 | 26 | 249 |
| V1: exact d−7 COMPLETE | 249 | 31 | 218 |
| V2: all preceding seven days COMPLETE | 218 | 87 | 131 |
| V3: all preceding fourteen days COMPLETE | 131 | 76 | 55 |

V1 uses lag_7 and calendar (weekday/month/weekend); V2 adds lag_1 and rolling_mean_7; V3 adds rolling_mean_14. Rolling windows end at d−1. Each version has its own readiness mask; removing an estimator column while retaining V3 readiness would not restore samples.

Marginal failures overlap: training target=26, lag_1=27, lag_7=33, rolling_7=131, rolling_14=213. There are 19 dates failing both target and fourteen-day history, so excluded union=26+213−19=220, leaving 55. Equivalently, 26 PARTIAL targets, 14 initial warm-up dates and 180 further COMPLETE dates affected by previous PARTIAL history are excluded. Exact combinations and dates remain in the accepted run's `filtering.json`.

The live source audit identified 33 non-canceled zero-guest reservations on the 26 PARTIAL training dates. Existing rules mark those bookings guest-ineligible and suppress that day's target. All four missing-children bookings are canceled and do not cause these losses. No rule was relaxed and no NULL target was replaced by zero/subtotals.

Examples: July 23, 2015 is PARTIAL; July 30 fails V1 because d−7 is July 23; July 24 passes V1 but fails V2 because yesterday is PARTIAL; August 2 passes V2 but fails V3 because its older seven history dates contain PARTIAL days.

| Training month | Calendar days | COMPLETE | V1 | V2 | V3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2015-07 | 31 | 29 | 21 | 15 | 8 |
| 2015-08 | 31 | 26 | 22 | 14 | 0 |
| 2015-09 | 30 | 27 | 23 | 8 | 0 |
| 2015-10 | 31 | 27 | 22 | 12 | 1 |
| 2015-11 | 30 | 28 | 27 | 21 | 14 |
| 2015-12 | 31 | 29 | 26 | 8 | 0 |
| 2016-01 | 31 | 31 | 31 | 31 | 24 |
| 2016-02 | 29 | 24 | 21 | 4 | 3 |
| 2016-03 | 31 | 28 | 25 | 18 | 5 |

V3 loses three entire months; November/January supply 38/55 rows. V1 restores representation across all training months. More rows also change date composition, so they do not guarantee better generalization.

## Model comparison and selection

All primary candidates use identical **28 common validation origins / 196 scored points**. MAE/RMSE are guests per forecast day. Seeds and model configurations are consistent, preprocessing fits training data only, and seven-day inference reads no actual after cutoff T.

| Version | Model | Training rows | Common MAE | Common RMSE | Expanded validation origins |
| --- | --- | ---: | ---: | ---: | ---: |
| Baseline | Seasonal Naive | N/A | 46.244898 | 55.778169 | 50 |
| V1 | Linear Regression | 218 | 63.380346 | 77.819348 | 50 |
| V1 | Random Forest | 218 | 48.403215 | 63.050631 | 50 |
| V1 | XGBoost | 218 | 51.874132 | 67.092820 | 50 |
| V2 | Linear Regression | 131 | 60.832433 | 74.701065 | 50 |
| V2 | Random Forest | 131 | 48.020478 | 62.135714 | 50 |
| V2 | XGBoost | 131 | 48.437814 | 63.615273 | 50 |
| V3 | Linear Regression | 55 | 79.113219 | 92.095654 | 28 |
| V3 | Random Forest | 55 | 62.296069 | 78.132147 | 28 |
| V3 | XGBoost | 55 | 50.827130 | 65.554369 | 28 |

V1/V2 support 50/420 eligible validation windows (11.90%) versus V3's 28/420 (6.67%). Expanded-origin scores were not mixed into ranking. For example, V2 Forest expanded MAE=45.607232 is worse than naive on those same origins (42.422857); comparing it with naive's common MAE=46.244898 would falsely suggest improvement.

Controlled analysis compares V1 on 218/131/55-date subsets, V2 on 131/55, and V3 on 55, with all three model families on identical common origins. Nine fits are reused and nine additional fits were executed. With V1 features, Forest MAE improves 82.0076→54.9626→48.4032 as the eligible subset grows 55→131→218. At fixed 55 dates, XGBoost improves V1 80.5693→V2 58.8565→V3 50.8271. V1 Linear Regression is slightly worse on 218 than 131 dates, so the benefit is not universal. Controlled candidates were excluded from selection.

Selection was frozen before new test scoring: common MAE, then RMSE, then model/feature simplicity. A challenger also needed at least 1% improvement over naive and positive improvement on the non-overlapping subset. These are policy gates, not significance tests. None beat naive; the best regression, V2 Forest, has approximately 3.84% higher common MAE. No learned model was selected/refitted for final deployment.

| Selected strategy test set | Origins | Points | MAE | RMSE |
| --- | ---: | ---: | ---: | ---: |
| Supported origins | 24 | 168 | 33.160714 | 39.360740 |
| Common subset of the same predictions | 15 | 105 | 32.704762 | 37.928002 |

The test partition was evaluated in previous work; it is not a newly untouched holdout. Overlapping origins are correlated, with only five non-overlapping common validation origins. Final reservation/cancellation states are a retrospective proxy, not verified point-in-time operational data. Small training errors are not sufficient evidence of forecasting accuracy. These are demonstration results, not a production guarantee.

## DSS result and verification

For T=2017-08-31, the seven predictions are **213, 140, 164, 154, 105, 69, 98**, totaling **943**. Model/data versions are in the accepted-state table. The reference interval 2017-07-07…2017-08-31 contains 54/56 COMPLETE targets; July 15 and July 27 are PARTIAL. Forecast remains `ok`, every level is `INSUFFICIENT_HISTORY`, and all threshold measures are NULL.

Independent live SQL and Python checks found **zero COMPLETE 56-day windows out of 738**, maximum 54 COMPLETE dates per full window, and a longest COMPLETE run of 41 days. Real HIGH/NORMAL/LOW examples cannot be produced under this rule. Labeled synthetic history of 28 tens and 28 thirties supplies mean=20/std=10 and tests both strict boundaries, HIGH/NORMAL/LOW, zero variance and nonnegative lower thresholds.

Core release verification passed 84 tests and all 57 live quality checks. Saved metrics independently reconcile 40 score sets over 4,970 prediction records; all 20 bundles reload. Protected artifacts/backend/frontend hashes remained unchanged. No accepted-model training or database writes were needed for DSS. HTTP/browser integration and another-machine reproduction remain the Phase 3 owner's work.

## Optional research reproduction

Run from the full repository with Python 3.12.9, `ml/requirements.txt` and `ml/requirements-dev.txt`. The default handoff needs only `requirements-serving.txt`.

```powershell
# Check accepted metrics and bundle reload without training:
python scripts/verify_demand_metrics.py --run-dir artifacts/metrics/demand_feature_versions_20261105

# Reproduce experiments only when needed, using a new output directory:
python scripts/compare_demand_features.py --snapshot artifacts/metrics/demand_feature_versions_20261105/snapshot.json --output-dir artifacts/metrics/demand_versions_reproduction

# Full regression tests; output stays in an ignored disposable workspace:
python -m pytest -q tests/ml -p no:cacheprovider --basetemp artifacts/tests/tmp_demand_checks

# Explicitly opt into a complete research package:
python scripts/package_demand_handoff.py --profile research --output artifacts/handoff/demand-research.zip
```

The full run preserves frozen dates/configuration, features, predictions, metrics, controlled fits and five PNG/SVG charts. Research packages include that evidence; serving packages contain only accepted runtime inputs. Neither includes raw data or credentials. Live checks additionally require the full repository's established warehouse/source configuration; this local restoration uses `artifacts/recovery/phase4_recreate_20261104/dw_config.json`, which pins verified archived weather. It is not a portable assumption about another member's database.

## Consolidation decisions

The previous ten guides repeated contracts, setup, results and session history, and the 133-file handoff bundled every experiment with serving. Current documentation has one required guide and this optional report, with schema/examples as references. Historical notes and scratch outputs are moved to the ignored local archive; accepted run paths and bytes remain unchanged. The default package uses canonical `runtime/model`, `runtime/snapshot.json` and `runtime/verification.json` paths and omits training code, losing models and logs. Existing forecasting modules were not merged or refactored merely to reduce file counts: each has a different runtime, training or evidence responsibility, and the tested inference contract is preserved.
