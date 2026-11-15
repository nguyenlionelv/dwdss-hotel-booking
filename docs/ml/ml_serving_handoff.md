# ML serving handoff

The three current-branch notebook protocols have been extracted into reusable Python modules, reproduced on the rebuilt published data, and connected to daily/monthly FastAPI inference. The React DSS page uses the trained registry and propagates production API failures.

## Notebook → model mapping

| Source notebook under `notebooks/experiments/` | Implementation | Served model IDs | Selected algorithm |
|---|---|---|---|
| `history_demand_imputed_3fold_report.ipynb` | `ml/demand_forecast/imputed.py` | `imputed_canonical_history`, `imputed_imputed_history` | `B4_weekday`, separately selected for both policies |
| `history_demand_causal_methods_report.ipynb` | `ml/demand_forecast/causal.py` | `causal_causal_history` | `B4_matched` |
| `monthly_demand_forecast_report.ipynb` | `ml/demand_forecast/monthly.py` | `monthly_last_month_rate` | `M0_last_month_rate` |

Extracted definitions use instance-scoped daily/booking data. They retain the notebooks' room imputation, residual calibration, features, estimator configurations, inner searches, metrics and 1% simplicity selection rules. Notebook files are unchanged. The causal search used six tree workers; its statistical configuration and seeds are unchanged. Serial/parallel parity is tested to absolute tolerance `1e-12`; the recorded diagnostic maximum difference was `1.1e-16`.

The daily default is the causal protocol because it explicitly assumes a one-day reporting delay. This is an operational default, not a ranking against the delay-zero protocol. Each algorithm was selected within its own validation protocol; holdout did not select models.

## Data, labels and provenance

- Published database: `hotel_dwdss_rebuild_20261110`, selected by the existing ignored `.env`.
- `data_version`: `9963548d-c0fc-44b4-92dc-55f139447ea7`.
- DW/Mart run: `3ab8540b-3874-4162-b775-bbc2ad01b2b3`.
- Immutable ML snapshot: `artifacts/ml_serving/snapshot/`, with `input_manifest.json`, `provenance.json`, `quality.json`, 793 daily rows and 79,250 fact bookings.
- Export runs independent DW/Mart quality checks, verifies matching publication versions, verifies the selected raw sources, and joins raw reserved-room types by source row ordinal. Loading checks snapshot hashes, versions, canonical status/NULL consistency, unique booking lineage and daily reconciliation.
- Source SHA-256 values and acquisition evidence remain in [the source recovery manifest](../data_dictionary/source_manifest_20261110.md). Booking SHA-256 is `7c2ae42a7353905ea136e5c2287f17c92c5435826598bfbb8491c6f0c7b1fc06`.

Canonical history retains 713 COMPLETE and 80 PARTIAL dates. COMPLETE zeros are preserved; PARTIAL canonical targets remain NULL. Estimated labels add only eligible missing guest bookings to observed subtotals, using room means with at least 30 valid train bookings and a train-global fallback. Causal history uses room/global means strictly before the historical day. Estimated labels are not verified ground truth.

The target is final non-canceled reservation guests by arrival date. It is not occupancy, verified check-in, stay nights or departures. Final reservation states and assumed publication delays do not establish historical point-in-time availability.

## Reproduced validation and holdout results

Daily development is July 2015–May 2017. Three expanding TimeSeriesSplit folds end training on 2015-12-23, 2016-06-15 and 2016-12-07; causal label cutoffs are one day earlier. All seven horizons are scheduled at every eligible origin. Selection uses equal-fold ALL_ESTIMATED MAE with the original 1% simplicity rule. Holdout is June–August 2017; its daily calibration cutoff is May 31 for delay zero and May 30 for delay one.

Monthly validation consists of 11 rolling one-month origins, July 2016–May 2017, following 12 initial training months. June–August 2017 is a separate rolling holdout, refitting room means at each origin. Months must contain every calendar day and have no unresolved estimated daily labels.

| Protocol / history policy | Validation MAE | Holdout MAE | Holdout RMSE | Units |
|---|---:|---:|---:|---|
| Imputed notebook / canonical_history | 30.747332 | 24.548745 | 32.634872 | guests/daily prediction |
| Imputed notebook / imputed_history | 30.725957 | 24.896427 | 32.915186 | guests/daily prediction |
| Causal notebook / causal_history | 30.915220 | 24.963669 | 32.979544 | guests/daily prediction |
| Monthly / room-type estimates | 438.068852 | 288.164643 | 325.450691 | guests/month |

These are newly computed ALL_ESTIMATED results. COMPLETE_ONLY and IMPUTED_ONLY daily metrics and per-horizon results are saved separately in `artifacts/ml_serving/models/*_metrics.csv` and `*_horizon.csv`. Daily validation values are equal-fold means. Daily and monthly MAE have different units; different daily availability protocols must not be treated as an identical-information leaderboard. Historical notebook holdout was already explored, so these remain retrospective results.

## Artifacts and inference

`artifacts/ml_serving/models/registry.json` pins metadata for four actual saved artifacts. Each model directory contains `metadata.json` and a checksum-verified `state.joblib`. Metadata records model ID/version, data version, calibration cutoff, imputation policy, label definition, validation metrics, feature schema, availability assumptions, notebook hash, input-manifest hash, environment and benchmark evidence. State contains fitted calibration and room means; monthly state contains predictions fitted offline at each saved origin.

Serving requires the artifact data version to match the active published DW/Mart. It verifies the artifact and snapshot checksums; incompatible or absent artifacts return 503. Model names without an available artifact return 422. Requests do not execute notebooks, fit imputers, select models or retrain.

