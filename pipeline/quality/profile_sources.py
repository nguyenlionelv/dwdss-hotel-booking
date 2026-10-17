#!/usr/bin/env python3
"""Profile newly acquired sources and validate City Hotel context joins."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


GUEST_FIELDS = ["adults", "children", "babies"]
NIGHT_FIELDS = ["stays_in_weekend_nights", "stays_in_week_nights"]
REQUIRED_FIELDS = [
    "hotel",
    "is_canceled",
    "arrival_date_year",
    "arrival_date_month",
    "arrival_date_day_of_month",
    *GUEST_FIELDS,
    *NIGHT_FIELDS,
    "lead_time",
    "adr",
    "country",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scalar(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def choose_sample(merged: pd.DataFrame, name: str, mask: pd.Series) -> dict:
    matches = merged.loc[mask]
    if matches.empty:
        return {"sample_type": name, "status": "not_found"}
    row = matches.iloc[0]
    fields = [
        "_source_row_id",
        "hotel",
        "arrival_date",
        "day_name",
        "is_weekend",
        "is_holiday",
        "holiday_name",
        "temperature_2m_mean",
        "precipitation_sum",
        "is_canceled",
        "adults",
        "children",
        "babies",
    ]
    result = {"sample_type": name, "status": "found"}
    result.update({field: scalar(row.get(field)) for field in fields})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--booking", required=True, type=Path)
    parser.add_argument("--holiday", required=True, type=Path)
    parser.add_argument("--weather", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    booking_raw = pd.read_csv(args.booking, dtype=str, keep_default_na=False, low_memory=False)
    booking = booking_raw.copy()
    missing_columns = sorted(set(REQUIRED_FIELDS) - set(booking.columns))
    if missing_columns:
        raise ValueError(f"Booking source is missing required fields: {missing_columns}")
    # Missing tokens are field-specific; pandas' global NA vocabulary would erase evidence.
    missing_tokens = {"children": "NA", "country": "NULL", "agent": "NULL", "company": "NULL"}
    for column, token in missing_tokens.items():
        if column in booking:
            booking[column] = booking[column].replace({token: pd.NA, "": pd.NA})
    numeric_fields = GUEST_FIELDS + NIGHT_FIELDS + [
        "is_canceled", "lead_time", "adr", "arrival_date_year",
        "arrival_date_day_of_month", "arrival_date_week_number",
    ]
    parse_failures = {}
    for column in numeric_fields:
        raw = booking[column]
        missing = raw.isna() | raw.eq("")
        parsed = pd.to_numeric(raw, errors="coerce")
        parse_failures[column] = int((parsed.isna() & ~missing).sum())
        booking[column] = parsed
    booking.insert(0, "_source_row_id", range(2, len(booking) + 2))
    booking["arrival_date"] = pd.to_datetime(
        booking["arrival_date_year"].astype("Int64").astype(str)
        + "-"
        + booking["arrival_date_month"].astype(str)
        + "-"
        + booking["arrival_date_day_of_month"].astype("Int64").astype(str),
        format="%Y-%B-%d",
        errors="coerce",
    )
    city = booking.loc[booking["hotel"].eq("City Hotel")].copy()
    city["total_guests"] = city[GUEST_FIELDS].sum(axis=1, min_count=len(GUEST_FIELDS))
    city["total_stay_nights"] = city[NIGHT_FIELDS].sum(axis=1, min_count=len(NIGHT_FIELDS))

    negative_columns = GUEST_FIELDS + NIGHT_FIELDS + ["lead_time"]
    date_components = ["arrival_date_year", "arrival_date_month", "arrival_date_day_of_month"]
    missing_date_component = city[date_components].isna().any(axis=1) | city["arrival_date_month"].eq("")
    city_issue_masks = {
        "missing_arrival_date_component": missing_date_component,
        "invalid_arrival_date": city["arrival_date"].isna() & ~missing_date_component,
        "missing_children": city["children"].isna(),
        "missing_any_guest_component": city[GUEST_FIELDS].isna().any(axis=1),
        "negative_guest_or_night_or_lead_time": city[negative_columns].lt(0).any(axis=1),
        "zero_total_guests": city["total_guests"].eq(0),
        "invalid_cancellation_flag": city["is_canceled"].notna() & ~city["is_canceled"].isin([0, 1]),
    }

    iso_week = city["arrival_date"].dt.isocalendar().week.astype("Int64")
    week_mismatch = city["arrival_date_week_number"].astype("Int64").ne(iso_week) & city["arrival_date"].notna()
    null_counts = {column: int(value) for column, value in booking.isna().sum().items()}
    city_null_counts = {column: int(value) for column, value in city.isna().sum().items()}
    booking_profile = {
        "path": str(args.booking),
        "sha256": sha256(args.booking),
        "encoding": "UTF-8 compatible; read with field-specific missing tokens",
        "rows": int(len(booking)),
        "columns": int(len(booking.columns) - 2),
        "source_columns": [column for column in booking.columns if column not in {"_source_row_id", "arrival_date"}],
        "dtypes": {column: str(dtype) for column, dtype in booking.dtypes.items()},
        "null_counts": null_counts,
        "distinct_counts": {column: int(booking[column].nunique(dropna=True)) for column in booking.columns},
        "hotel_distribution": {str(key): int(value) for key, value in booking["hotel"].value_counts(dropna=False).items()},
        "out_of_scope_hotel_rows": int(booking["hotel"].eq("Resort Hotel").sum()),
        "unidentified_hotel_rows": int((~booking["hotel"].isin(["City Hotel", "Resort Hotel"])).sum()),
        "numeric_parse_failures": parse_failures,
        "field_missing_tokens": missing_tokens,
        "arrival_date_min": booking["arrival_date"].min().date().isoformat(),
        "arrival_date_max": booking["arrival_date"].max().date().isoformat(),
        "invalid_arrival_dates": int(booking["arrival_date"].isna().sum()),
        "identical_rows_after_first": int(booking.drop(columns=["_source_row_id", "arrival_date"]).duplicated().sum()),
        "rows_in_identical_groups": int(
            booking.drop(columns=["_source_row_id", "arrival_date"]).duplicated(keep=False).sum()
        ),
        "city": {
            "rows": int(len(city)),
            "null_counts": city_null_counts,
            "arrival_date_min": city["arrival_date"].min().date().isoformat(),
            "arrival_date_max": city["arrival_date"].max().date().isoformat(),
            "unique_arrival_dates": int(city["arrival_date"].nunique()),
            "issue_counts": {name: int(mask.sum()) for name, mask in city_issue_masks.items()},
            "staging_rows_expected": int(len(city)),
            "identical_rows_after_first": int(
                city.drop(columns=["_source_row_id", "arrival_date", "total_guests", "total_stay_nights"]).duplicated().sum()
            ),
            "arrival_week_number_mismatch_iso": int(week_mismatch.sum()),
            "adr_negative_rows": int(city["adr"].lt(0).sum()),
        },
        "duplicate_policy": "Report identical attributes but do not auto-delete; source has no reservation identifier.",
    }

    holiday = pd.read_csv(args.holiday, keep_default_na=False)
    holiday["date"] = pd.to_datetime(holiday["date"], errors="coerce")
    holiday_profile = {
        "path": str(args.holiday),
        "sha256": sha256(args.holiday),
        "rows": int(len(holiday)),
        "invalid_dates": int(holiday["date"].isna().sum()),
        "duplicate_date_scope_name": int(holiday.duplicated(["date", "scope", "holiday_name"]).sum()),
        "national_rows": int(holiday["scope"].eq("national").sum()),
        "lisboa_specific_rows": int(holiday["scope"].eq("Lisboa").sum()),
        "date_min": holiday["date"].min().date().isoformat(),
        "date_max": holiday["date"].max().date().isoformat(),
        "observed_values": sorted(holiday["observed"].astype(str).unique().tolist()),
    }

    weather_raw = json.loads(args.weather.read_text(encoding="utf-8"))
    daily = weather_raw["daily"]
    weather = pd.DataFrame(daily)
    weather["date"] = pd.to_datetime(weather.pop("time"), errors="coerce")
    weather_profile = {
        "path": str(args.weather),
        "sha256": sha256(args.weather),
        "rows": int(len(weather)),
        "date_min": weather["date"].min().date().isoformat(),
        "date_max": weather["date"].max().date().isoformat(),
        "duplicate_dates": int(weather["date"].duplicated().sum()),
        "missing_by_field": {column: int(value) for column, value in weather.isna().sum().items()},
        "latitude": weather_raw.get("latitude"),
        "longitude": weather_raw.get("longitude"),
        "timezone": weather_raw.get("timezone"),
        "units": weather_raw.get("daily_units"),
    }

    date_min = city["arrival_date"].min()
    date_max = city["arrival_date"].max()
    calendar = pd.DataFrame({"arrival_date": pd.date_range(date_min, date_max, freq="D")})
    calendar["day_name"] = calendar["arrival_date"].dt.day_name()
    calendar["is_weekend"] = calendar["arrival_date"].dt.dayofweek.ge(5)
    holiday_relevant = holiday.loc[holiday["date"].between(date_min, date_max)].copy()
    holiday_context = (
        holiday_relevant.groupby("date", as_index=False)
        .agg(holiday_name=("holiday_name", lambda values: " | ".join(sorted(set(values)))), holiday_scopes=("scope", lambda values: " | ".join(sorted(set(values)))))
        .rename(columns={"date": "arrival_date"})
    )
    calendar = calendar.merge(holiday_context, on="arrival_date", how="left", validate="one_to_one")
    calendar["is_holiday"] = calendar["holiday_name"].notna()
    weather_context = weather.rename(columns={"date": "arrival_date"})
    context = calendar.merge(weather_context, on="arrival_date", how="left", validate="one_to_one")
    merged = city.merge(context, on="arrival_date", how="left", validate="many_to_one")
    integration = {
        "city_rows_before_join": int(len(city)),
        "city_rows_after_join": int(len(merged)),
        "row_count_preserved": bool(len(city) == len(merged)),
        "context_rows": int(len(context)),
        "expected_calendar_days": int((date_max - date_min).days + 1),
        "context_duplicate_dates": int(context["arrival_date"].duplicated().sum()),
        "weather_days_missing_in_range": int(context["temperature_2m_mean"].isna().sum()),
        "holiday_dates_in_range": int(context["is_holiday"].sum()),
        "booking_rows_without_context": int(merged["day_name"].isna().sum()),
        "weather_interpretation": "Historical observed/reanalysis context only; not assumed available at forecast cutoff.",
        "causality_note": "A valid date/location join supports observational analysis, not causal claims.",
    }

    rainy = merged["precipitation_sum"].gt(0)
    dry = merged["precipitation_sum"].eq(0)
    samples = [
        choose_sample(merged, "weekday_non_holiday", ~merged["is_weekend"] & ~merged["is_holiday"]),
        choose_sample(merged, "weekend_non_holiday", merged["is_weekend"] & ~merged["is_holiday"]),
        choose_sample(merged, "holiday_weekday", merged["is_holiday"] & ~merged["is_weekend"]),
        choose_sample(merged, "holiday_weekend", merged["is_holiday"] & merged["is_weekend"]),
        choose_sample(merged, "rainy_day", rainy),
        choose_sample(merged, "dry_day", dry),
    ]
    pd.DataFrame(samples).to_csv(args.output_dir / "sample_context_validation.csv", index=False)

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "booking": booking_profile,
        "holiday": holiday_profile,
        "weather": weather_profile,
        "integration": integration,
        "samples": samples,
    }
    (args.output_dir / "source_profile.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    city_summary = booking_profile["city"]
    report = f"""# Source profiling and integration validation

