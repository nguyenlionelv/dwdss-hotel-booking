"""Pure Booking transformation for D01-D08; no database, file writes or key allocation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Any
from uuid import UUID

from pipeline.source_to_staging.booking import MONTH_NUMBERS
from pipeline.source_to_staging.common import INTEGER_RE
from .config import mapped_value


TRANSFORM_VERSION = "booking-transform-v1"
INTEGER_MAX = 2147483647
GUEST_FIELDS = ("adults", "children", "babies")
NIGHT_FIELDS = ("stays_in_week_nights", "stays_in_weekend_nights")
DATE_FIELDS = ("arrival_date_year", "arrival_date_month", "arrival_date_day_of_month")
CATEGORICAL_FIELDS = {
    "country": "country", "distribution_channel": "channel", "market_segment": "market_segment",
    "customer_type": "customer_type", "reserved_room_type": "room_type", "assigned_room_type": "room_type",
}
VALUE_FIELDS = (*GUEST_FIELDS, *NIGHT_FIELDS, "lead_time", "adr", "is_canceled", "is_repeated_guest")
RAW_FIELDS = (*DATE_FIELDS, *VALUE_FIELDS, *CATEGORICAL_FIELDS)


@dataclass
class BookingTransformResult:
    """Exactly one fact candidate or rejection; loader later adds run ID and FK lookups."""

    fact: dict[str, Any] | None
    rejection: dict[str, Any] | None
    issues: list[dict[str, Any]]
    block_publish: bool = False


def checked_number(value: Any, *, integer: bool) -> tuple[int | Decimal | None, str | None]:
    """Validate typed Staging values before casting, preserving NUMERIC precision."""
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        return None, "Expected a typed integer or Decimal; binary floats are not accepted"
    number = Decimal(value)
    if not number.is_finite():
        return None, "Number must be finite"
    if number < 0:
        return None, "Number must be nonnegative"
    if integer:
        if number != number.to_integral_value():
            return None, "Number must be integral"
        if number > INTEGER_MAX:
            return None, "Number exceeds PostgreSQL INTEGER range"
        return int(number), None
    return number, None


def classify_party(adults: int | None, children: int | None, babies: int | None,
                   guest_eligible: bool) -> str:
    """Classify a reservation's composition without inferring personal relationships."""
    if not guest_eligible:
        return "UNKNOWN"
    if children > 0 or babies > 0:
        return "FAMILY"
    if adults == 1:
        return "SINGLE"
    if adults == 2:
        return "COUPLE"
    return "OTHER_GROUP"


