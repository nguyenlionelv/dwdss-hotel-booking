"""Load only City Hotel records, preserving full-file CSV ordinals and raw tokens."""

from __future__ import annotations

import csv
from calendar import month_name
from datetime import date
from pathlib import Path

from psycopg.types.json import Jsonb

from .common import LoadResult, RecordParser, StructuralError


BOOKING_FIELDS = [
    "hotel", "is_canceled", "lead_time", "arrival_date_year", "arrival_date_month",
    "arrival_date_week_number", "arrival_date_day_of_month", "stays_in_weekend_nights",
    "stays_in_week_nights", "adults", "children", "babies", "meal", "country",
    "market_segment", "distribution_channel", "is_repeated_guest", "previous_cancellations",
    "previous_bookings_not_canceled", "reserved_room_type", "assigned_room_type",
    "booking_changes", "deposit_type", "agent", "company", "days_in_waiting_list",
    "customer_type", "adr", "required_car_parking_spaces", "total_of_special_requests",
    "reservation_status", "reservation_status_date",
]

INSERT_COLUMNS = [
    "_source_file", "_source_file_sha256", "_source_row_id", "_batch_id", "raw_record",
    *BOOKING_FIELDS, "arrival_date",
]
INSERT_SQL = (
    "INSERT INTO staging.stg_booking (" + ",".join(INSERT_COLUMNS) + ") VALUES ("
    + ",".join(["%s"] * len(INSERT_COLUMNS)) + ") ON CONFLICT DO NOTHING"
)
MONTH_NUMBERS = {name.lower(): number for number, name in enumerate(month_name) if name}
NONNEGATIVE_INTS = {
    "lead_time", "stays_in_weekend_nights", "stays_in_week_nights", "previous_cancellations",
    "previous_bookings_not_canceled", "booking_changes", "days_in_waiting_list",
    "required_car_parking_spaces", "total_of_special_requests",
}
INTEGER_FIELDS = NONNEGATIVE_INTS | {
    "is_canceled", "arrival_date_year", "arrival_date_week_number", "arrival_date_day_of_month",
    "is_repeated_guest",
}
GUEST_FIELDS = {"adults", "children", "babies"}
SPECIAL_MISSING = {
    "children": {"", "NA"}, "country": {"", "NULL"},
    "agent": {"", "NULL"}, "company": {"", "NULL"},
}


def load(cur, spec: dict, batch_id) -> LoadResult:
    result = LoadResult()
    path: Path = spec["resolved_path"]
    sha = spec["sha256"]
    source_file = spec["file"]
    pending = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            if reader.fieldnames is None or set(reader.fieldnames) != set(BOOKING_FIELDS) or len(reader.fieldnames) != 32:
                raise StructuralError("booking", "header", "Booking CSV must contain exactly the contracted 32 fields", str(reader.fieldnames))
            for row_id, raw in enumerate(reader, start=2):
                result.raw_count += 1
                if None in raw or any(value is None for value in raw.values()):
                    raise StructuralError("booking", f"record {row_id}", "Malformed CSV field count", str(raw))
                hotel = raw["hotel"]
                if hotel == "Resort Hotel":
                    result.out_of_scope_count += 1
                    continue
                if hotel != "City Hotel":
                    result.unidentified_count += 1
                    continue
                parser = RecordParser("booking", sha, row_id, raw, result, batch_id)
                typed = {}
                for field in BOOKING_FIELDS:
                    if field in INTEGER_FIELDS:
                        typed[field] = parser.value(field, "integer", nonnegative=field in NONNEGATIVE_INTS)
                    elif field in GUEST_FIELDS:
                        typed[field] = parser.value(field, "numeric", missing_tokens=SPECIAL_MISSING.get(field),
                                                    nonnegative=True, guest=True)
                    elif field == "adr":
                        typed[field] = parser.value(field, "numeric")
                    elif field == "reservation_status_date":
                        typed[field] = parser.value(field, "date")
                    else:
                        typed[field] = parser.value(field, missing_tokens=SPECIAL_MISSING.get(field))
                for flag in ("is_canceled", "is_repeated_guest"):
                    if typed[flag] is not None and typed[flag] not in (0, 1):
                        parser.issue(flag, "CANCEL_FLAG_DOMAIN" if flag == "is_canceled" else "REPEATED_GUEST_FLAG_DOMAIN",
                                     "invalid", raw[flag], "Flag must be 0 or 1")
                week = typed["arrival_date_week_number"]
                if week is not None and not 1 <= week <= 53:
                    parser.issue("arrival_date_week_number", "SOURCE_WEEK_DOMAIN", "invalid", raw["arrival_date_week_number"], "Week number must be 1..53")
                if typed["adr"] is not None and typed["adr"] < 0:
                    parser.issue("adr", "NEGATIVE_ADR", "invalid", raw["adr"], "ADR is negative")
                arrival_date = None
                year, day = typed["arrival_date_year"], typed["arrival_date_day_of_month"]
                month = typed["arrival_date_month"]
                if year is not None and day is not None and month is not None:
                    try:
                        arrival_date = date(year, MONTH_NUMBERS[month.lower()], day)
                    except (KeyError, ValueError, OverflowError):
                        parser.issue("arrival_date", "DATE_PARSE_FAILED", "invalid",
                                     f"{raw['arrival_date_year']}-{raw['arrival_date_month']}-{raw['arrival_date_day_of_month']}",
                                     "Arrival date is not a valid calendar date")
                guests = [typed[field] for field in ("adults", "children", "babies")]
                if all(value is not None for value in guests) and sum(guests) == 0:
                    parser.issue("adults,children,babies", "ZERO_GUESTS", "invalid", "0", "Guest total is zero", "warning")
                pending.append((source_file, sha, row_id, batch_id, Jsonb(raw),
                                *(typed[field] for field in BOOKING_FIELDS), arrival_date))
                result.staged_count += 1
                if len(pending) >= 1000:
                    cur.executemany(INSERT_SQL, pending)
                    pending.clear()
            if pending:
                cur.executemany(INSERT_SQL, pending)
    except (csv.Error, UnicodeError) as exc:
        raise StructuralError("booking", f"CSV line {getattr(reader, 'line_num', '?')}", str(exc)) from exc
    return result