Daily requests must follow calibration and validation-selection availability. Current serving origins start May 31, 2017 for the imputed protocol and June 1 for causal, and end August 31, 2017. Predictions cover T+1…T+h; causal features and thresholds stop at T−1. Monthly serving accepts saved month-end origins May 31–August 31, 2017; earlier validation-origin calculations are evaluation evidence, not deployable forecasts.

The snapshot CSVs and fitted binaries are local ignored outputs. Keep metadata/evidence with them when transferring artifacts, or regenerate using offline training. `DWDSS_MODEL_DIR` and `DWDSS_SNAPSHOT_DIR` override serving paths; Docker sets container-local paths. Only trusted local model artifacts should be loaded.

## API contracts and frontend compatibility

The pre-implementation map is [api_contract_mapping.md](api_contract_mapping.md).

| Endpoint | Parameters / response |
|---|---|
| `GET /api/dss/models` | Lists verified saved artifacts, IDs, labels, kind, default, versions, protocol and delay. The UI filters `kind=daily`. |
| `GET /api/dss/demand-forecast` | `as_of_date=2017-08-31` (default; forecasts 1-7 September), optional registry `model_name`, `horizon=1..7` (default 7). Typed hotel/version/time, model metadata, thresholds, summary, forecast rows, canonical history and within-protocol benchmark comparisons. |
| `GET /api/dss/monthly-demand-forecast` | Month-end `as_of_date` (default `2017-08-31`), optional monthly registry `model_name`. Typed `kind=monthly`, next `forecast_month`, `horizon_months=1`, `units=guests/month`, prediction and metadata. |

The legacy summary field `total_predicted_guests_7d` sums the requested horizon; `horizon` explicitly identifies shorter requests. Predictions retain real precision; display rounding is separate. Actuals after T are canonical values for explicit backtest display only and never enter prediction features. Room-night predictions remain NULL.

DSS classification is separate from forecasting. Its 56-calendar-day window ends at the latest label available under the chosen delay. It requires all 56 dates to be COMPLETE and uses population standard deviation (`ddof=0`), HIGH at μ+σ, LOW at max(0, μ−σ), with HIGH tested first at an equal boundary. Otherwise thresholds are NULL and every row is INSUFFICIENT_HISTORY. Actions use only the documented fixed text. At the backtest causal cutoff `2017-08-24` there are **53 COMPLETE days**, so classification is correctly unavailable.

The UI now loads registry choices, removes untrained legacy model claims, and displays errors instead of silently returning fabricated forecasts. Mock data is restricted to explicit labeled Demo Mode. Stay-night controls are disabled, unsupported values remain unavailable, and canonical NULLs render as gaps. The fixed μ±σ rule and strict 56-day requirement replace the previous adjustable/28-day behavior. Benchmark rows include availability flags; evaluated algorithms without serving artifacts are not selectable. The existing visual layout is retained.

## Commands and verification

From the repository root, with PostgreSQL running and the local `.env` configured:

```powershell
python -m pip install -r backend/requirements.txt
python scripts/train_models.py --export --tree-jobs 6
# After an interrupted training protocol, retain and verify completed artifacts:
python scripts/train_models.py --resume --tree-jobs 6

python -m ml.demand_forecast.predict --data-version 9963548d-c0fc-44b4-92dc-55f139447ea7 --cutoff 2017-08-31
python -m ml.demand_forecast.predict --data-version 9963548d-c0fc-44b4-92dc-55f139447ea7 --cutoff 2017-08-31 --kind monthly
python -m ml.demand_forecast.evaluate
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

$env:DWDSS_INTEGRATION='1'
$env:PYTHONPATH='.;tests/warehouse;tests/pipeline'
python -m pytest -q tests/ml tests/backend -p no:cacheprovider --basetemp artifacts/tests/tmp_dss_verify
python scripts/verify_dss_client.py
npm --prefix frontend run build
```

For a fresh reproduction after an existing successful run, choose new `--snapshot` and `--output` directories. Existing snapshot/artifact output directories are protected; successful `--resume` verifies and reuses the completed run. Export is read-only and does not alter canonical Mart rules.

Executed validation:

- **22 Python tests PASS**, including original-notebook numerical oracles, future poisoning, train-only preprocessing, serial/parallel forest parity, date/horizon alignment, artifact/version failures, typed responses, real published Mart → inference → FastAPI, and backend regressions. [Final pytest evidence](../../artifacts/ml_serving/pytest_final.xml). An initial backend collection attempt required the existing fixture import directories on PYTHONPATH; the final configured run passed.
- **4 frontend-client tests PASS**, including actual localhost HTTP through the real client, explicit demo labeling, production error propagation and preserved NULL/zero values. [HTTP verification](../../artifacts/ml_serving/frontend_client_verification.json), [test output](../../artifacts/ml_serving/frontend_client_tests.log). The temporary server was stopped after testing.
- **Production Vite build PASS**. Frontend dependencies were installed from the existing lockfile.
- Real response examples: [daily](../../artifacts/ml_serving/daily_api_response.json), [monthly](../../artifacts/ml_serving/monthly_api_response.json). Live horizons 1, 3 and 7 were executed and their summary totals reconciled.
- Completed-artifact resume and both daily/monthly CLI prediction commands PASS. September 2017 monthly prediction: **4,193.225806 guests**, with no verified actual available.

No browser interaction E2E or Docker image rebuild is claimed. Docker packaging was updated for ML modules, dependencies and the generated local artifacts. No OTB models, obsolete ML branch/PR, canonical Mart changes, commits or pushes were used.
