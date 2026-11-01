"""Aggregate Holiday/Weather to one context row per configured calendar day."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from .config import coverage_status


CONTEXT_COLUMNS = ("date_key", "dw_run_id", "is_holiday", "has_national_holiday", "has_lisboa_holiday",
    "holiday_names", "holiday_record_count", "holiday_data_status", "holiday_source_sha256", "temperature_mean",
    "precipitation", "temperature_status", "precipitation_status", "weather_record_count", "weather_ambiguous", "weather_source_sha256")


def combined_coverage(statuses: list[str]) -> str:
    if len(set(statuses)) == 1:
        return statuses[0]
    return "PARTIAL"


def context_issue(row: dict, source: str, field: str, code: str, kind: str, reason: str, day=None) -> dict:
    return {"source_id": source, "source_file_sha256": row["_source_file_sha256"],
            "source_row_id": row["_source_row_id"], "local_date": day, "field_name": field,
            "rule_code": code, "issue_type": kind, "severity": "warning", "disposition": "NULL_MEASURE",
            "raw_value": row["raw_record"].get(field) if field in row["raw_record"] else row["raw_record"], "reason": reason}


def source_date(row: dict, typed_field: str, raw_field: str) -> date | None:
    typed = row[typed_field]
    try:
        raw_day = date.fromisoformat(row["raw_record"][raw_field])
    except (TypeError, ValueError):
        return None
    return typed if type(typed) is date and typed == raw_day else None


def weather_value(row: dict, field: str, invalid: set[tuple]) -> tuple[Decimal | None, str]:
    value = row[field]
    raw = row["raw_record"].get(field)
    if (row["_source_row_id"], field) in invalid:
        return None, "INVALID"
    if raw is None or raw == "":
        return None, "MISSING"
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        return None, "INVALID"
    number = Decimal(value)
    try:
        original = Decimal(str(raw))
    except InvalidOperation:
        return None, "INVALID"
    if not number.is_finite() or not original.is_finite() or number != original:
        return None, "INVALID"
    if field == "precipitation_sum" and number < 0:
        return None, "INVALID"
    return number, "COMPLETE"


def build_context(calendar: list[dict], snapshot, coverage: dict) -> tuple[list[dict], list[dict]]:
    holidays = defaultdict(list)
    weather = defaultdict(list)
    tainted = {scope: set() for scope in ("national", "Lisboa")}
    unlocated = set()
    issues = []
    holiday_invalid = {i["source_row_id"] for i in snapshot.issues if i["source_id"] == "holiday" and i["issue_type"] == "invalid"}
    weather_invalid = {(i["source_row_id"], i["field"]) for i in snapshot.issues
                       if i["source_id"] == "weather" and i["issue_type"] == "invalid" and i["rule_code"] != "WEATHER_DUPLICATE_DATE"}
    for row in snapshot.holidays:
        day = source_date(row, "date", "date")
        scope = row["scope"]
        valid = (day is not None and row["country"] == "PT" and row["category"] == "public" and row["observed"] is False
                 and isinstance(row["holiday_name"], str) and bool(row["holiday_name"].strip())
                 and (scope == "national" and row["subdivision"] is None or scope == "Lisboa" and row["subdivision"] == "11")
                 and row["_source_row_id"] not in holiday_invalid)
        if valid:
            holidays[(day, scope)].append(row)
        else:
            scopes = [scope] if scope in tainted else list(tainted)
            for affected in scopes:
                if day is None:
                    unlocated.add(affected)
                else:
                    tainted[affected].add(day)
            issues.append(context_issue(row, "holiday", "date" if day is None else "holiday_name", "HOLIDAY_INVALID_RECORD",
                                        "invalid", "Invalid calendar row prevents certification of the affected scope/day", day))
    for row in snapshot.weather:
        day = source_date(row, "local_date", "time")
        if day is not None and (row["_source_row_id"], "time") not in weather_invalid:
            weather[day].append(row)
        else:
            issues.append(context_issue(row, "weather", "time", "WEATHER_INVALID_DATE", "invalid", "Weather entry cannot be assigned to a local day"))

    output = []
    for calendar_row in calendar:
        day = calendar_row["full_date"]
        flags, statuses, valid_holidays = {}, [], []
        for scope in ("national", "Lisboa"):
            entries = holidays[(day, scope)]
            valid_holidays.extend(entries)
            base = coverage_status(coverage, "holiday", scope, day)
            affected = scope in unlocated or day in tainted[scope]
            if entries:
                flags[scope] = True
            elif base == "COMPLETE" and not affected:
                flags[scope] = False
            else:
                flags[scope] = None
            statuses.append(("PARTIAL" if entries else "UNKNOWN") if affected else base)
        national, lisboa = flags["national"], flags["Lisboa"]
        combined = True if national is True or lisboa is True else False if national is False and lisboa is False else None
        entries = weather[day]
        temp, rain = None, None
        if len(entries) > 1:
            temperature_status = precipitation_status = "AMBIGUOUS"
            issues.append(context_issue(entries[1], "weather", "time", "WEATHER_AMBIGUOUS_DAY", "invalid",
                                        "Multiple entries; no measurement was selected", day))
        elif entries:
            row = entries[0]
            temp, temperature_status = weather_value(row, "temperature_2m_mean", weather_invalid)
            rain, precipitation_status = weather_value(row, "precipitation_sum", weather_invalid)
            for field, status in (("temperature_2m_mean", temperature_status), ("precipitation_sum", precipitation_status)):
                if status != "COMPLETE":
                    issues.append(context_issue(row, "weather", field, f"WEATHER_{status}_{field.upper()}", status.lower(),
                                                "Measurement is missing or invalid; preserve NULL", day))
        else:
            base = coverage_status(coverage, "weather", "all", day)
            temperature_status = precipitation_status = "MISSING" if base in ("COMPLETE", "MISSING") else "UNKNOWN"
        output.append({"date_key": calendar_row["date_key"], "is_holiday": combined,
            "has_national_holiday": national, "has_lisboa_holiday": lisboa,
            "holiday_names": sorted({r["holiday_name"].strip() for r in valid_holidays}),
            "holiday_record_count": len(valid_holidays), "holiday_data_status": combined_coverage(statuses),
            "holiday_source_sha256": snapshot.sources["holiday"]["source_file_sha256"],
            "temperature_mean": temp, "precipitation": rain, "temperature_status": temperature_status,
            "precipitation_status": precipitation_status, "weather_record_count": len(entries),
            "weather_ambiguous": len(entries) > 1, "weather_source_sha256": snapshot.sources["weather"]["source_file_sha256"]})
    return output, issues
