# Pipeline rebuild — 2026-11-10

**PASS: Raw → Staging → DW → Operations Mart is published and verified.**

The checkout's ignored `.env` selects PostgreSQL database `hotel_dwdss_rebuild_20261110` on localhost:5432, using the separate login `hotel_rebuild_20261110`. The existing PostgreSQL 17.11 volume was inspected and preserved; `hotel_dwdss` publication IDs, timestamps and row counts are unchanged. See [preservation evidence](../artifacts/recovery/pipeline_20261110/preserved_database_verification.json). Dependencies already matched the required versions: Python 3.12.9, psycopg 3.3.6, holidays 0.106 and pytest 9.0.3.

| Layer | Records |
|---|---:|
| Booking raw | 119,390 |
| Staging City Booking | 79,330 |
| Resort out of scope | 40,060 |
| Staging Holiday | 38 (35 national, 3 Lisboa) |
| Staging Weather | 793 |
| DW fact_booking | 79,250 |
| DW booking_rejection | 80, under the existing cleaning rules |
| DW calendar / daily context / daily quality | 800 each, including seven future dates |
| Mart daily_hotel_operations | 793 |
| Mart daily_hotel_operations_by_country | 131,638 |

Guest data status: **713 COMPLETE / 80 PARTIAL**. All 80 partial-day targets remain NULL; five valid zero-target days remain zero. Weather and Holiday context are COMPLETE on all 793 historical dates (2015-07-01–2017-08-31). The PT/Lisboa calendar covers 2015–2017; 26 holiday dates fall inside the historical Mart range. Seven subsequent DW calendar dates retain UNKNOWN Booking/Weather coverage.

Staging has zero structural rejects. Four missing children values remain NULL in DW; 74,140 fact rows retain valid zero children. All 79,330 Staging bookings retain raw booking-level fields for EDA/OTB. Joining facts to their source rows and daily context yields exactly 79,250 distinct source keys, without missing lineage or duplicate joins. No target imputation or business-rule changes were made.

## Published versions

- Staging batch: `8c928f28-f4f8-49a1-8cda-a315badb01da`
- Source-set fingerprint: `bd5373c46ae9fe55a26c50bef116b69cf9d38e09c6957982d4f6d37ebb1daa36`
- DW/Mart run_id: `3ab8540b-3874-4162-b775-bbc2ad01b2b3`
- data_version: `9963548d-c0fc-44b4-92dc-55f139447ea7`
- Staging contract: `staging-v1.1`; DW config: `dw-inputs-v3-20261110`; coverage: `selected-coverage-v3-20261110`

## Sources and SHA-256

| Source | Local raw path | SHA-256 |
|---|---|---|
| [Kaggle Booking v5](https://www.kaggle.com/datasets/mathsian/hotel-bookings) | `data/raw/booking/mathsian_hotel-bookings_20261110/hotel_bookings.csv` | `7c2ae42a7353905ea136e5c2287f17c92c5435826598bfbb8491c6f0c7b1fc06` |
| [python-holidays 0.106](https://holidays.readthedocs.io/en/main/auto_gen_docs/portugal/) | `data/raw/holiday/pt_lisboa_holidays_2015_2017_20261110.csv` | `0ee97e00fc4cbb89361454fd9b9e84ef363b29780e40be3cd0ecafaaa7378428` |
| [Open-Meteo ERA5](https://open-meteo.com/en/docs/historical-weather-api) | `data/raw/weather/open_meteo_lisbon_era5_2015-07-01_2017-08-31_20261110.json` | `fccc24f4ba84849005154e31aee6ff7b307ce0d2a8f6556ae44c1e1f28f3339a` |

Raw acquisition timestamps, versions, requests and metadata checksums are retained alongside the files and in [source verification](../artifacts/recovery/pipeline_20261110/source_verification.json). Raw files and credentials remain ignored by Git.

Booking CSV/archive and Holiday CSV reproduce their pinned bytes exactly. Weather differs from the previous selected checksum `741efa5393acb0c0df3c434051bdeb4b11fe2c9fdaebe6ea19da1954ca5be2c3`. Validation established the exact 793-day sequence, aligned arrays, finite temperature, nonnegative finite precipitation and matching coordinates/model/timezone/units. Against the preserved **October 17** snapshot, all precipitation matches and 334 temperatures differ by −0.2°C to +0.3°C. The October 27 raw file is unavailable for a full comparison; the upstream cause of temperature changes is undetermined. This is a new validated acquisition, with no claim of value equivalence. Details and provenance: [source manifest](../docs/data_dictionary/source_manifest_20261110.md).

The source selection and checksum-bound coverage were updated together after verification; previous configurations remain in the recovery directory. Booking completeness retains the existing accepted assumption for the unchanged Booking checksum. Holiday retains the existing replay evidence. New Weather coverage pins the new verification evidence. `.gitattributes` preserves the bytes of checksum-bound configuration/evidence across checkouts.

## Executed commands and checks

All commands ran from the repository root. Initial sandbox denials for Docker/network access were retried with approval; no pipeline gate was bypassed.

| Command | Result |
|---|---|
| `docker compose ps --all`, volume/container inspection and read-only SQL | PASS; existing published database identified |
| `python -m pip show psycopg holidays pytest` | PASS; required versions installed |
| `python pipeline/ingestion/download_booking.py --run-id 20261110` | PASS |
| `python pipeline/ingestion/generate_holidays.py --start-year 2015 --end-year 2017 --run-id 20261110` | PASS |
| `python pipeline/ingestion/fetch_weather.py --start-date 2015-07-01 --end-date 2017-08-31 --run-id 20261110` | PASS |
| Independent source validation and pinned config validation | PASS |
| `docker compose up -d db` | PASS; preserved volume |
| Local isolated role/database creation | PASS; existing database preserved |
| `python scripts/setup_db.py --report artifacts/recovery/pipeline_20261110/staging_migration.json` | PASS |
| `python scripts/run_pipeline.py --to staging --report artifacts/recovery/pipeline_20261110/staging_first_load.json` | PASS; published |
| `python pipeline/quality/staging_checks.py --report artifacts/recovery/pipeline_20261110/staging_quality.json` | PASS |
| `python scripts/run_pipeline.py --to staging --report artifacts/recovery/pipeline_20261110/staging_rerun.json` | PASS; no-op |
| `python scripts/run_pipeline.py --to dw --with-mart --with-tests --output-dir artifacts/recovery/pipeline_20261110/dw` | PASS; all seven steps exit 0 |
| `python artifacts/recovery/pipeline_20261110/verify_readiness.py` | PASS; all ten handoff checks |
| Original database publication/count comparison | PASS; unchanged |
| `git diff --check` | PASS |

The DW runner passed preflight, DW migration, Mart migration, load, independent DW/Mart quality, rerun and tests. Rerun is `no-op` with the same run_id, data_version and counts. **321 tests passed in 95.49 seconds**, covering Staging, DW, Mart, reconciliation, reporting views and OLAP fixtures on PostgreSQL. Tests used their own disposable databases.

Evidence: [workflow summary](../artifacts/recovery/pipeline_20261110/dw/summary.json), [quality report](../artifacts/recovery/pipeline_20261110/dw/quality_report.json), [pytest XML](../artifacts/recovery/pipeline_20261110/dw/pytest.xml), [readiness audit](../artifacts/recovery/pipeline_20261110/readiness.json).

No notebooks, ML, frontend or backend files were changed. No commit or push was made. The published data is ready for subsequent EDA and baseline forecasting; those workloads were outside this rebuild.
