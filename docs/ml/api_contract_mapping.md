# DSS contract mapping (before implementation)

| Area | Existing state | Implementation contract |
|---|---|---|
| Daily endpoint | Documentation/client request `/api/dss/demand-forecast`; backend only has `/status` | GET with `as_of_date`, optional registry `model_name`, horizon 1–7 (default 7) |
| Models | UI advertises XGBoost, RF, Ridge, Seasonal Naive; no trained artifacts | Registry lists only saved, verified daily artifacts; notebook protocols remain separate |
| Daily origin | Documentation T+1…T+7 | Imputed protocol history ≤T; causal protocol history ≤T−1; reject origins before artifact training availability |
| Monthly | No endpoint; different label and units | Separate GET `/api/dss/monthly-demand-forecast`, month-end cutoff, next calendar month, guests/month |
| Model availability | Notebook selection is retrospective | Daily origins must follow calibration and validation-selection availability; monthly serving accepts saved origins May–August 2017, after selection, rather than exposing earlier validation-origin forecasts as deployable artifacts |
| Response | Documented hotel/cutoff/version/time, thresholds, summary, forecasts, canonical history, comparisons | Typed Pydantic schemas; metadata identifies data version, label estimates, reporting delay and metric protocol/population |
| Thresholds | Docs require all 56 COMPLETE days; UI accepts 28, adjustable k | Require 56 COMPLETE days within 56-calendar-day window ending at latest available label; population std, μ±σ; insufficient → NULL thresholds and explicit status |
| Errors/demo | Client silently fabricates mock predictions, stay nights and metrics on errors | Errors propagate; static mock only in explicit labeled Demo Mode |
| UI fields | Legacy aliases, hard-coded KPIs, weather Clear, fabricated stay nights | Use documented fields, registry choices, explicit unavailable values; keep visual layout |
| Comparison | Legacy model families, daily and monthly potentially conflated | Validation-only metrics with protocol and label population; separate monthly output, never rank across protocols |
| Provenance | Notebooks pin absent November 9 snapshots | Export immutable daily/fact input snapshot from current verified published Mart/DW and checksum-verified raw room types; retain quality and source checksums |

The three source notebooks are the current branch's imputed 3fold, causal methods and monthly `_report.ipynb` files. Expected winners B4_weekday, B4_matched and M0_last_month_rate must be checked by rerunning their respective validation selection rules. Holdout never selects a model. Final database reservation states support retrospective experiments; actual historical publication timestamps are not verified.
