# Source selection — Weather refresh 2026-10-27

The user authorized using the newly downloaded Open-Meteo Weather file on 2026-10-27. The executable selection remains `operations_source_set.json`, so the existing Staging runbook and default loader entry point continue to apply.

Booking and Holiday retain their 2026-10-17 checksums. Holiday CSV was reproduced with python-holidays 0.106 and matched the selected checksum exactly; its original acquisition metadata content was recovered from `artifacts/staging/quality_report.json`. The old Weather metadata was also recovered for provenance, but the selected Weather input now uses its own new acquisition metadata.

| Item | Selected value |
|---|---|
| Weather file | `data/raw/weather/open_meteo_lisbon_era5_2015-07-01_2017-08-31_20261027.json` |
| Weather SHA-256 | `741efa5393acb0c0df3c434051bdeb4b11fe2c9fdaebe6ea19da1954ca5be2c3` |
| Acquisition metadata | `data/raw/weather/open_meteo_lisbon_era5_2015-07-01_2017-08-31_20261027.metadata.json` |
| Retrieved at UTC | `2026-10-27T02:03:21.293151+00:00` |
| Source/model | Open-Meteo Historical Weather API / ERA5 |
| Requested coordinate | Lisbon 38.72509, -9.1498 |
| Returned coordinate | 38.75, -9.25 |
| Timezone / units | Europe/Lisbon; temperature degrees Celsius, precipitation mm |
| Daily range | 2015-07-01 through 2017-08-31 inclusive, 793 entries |

Validation found aligned arrays, the exact continuous date sequence, no duplicate date, no missing/non-finite temperature or precipitation and no negative precipitation. Archived sample-date values match; full value equivalence to the old Weather file is not asserted because that original file is unavailable. Validation evidence is `artifacts/recovery/staging_20261027/weather_validation.json`.

The source checksum changes the source-set fingerprint. Contract version remains `staging-v1.1` because parsing, schema, scope and transformation rules are unchanged. The previous source selection is retained in `artifacts/recovery/staging_20261027/source_set_before_weather_refresh.json`; the 2026-10-17 source manifest and Staging evidence describe the old snapshot and do not certify a new local load. Save new load/quality/rerun/test evidence separately.
