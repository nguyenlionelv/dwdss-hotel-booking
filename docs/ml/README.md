# Demand forecasting: start here

**This is the only guide the integrating member needs to read.** [REPORT.md](REPORT.md) is optional project-report material. The [JSON schema](demand_dss_response.schema.json) and [official](examples/demand_dss_real.json) / [synthetic](examples/demand_dss_synthetic.json) responses are reference files.

Implemented: accepted Seasonal Naive inference, strict 56-day DSS rules, and a callable service. Remaining: Phase 3 owns FastAPI registration, frontend wiring and end-to-end verification. Guest Mix and Cancellation Prediction are outside scope.

## 1. Receive one small package and run it

Receive **`demand-serving.zip`** and extract it into a new folder. With Python 3.12.9, run the following from that folder; the first command checks the received ZIP before loading the model (`..\demand-serving.zip` assumes the ZIP is beside the extracted folder):

```powershell
python scripts/package_demand_handoff.py --verify ..\demand-serving.zip
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ml/requirements-serving.txt
.\.venv\Scripts\python.exe scripts/forecast_dss.py --as-of-date 2017-08-31 --bundle runtime/model --snapshot runtime/snapshot.json
```

The package contains the accepted model, one validated snapshot, runtime code and response references. It has no challenger models, training outputs, recovery logs or test scratch files. A Git clone supplies source code but not these ignored model/data artifacts.

Expected seven guest predictions: **213, 140, 164, 154, 105, 69, 98**; total **943**, peak **213 on 2017-09-01**. Forecast status is `ok`; DSS is `INSUFFICIENT_HISTORY`, with 54/56 COMPLETE reference days and NULL thresholds. This is the correct official result, not an integration failure.

## 2. Call one service from the backend

```python
from ml.demand_forecast.data import load_snapshot
from ml.demand_forecast.service import DemandForecastService

# Application setup: load the trusted model and pinned demonstration snapshot once.
snapshot = load_snapshot("runtime/snapshot.json")
service = DemandForecastService.from_bundle("runtime/model", lambda: snapshot)

# A normal synchronous FastAPI handler can return this dict directly.
payload = service.forecast("2017-08-31", model_name="seasonal_naive")
```

`service.forecast(as_of_date, *, model_name=None) -> dict` performs inference and DSS classification without training. Model and source-data versions must match. The packaged snapshot is a reproducible historical demonstration. Live operation requires the full repository and a provider calling `extract_snapshot(dw_config=...)` against a compatible, quality-checked Mart; changing the provider does not retrain the model.

Canonical endpoint to implement: **`GET /api/dss/demand-forecast?as_of_date=YYYY-MM-DD&model_name=seasonal_naive`**. Horizon is fixed at seven. Use a synchronous handler or a threadpool. The endpoint is not registered by this ML code.

## 3. Align the existing client

| Existing client | Use this contract |
| --- | --- |
| `/api/dss/operations/demand-forecast`, `cutoff_date` | `/api/dss/demand-forecast`, `as_of_date` |
| `forecast_rows`, `stay_date`, `predicted_arrivals` | `forecasts`, `forecast_date`, `predicted_guest_count` |
| `summary_kpis` and one peak date | `summary.total_predicted_guests_7d`, `peak_predicted_guest_count`, `peak_forecast_dates` |
| Rounded/local threshold logic and multiplier slider | Server `dss_threshold_rule` and row `demand_level`; fixed multiplier=1 |
| Mock fallback and hardcoded model/metric defaults | Explicit error/unavailable states; actual model/data versions |

The model predicts a **non-canceled guest-arrival proxy**, not booking counts, occupancy, room nights or required staff. Remove unsupported room/staffing/future-weather claims. Preserve zeros, NULLs and tied peak dates. The response references and schema specify every field; do not introduce a second endpoint or duplicate aliases.

| `forecast_status` / `dss_status` | UI behavior |
| --- | --- |
| `ok` / `OK` | Seven rows with HIGH/NORMAL/LOW and numeric thresholds |
| `ok` / `INSUFFICIENT_HISTORY` | Keep seven predictions; show available/required history and NULL thresholds |
| `unavailable` / `FORECAST_UNAVAILABLE` | Empty forecast rows, NULL summary, explicit forecast reason |

DSS requires exactly T−55…T, all COMPLETE. It uses population mean/std, HIGH when prediction > mean+std, LOW when prediction < max(0,mean−std), and NORMAL at equality. Missing/PARTIAL days are never skipped or filled. Suggestions are qualitative.

Hard errors raise `DemandError(code, message)`: map invalid request/model/cutoff to 422, stale versions to 409, source/artifact/configuration failures to 503, and unexpected prediction failures to 500. These HTTP mappings belong in the Phase 3 adapter. Missing DSS history is a valid response, not a hard error or permission to return NORMAL.

Before declaring integration complete, verify the real response, synthetic HIGH/NORMAL/LOW and equality boundaries, stale-bundle/source failure handling, and the actual browser-to-endpoint flow. No full-stack or another-machine verification has been claimed.

## Maintainer commands — repository only

Create the default serving package with `python scripts/package_demand_handoff.py --output artifacts/handoff/demand-serving.zip`. Choose a fresh output filename when regenerating. Source changes are still uncommitted; the package includes the needed current runtime code.

Research evidence is optional: add `--profile research` to build a full experiment package. Read [REPORT.md](REPORT.md) for experiment results, filtering and reproducibility. Training/report modules remain in the repository, but the integrating member does not need them to serve the accepted model.

Local historical notes, failed attempts and scratch outputs are preserved under `artifacts/local_archive/p4/`. They are not required reading or handoff inputs. The original accepted run and official DSS evidence retain their existing paths and contents.
