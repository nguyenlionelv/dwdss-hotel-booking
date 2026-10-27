# Source profiling and integration validation

Generated at: `2026-10-17T07:04:10.314911+00:00`

## Booking source

- Rows: **119,390**; source columns: **32**.
- Hotel distribution: City Hotel **79,330**, Resort Hotel **40,060**.
- Arrival-date range: **2015-07-01 → 2017-08-31**.
- Identical attribute rows after the first: **31,994**. These are not auto-deleted.
- City Hotel rows expected in Staging: **79,330**. Missing/invalid observations do not subtract rows.
- Out-of-scope hotel rows: **40,060**; unidentified hotel rows: **0**.
- Missing `children`: **4**; zero total guests: **167** (quality observation, not automatic exclusion).
- Arrival week-number rows differing from ISO week: **42,689**.
- Negative City Hotel ADR rows: **0**; this is profiled, not silently removed.

## Holiday and weather

- Holiday rows: **38** (35 national, 3 Lisboa-specific); duplicate date/scope/name keys: **0**.
- Weather rows: **793**, covering **2015-07-01 → 2017-08-31**; duplicate dates: **0**.
- Weather missing days in City Hotel range: **0**.

## Join validation

- City rows before/after join: **79,330 / 79,330**.
- Context rows / expected days: **793 / 793**.
- Duplicate context dates: **0**.
- Booking rows without calendar context: **0**.
- Holiday dates in booking range: **26**.

Historical ERA5 weather is suitable for descriptive association analysis after this join check. It is not evidence that future weather was available at a forecast cutoff, and the join does not establish causality.