def transform_booking(row: dict[str, Any], config: dict, mappings: dict,
                      staging_issues: list[dict] | tuple[dict, ...] = ()) -> BookingTransformResult:
    """Transform one complete Staging row and its same-source issues into DW candidates.

    Configuration/lineage defects raise ValueError. Unknown dates reject the source row
    and block publication. A valid date outside calendar is a build error, not rejection.
    """
    required = {"_source_file_sha256", "_source_row_id", "_batch_id", "raw_record", "hotel", "arrival_date", *RAW_FIELDS}
    missing = required - row.keys()
    if missing:
        raise ValueError(f"Incomplete Booking transform input: {sorted(missing)}")
    sha, row_id = row["_source_file_sha256"], row["_source_row_id"]
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise ValueError("Booking requires an unchanged lowercase source SHA-256")
    if isinstance(row_id, bool) or not isinstance(row_id, int) or not 2 <= row_id <= 9223372036854775807:
        raise ValueError("Booking source row ID must be the original CSV ordinal")
    try:
        first_batch = row["_batch_id"] if isinstance(row["_batch_id"], UUID) else UUID(row["_batch_id"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Booking requires a valid source first-batch UUID") from exc
    if row["hotel"] != "City Hotel" or row.get("_source_id", "booking") != "booking":
        raise ValueError("Transformer expects Booking City Hotel rows already selected by Staging")
    raw = row["raw_record"]
    if not isinstance(raw, dict) or set(RAW_FIELDS) - raw.keys():
        raise ValueError("Booking raw_record must retain all transform input fields")
    if any(value is not None and not isinstance(value, str) for field, value in raw.items() if field in RAW_FIELDS):
        raise ValueError("Booking CSV raw tokens must remain strings or null")
    if config["room_namespace"] != "shared_anonymized_source_codes":
        raise ValueError("Room comparison requires the verified shared namespace")
    for name in set(CATEGORICAL_FIELDS.values()):
        unknown = "UNK" if name == "country" else "UNKNOWN"
        if name not in mappings or unknown not in mappings[name]:
            raise ValueError(f"Missing validated mapping/unknown member: {name}")
    calendar_start = date.fromisoformat(config["calendar"]["start"])
    calendar_end = date.fromisoformat(config["calendar"]["end"])
    if calendar_start > calendar_end:
        raise ValueError("Invalid calendar interval")
    invalid_fields: dict[str, list[str]] = {}
    for issue in staging_issues:
        if (issue["source_id"] != "booking" or issue["source_file_sha256"] != sha or issue["source_row_id"] != row_id):
            raise ValueError("Staging issue does not belong to this Booking source key")
        # ZERO_GUESTS is a row warning, not a reason to null three valid zero components.
        if issue["issue_type"] == "invalid" and issue["rule_code"] != "ZERO_GUESTS":
            invalid_fields.setdefault(issue["field"], []).append(issue["rule_code"])

    issues: list[dict] = []
    arrival_date = None

    def add_issue(field: str, code: str, kind: str, disposition: str, reason: str,
                  *, severity: str = "warning", raw_value: Any = None) -> None:
        issues.append({
            "source_id": "booking", "source_file_sha256": sha, "source_row_id": row_id,
            "local_date": arrival_date, "field_name": field, "rule_code": code, "issue_type": kind,
            "severity": severity, "disposition": disposition,
            "raw_value": deepcopy(raw.get(field) if raw_value is None else raw_value), "reason": reason,
        })

    def missing_value(field: str) -> bool:
        if field == "children":
            tokens = (None, "", "NA")
        elif field == "country":
            tokens = (None, "", "NULL")
        else:
            tokens = (None, "")
        return raw[field] in tokens and field not in invalid_fields

    def source_number(field: str, *, integer: bool = True) -> tuple[int | Decimal | None, str | None]:
        if missing_value(field):
            return None, "Source value is missing according to this field's token contract"
        value, reason = checked_number(row[field], integer=integer)
        if field in invalid_fields:
            value, reason = None, "Invalid in selected Staging snapshot: " + ", ".join(sorted(set(invalid_fields[field])))
        if value is not None:
            token = raw[field]
            if token is None or (integer and field not in GUEST_FIELDS and not INTEGER_RE.fullmatch(token)):
                return None, "Typed value does not match a valid source integer token"
            try:
                raw_number = Decimal(token)
            except InvalidOperation:
                return None, "Source numeric token is invalid"
            if not raw_number.is_finite() or raw_number != value:
                return None, "Typed number is inconsistent with the original source token"
        return value, reason

    def number(field: str, *, integer: bool = True, flag: bool = False) -> int | Decimal | None:
        value, reason = source_number(field, integer=integer)
        if flag and value not in (None, 0, 1):
            value, reason = None, "Flag must be 0 or 1"
        if value is None:
            kind = "missing" if missing_value(field) else "invalid"
            core = field == "is_canceled"
            if core:
                disposition = "REJECT_FACT"
            elif field == "is_repeated_guest":
                disposition = "UNKNOWN_DIMENSION"
            else:
                disposition = "NULL_MEASURE"
            add_issue(field, f"{kind.upper()}_{field.upper()}", kind, disposition,
                      reason or "Value is unknown", severity="error" if core else "warning")
        return value

    # Check component-derived date against the typed date; never recover a failed date by guessing.
    year, year_error = source_number("arrival_date_year")
    day, day_error = source_number("arrival_date_day_of_month")
    month = row["arrival_date_month"]
    derived_date = None
    if year_error is None and day_error is None and isinstance(month, str) and month == raw["arrival_date_month"]:
        month_number = MONTH_NUMBERS.get(month.lower())
        if month_number is not None:
            try:
                derived_date = date(year, month_number, day)
            except (ValueError, OverflowError):
                derived_date = None
    date_invalid = any(field in invalid_fields for field in (*DATE_FIELDS, "arrival_date"))
    if type(row["arrival_date"]) is date and row["arrival_date"] == derived_date and not date_invalid:
        arrival_date = row["arrival_date"]
        if not calendar_start <= arrival_date <= calendar_end:
            raise ValueError("Calendar does not cover a valid Booking arrival date")
    else:
        kind = "missing" if any(missing_value(field) for field in DATE_FIELDS) else "invalid"
        add_issue("arrival_date", f"{kind.upper()}_ARRIVAL_DATE", kind, "REJECT_FACT",
                  "Arrival date is unknown, inconsistent or invalid; no date was inferred", severity="error",
                  raw_value={field: raw[field] for field in DATE_FIELDS})
        add_issue("arrival_date", "UNKNOWN_DATE_BLOCK_PUBLISH", "coverage", "BLOCK_PUBLISH",
                  "The affected arrival day cannot be determined under D06", severity="error",
                  raw_value={field: raw[field] for field in DATE_FIELDS})

    canceled = number("is_canceled", flag=True)
    if arrival_date is None or canceled is None:
        rejection = {"source_file_sha256": sha, "source_row_id": row_id, "arrival_date": arrival_date,
                     "reason_codes": sorted({i["rule_code"] for i in issues if i["disposition"] == "REJECT_FACT"})}
        return BookingTransformResult(None, rejection, issues, block_publish=arrival_date is None)

    fact = {"source_file_sha256": sha, "source_row_id": row_id, "source_first_batch_id": first_batch,
            "arrival_date": arrival_date, "date_key": arrival_date.year * 10000 + arrival_date.month * 100 + arrival_date.day,
            "country_raw": deepcopy(raw["country"]), "booking_count": 1, "is_canceled": canceled}
    for field in (*GUEST_FIELDS, *NIGHT_FIELDS, "lead_time"):
        fact[field] = number(field)
    fact["adr"] = number("adr", integer=False)
    guests = [fact[field] for field in GUEST_FIELDS]
    nights = [fact[field] for field in NIGHT_FIELDS]
    fact["total_guests"] = sum(guests) if all(value is not None for value in guests) else None
    fact["guest_eligible"] = fact["total_guests"] is not None and fact["total_guests"] > 0
    fact["total_stay_nights"] = sum(nights) if all(value is not None for value in nights) else None
    fact["stay_eligible"] = fact["total_stay_nights"] is not None
    for fields, total, code in ((GUEST_FIELDS, fact["total_guests"], "ZERO_GUESTS"),
                                (NIGHT_FIELDS, fact["total_stay_nights"], "ZERO_STAY_NIGHTS")):
        if total == 0:
            add_issue(",".join(fields), code, "warning", "WARN_ONLY", "Observed total is zero; source values are retained",
                      raw_value={field: raw[field] for field in fields})

    codes = {}
    for field, name in CATEGORICAL_FIELDS.items():
        unknown = "UNK" if name == "country" else "UNKNOWN"
        value = row[field]
        if missing_value(field):
            code, status = unknown, "missing"
        elif field in invalid_fields or not isinstance(value, str) or value != raw[field]:
            code, status = unknown, "invalid"
        else:
            code, status = mapped_value(value, mappings[name], unknown)
            if status == "missing":
                status = "unmapped"  # A present blank token is not a field-specific source missing token.
        codes[field] = code
        if status != "known":
            if status == "missing":
                kind = "missing"
            elif status == "invalid":
                kind = "invalid"
            else:
                kind = "mapping"
            add_issue(field, f"{status.upper()}_{field.upper()}", kind, "UNKNOWN_DIMENSION",
                      "Use the explicit unknown dimension member; preserve the source token")
    fact.update({"country_code": codes["country"], "channel_code": codes["distribution_channel"],
                 "market_segment_code": codes["market_segment"], "customer_type_code": codes["customer_type"],
                 "reserved_room_type_code": codes["reserved_room_type"], "assigned_room_type_code": codes["assigned_room_type"]})
    customer_type = row["customer_type"]
    type_mapping = mappings["customer_type"].get(customer_type.strip().upper()) if isinstance(customer_type, str) else None
    fact["customer_type_name"] = (type_mapping["target_name"] if type_mapping and fact["customer_type_code"] != "UNKNOWN" else "Unknown")
    repeated = number("is_repeated_guest", flag=True)
    fact["repeat_status"] = {0: "NEW", 1: "REPEAT"}.get(repeated, "UNKNOWN")
    fact["is_repeated_guest"] = None if repeated is None else repeated == 1
    fact["party_type"] = classify_party(fact["adults"], fact["children"], fact["babies"], fact["guest_eligible"])
    fact["party_eligible"] = fact["guest_eligible"]
    comparable = codes["reserved_room_type"] != "UNKNOWN" and codes["assigned_room_type"] != "UNKNOWN"
    fact["room_comparison_eligible"] = comparable
    fact["room_changed_flag"] = codes["reserved_room_type"] != codes["assigned_room_type"] if comparable else None
    return BookingTransformResult(fact, None, issues)