Generated at: `{result['generated_at_utc']}`

## Booking source

- Rows: **{booking_profile['rows']:,}**; source columns: **{booking_profile['columns']}**.
- Hotel distribution: City Hotel **{city_summary['rows']:,}**, Resort Hotel **{booking_profile['hotel_distribution'].get('Resort Hotel', 0):,}**.
- Arrival-date range: **{booking_profile['arrival_date_min']} → {booking_profile['arrival_date_max']}**.
- Identical attribute rows after the first: **{booking_profile['identical_rows_after_first']:,}**. These are not auto-deleted.
- City Hotel rows expected in Staging: **{city_summary['staging_rows_expected']:,}**. Missing/invalid observations do not subtract rows.
- Out-of-scope hotel rows: **{booking_profile['out_of_scope_hotel_rows']:,}**; unidentified hotel rows: **{booking_profile['unidentified_hotel_rows']:,}**.
- Missing `children`: **{city_summary['issue_counts']['missing_children']:,}**; zero total guests: **{city_summary['issue_counts']['zero_total_guests']:,}** (quality observation, not automatic exclusion).
- Arrival week-number rows differing from ISO week: **{city_summary['arrival_week_number_mismatch_iso']:,}**.
- Negative City Hotel ADR rows: **{city_summary['adr_negative_rows']:,}**; this is profiled, not silently removed.

## Holiday and weather

- Holiday rows: **{holiday_profile['rows']:,}** ({holiday_profile['national_rows']} national, {holiday_profile['lisboa_specific_rows']} Lisboa-specific); duplicate date/scope/name keys: **{holiday_profile['duplicate_date_scope_name']}**.
- Weather rows: **{weather_profile['rows']:,}**, covering **{weather_profile['date_min']} → {weather_profile['date_max']}**; duplicate dates: **{weather_profile['duplicate_dates']}**.
- Weather missing days in City Hotel range: **{integration['weather_days_missing_in_range']}**.

## Join validation

- City rows before/after join: **{integration['city_rows_before_join']:,} / {integration['city_rows_after_join']:,}**.
- Context rows / expected days: **{integration['context_rows']} / {integration['expected_calendar_days']}**.
- Duplicate context dates: **{integration['context_duplicate_dates']}**.
- Booking rows without calendar context: **{integration['booking_rows_without_context']}**.
- Holiday dates in booking range: **{integration['holiday_dates_in_range']}**.

Historical ERA5 weather is suitable for descriptive association analysis after this join check. It is not evidence that future weather was available at a forecast cutoff, and the join does not establish causality.
"""
    (args.output_dir / "source_profile.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
