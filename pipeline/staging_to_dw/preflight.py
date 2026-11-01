"""Read-only profiling of one published Staging snapshot before DW migrations."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json

import psycopg
from psycopg.rows import dict_row

from pipeline.source_to_staging.common import ROOT, connect, sha256, verify_sources
from .config import coverage_status, mapped_value


CATEGORICAL_FIELDS = {
    "country": "country", "distribution_channel": "channel", "market_segment": "market_segment",
    "customer_type": "customer_type", "reserved_room_type": "room_type", "assigned_room_type": "room_type",
}
GUEST_FIELDS = ("adults", "children", "babies")
NIGHT_FIELDS = ("stays_in_week_nights", "stays_in_weekend_nights")


def valid_number(value, *, integer: bool = False, nonnegative: bool = True) -> bool:
    """Check finite/integer/range before casting; zero is a valid component."""
    if value is None or isinstance(value, bool):
        return False
    try:
        number = Decimal(str(value))
        if not number.is_finite() or (nonnegative and number < 0):
            return False
        return not integer or (number == number.to_integral_value() and 0 <= number <= 2147483647)
    except InvalidOperation:
        return False


def days_between(first: date, last: date):
    while first <= last:
        yield first
        first += timedelta(days=1)


def quality_status(base: str, affected: bool) -> str:
    # A known defect proves incompleteness even when source-wide capture is unknown.
    return "PARTIAL" if affected else base


def measure_values(rows: list[dict], coverage: str, rejected_count: int) -> dict:
    """Profile expected observed measures; this is not a DW loader or a Mart refresh."""
    non_canceled = [row for row in rows if row["is_canceled"] == 0]
    guests = [row for row in non_canceled if all(valid_number(row[f], integer=True) for f in GUEST_FIELDS)
              and sum(row[f] for f in GUEST_FIELDS) > 0]
    stays = [row for row in non_canceled if all(valid_number(row[f], integer=True) for f in NIGHT_FIELDS)]
    leads = [row for row in non_canceled if valid_number(row["lead_time"], integer=True)]
    adrs = [row for row in non_canceled if valid_number(row["adr"])]
    empty_known = coverage == "COMPLETE" and not non_canceled and not rejected_count

    def observed_sum(eligible, fields):
        if eligible:
            values = [Decimal(str(row[f])) for row in eligible for f in fields]
            # NUMERIC input may exceed Decimal's default 28 digits. Keep sums exact.
            precision = max(v.adjusted() + 1 for v in values) - min(v.as_tuple().exponent for v in values)
            with localcontext() as context:
                context.prec = max(28, precision + len(str(len(values))) + 2)
                return sum(values)
        return 0 if empty_known else None

    def average(total, count):
        return total / count if count and total is not None else None

    guest_sum = observed_sum(guests, GUEST_FIELDS)
    stay_sum = observed_sum(stays, NIGHT_FIELDS)
    lead_sum = observed_sum(leads, ("lead_time",))
    adr_sum = observed_sum(adrs, ("adr",))
    booking_status = quality_status(coverage, bool(rejected_count))
    guest_status = quality_status(coverage, bool(rejected_count or len(guests) != len(non_canceled)))
    stay_status = quality_status(coverage, bool(rejected_count or len(stays) != len(non_canceled)))
    return {
        "observed_fact_booking_count": len(rows), "rejected_booking_count": rejected_count,
        "total_bookings": len(rows) if rows or coverage == "COMPLETE" and not rejected_count else None,
        "non_canceled_bookings": len(non_canceled) if rows or empty_known else None,
        "total_cancellations": len(rows) - len(non_canceled) if rows or empty_known else None,
        "guest_valid_booking_count": len(guests), "stay_valid_booking_count": len(stays),
        "lead_time_valid_count": len(leads), "adr_valid_count": len(adrs),
        "guest_ineligible_booking_count": len(non_canceled) - len(guests),
        "stay_ineligible_booking_count": len(non_canceled) - len(stays),
        "observed_total_adults": observed_sum(guests, ("adults",)),
        "observed_total_children": observed_sum(guests, ("children",)),
        "observed_total_babies": observed_sum(guests, ("babies",)),
        "observed_total_guests": guest_sum, "observed_total_stay_nights": stay_sum,
        "sum_lead_time": lead_sum, "sum_adr": adr_sum,
        "cancellation_rate": (len(rows) - len(non_canceled)) / len(rows) if rows else None,
        "avg_party_size": average(guest_sum, len(guests)), "avg_stay_nights": average(stay_sum, len(stays)),
        "avg_lead_time": average(lead_sum, len(leads)), "avg_adr": average(adr_sum, len(adrs)),
        "booking_data_status": booking_status, "guest_data_status": guest_status, "stay_data_status": stay_status,
        "target_guests": guest_sum if guest_status == "COMPLETE" else None,
    }


def profile_bookings(rows: list[dict], bundle: dict) -> dict:
    """Inventory all observed codes and the subset with valid arrival/cancellation."""
    config, mappings = bundle["config"], bundle["mappings"]
    first, last = date.fromisoformat(config["calendar"]["start"]), date.fromisoformat(config["calendar"]["end"])
    actual_start = date.fromisoformat(config["actual"]["start"])
    actual_end = date.fromisoformat(config["actual"]["end"])
    inventories = {f: {} for f in CATEGORICAL_FIELDS}
    daily, rejections = defaultdict(list), Counter()
    dimensions = {name: set() for name in mappings}
    profile_counts = Counter()
    affected = defaultdict(list)
    errors = []
    accepted = []
    for row in rows:
        row_id = row["_source_row_id"]
        day = row["arrival_date"]
        core_ok = day is not None and row["is_canceled"] in (0, 1)
        if day is None:
            affected["UNKNOWN_ARRIVAL_DATE"].append(row_id)
        elif not first <= day <= last:
            affected["CALENDAR_OUT_OF_RANGE"].append(row_id)
        elif not actual_start <= day <= actual_end:
            affected["OUTSIDE_ACTUAL_INTERVAL"].append(row_id)
        if row["is_canceled"] not in (0, 1):
            affected["INVALID_CANCELLATION"].append(row_id)
        if not core_ok:
            if day is not None:
                rejections[day] += 1
        else:
            accepted.append(row)
            daily[day].append(row)
        codes = {}
        for field, name in CATEGORICAL_FIELDS.items():
            unknown = config["mappings"][name]["unknown_code"]
            code, disposition = mapped_value(row[field], mappings[name], unknown)
            codes[field] = code
            token = row["raw_record"].get(field)
            entry = inventories[field].setdefault(token, {
                "raw_token": token, "target_code": code, "disposition": disposition,
                "all_rows": 0, "accepted_candidate_rows": 0, "example_row_ids": [],
            })
            entry["all_rows"] += 1
            entry["accepted_candidate_rows"] += int(core_ok)
            if len(entry["example_row_ids"]) < 3:
                entry["example_row_ids"].append(row_id)
            if core_ok:
                dimensions[name].add(code)
        if core_ok:
            repeat = {0: "NEW", 1: "REPEAT"}.get(row["is_repeated_guest"], "UNKNOWN")
            profile_counts[(codes["customer_type"], repeat)] += 1
        if not all(valid_number(row[f], integer=True) for f in GUEST_FIELDS):
            affected["GUEST_COMPONENT_INELIGIBLE"].append(row_id)
            if row["is_canceled"] == 0:
                affected["NON_CANCELED_GUEST_COMPONENT_INELIGIBLE"].append(row_id)
        elif sum(row[f] for f in GUEST_FIELDS) == 0:
            affected["ZERO_GUESTS"].append(row_id)
            if row["is_canceled"] == 0:
                affected["NON_CANCELED_ZERO_GUESTS"].append(row_id)
        for field in (*GUEST_FIELDS, *NIGHT_FIELDS, "lead_time", "adr"):
            if not valid_number(row[field], integer=field != "adr"):
                kind = "MISSING" if row[field] is None and row["raw_record"].get(field) in (
                    None, "", "NA" if field == "children" else "") else "INVALID"
                affected[f"{field.upper()}_{kind}"].append(row_id)
        if row["is_repeated_guest"] not in (0, 1):
            affected["REPEAT_STATUS_UNKNOWN"].append(row_id)
    for rule in ("UNKNOWN_ARRIVAL_DATE", "CALENDAR_OUT_OF_RANGE", "OUTSIDE_ACTUAL_INTERVAL"):
        if affected[rule]:
            errors.append(f"{rule}: {len(affected[rule])} rows; review before build")
    for field, entries in inventories.items():
        unmapped = [entry["raw_token"] for entry in entries.values() if entry["disposition"] == "unmapped"]
        if unmapped:
            errors.append(f"{field}: unreviewed codes {unmapped}")
    for name, values in dimensions.items():
        values.add(config["mappings"][name]["unknown_code"])
    profile_counts.setdefault(("UNKNOWN", "UNKNOWN"), 0)
    row_dates = {r["_source_row_id"]: r["arrival_date"] for r in rows}
    actual_days = []
    for day in days_between(actual_start, actual_end):
        base = coverage_status(bundle["coverage"], "booking", "all", day)
        actual_days.append({"date": day.isoformat(), "source_coverage_status": base,
                            **measure_values(daily[day], base, rejections[day])})
    room_unknown = config["mappings"]["room_type"]["unknown_code"]
    room_comparable = []
    room_changed = []
    for row in accepted:
        reserved = mapped_value(row["reserved_room_type"], mappings["room_type"], room_unknown)[0]
        assigned = mapped_value(row["assigned_room_type"], mappings["room_type"], room_unknown)[0]
        if reserved != room_unknown and assigned != room_unknown:
            room_comparable.append(row["_source_row_id"])
            if reserved != assigned:
                room_changed.append(row["_source_row_id"])
    return {
        "source_count": len(rows), "accepted_candidate_count": len(accepted),
        "rejected_candidate_count": len(rows) - len(accepted),
        "inventory": {f: sorted(entries.values(), key=lambda e: (e["raw_token"] is None, e["raw_token"] or ""))
                      for f, entries in inventories.items()},
        "dimension_codes": {name: sorted(values) for name, values in dimensions.items() if name != "customer_type"},
        "customer_profiles": [{"customer_type_code": kind, "repeat_status": repeat, "rows": count}
                              for (kind, repeat), count in sorted(profile_counts.items())],
        "calendar_day_count": (last - first).days + 1, "actual_day_count": len(actual_days),
        "country_calendar_row_count": len(actual_days) * len(dimensions["country"]),
        "room_comparison": {"eligible_rows": len(room_comparable), "ineligible_rows": len(accepted) - len(room_comparable),
                            "different_code_rows": len(room_changed), "different_code_example_row_ids": room_changed[:10]},
        "rule_impacts": {rule: {"rows": len(ids), "known_day_count": len({row_dates[i] for i in ids if row_dates[i]}),
                                 "source_row_ids": ids} for rule, ids in affected.items()},
        "daily_measures": actual_days, "errors": errors,
    }


def profile_context(holidays: list[dict], weather: list[dict], issues: list[dict], bundle: dict) -> dict:
    """Check actual source rows before trusting a COMPLETE coverage declaration."""
    invalid_keys = {(i["source_id"], i["source_row_id"]) for i in issues if i["issue_type"] == "invalid"}
    valid_holidays = defaultdict(list)
    invalid_holidays = []
    weather_days = defaultdict(list)
    unknown_weather_dates = []
    errors = []
    for row in holidays:
        valid_scope = (row["scope"] == "national" and row["subdivision"] is None
                       or row["scope"] == "Lisboa" and row["subdivision"] == "11")
        valid = (row["date"] is not None and row["country"] == "PT" and valid_scope
                 and bool(row["holiday_name"] and row["holiday_name"].strip())
                 and row["category"] == "public" and row["observed"] is False
                 and ("holiday", row["_source_row_id"]) not in invalid_keys)
        if valid:
            valid_holidays[(row["date"], row["scope"])].append(row)
        else:
            invalid_holidays.append(row["_source_row_id"])
    if invalid_holidays:
        errors.append("Invalid Holiday rows require coverage reassessment before build")
    for row in weather:
        if row["local_date"] is None:
            unknown_weather_dates.append(row["_source_row_id"])
        else:
            weather_days[row["local_date"]].append(row)
    if unknown_weather_dates:
        errors.append("Unknown Weather dates require coverage reassessment before build")
    coverage_counts = defaultdict(Counter)
    duplicate_dates, invalid_temperature, invalid_precipitation, missing_complete = [], [], [], []
    calendar = bundle["config"]["calendar"]
    for day in days_between(date.fromisoformat(calendar["start"]), date.fromisoformat(calendar["end"])):
        for sid, scope in (("booking", "all"), ("holiday", "national"), ("holiday", "Lisboa"), ("weather", "all")):
            coverage_counts[f"{sid}:{scope}"][coverage_status(bundle["coverage"], sid, scope, day)] += 1
        entries = weather_days[day]
        if len(entries) > 1:
            duplicate_dates.append(day.isoformat())
        if len(entries) == 1:
            row = entries[0]
            if not valid_number(row["temperature_2m_mean"], nonnegative=False):
                invalid_temperature.append(day.isoformat())
            if not valid_number(row["precipitation_sum"]):
                invalid_precipitation.append(day.isoformat())
        weather_status = coverage_status(bundle["coverage"], "weather", "all", day)
        if weather_status == "COMPLETE" and (len(entries) != 1 or day.isoformat() in invalid_temperature
                                             or day.isoformat() in invalid_precipitation
                                             or any(("weather", r["_source_row_id"]) in invalid_keys for r in entries)):
            missing_complete.append(day.isoformat())
    if missing_complete:
        errors.append("Weather COMPLETE coverage contradicts observed rows/values/issues")
    return {"holiday_valid_rows": sum(len(v) for v in valid_holidays.values()),
            "holiday_scope_counts": dict(Counter(row["scope"] for entries in valid_holidays.values() for row in entries)),
            "holiday_invalid_row_ids": invalid_holidays, "weather_unknown_date_row_ids": unknown_weather_dates,
            "weather_duplicate_dates": duplicate_dates, "temperature_missing_or_invalid_dates": invalid_temperature,
            "precipitation_missing_or_invalid_dates": invalid_precipitation,
            "weather_complete_claim_failures": missing_complete,
            "calendar_coverage_days": {k: dict(v) for k, v in coverage_counts.items()}, "errors": errors}


def report(conn: psycopg.Connection, bundle: dict) -> dict:
    """Require a fresh connection; enforce one read-only repeatable-read transaction."""
    if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        raise ValueError("Preflight requires an idle connection")
    if any(bundle["coverage"]["source_checksums"][sid] != spec["sha256"] for sid, spec in bundle["sources"].items()):
        raise ValueError("Coverage differs from selected source checksums")
    with conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""SELECT b.batch_id,b.status,b.source_set_fingerprint,b.contract_version,
                                  a.published_at,current_setting('server_version') AS database_version
                           FROM staging.active_snapshot a JOIN staging.load_batch b ON b.batch_id=a.batch_id
                           WHERE a.singleton_id=1""")
            snapshot = cur.fetchone()
            if not snapshot or snapshot["status"] != "published":
                raise ValueError("No published Staging snapshot")
            if (snapshot["source_set_fingerprint"] != bundle["source_set_fingerprint"]
                    or snapshot["contract_version"] != bundle["staging_contract"]):
                raise ValueError("Active snapshot differs from selected manifest")
            cur.execute("""SELECT source_id,source_file_sha256,source_metadata,raw_count,staged_count,
                                  out_of_scope_count,unidentified_count,reject_count
                           FROM staging.load_batch_source WHERE batch_id=%s ORDER BY source_id""",
                        (snapshot["batch_id"],))
            registry = cur.fetchall()
            if {r["source_id"] for r in registry} != {"booking", "holiday", "weather"}:
                raise ValueError("Published snapshot must contain all three sources")
            for row in registry:
                if row["source_file_sha256"] != bundle["sources"][row["source_id"]]["sha256"]:
                    raise ValueError("Registry checksum differs from selected source")
            cur.execute("""SELECT i.source_id,i.source_file_sha256,i.source_row_id,i.field,i.rule_code,i.issue_type
                           FROM staging.quality_issue i JOIN staging.load_batch_source s
                             ON s.batch_id=i.batch_id AND s.source_id=i.source_id
                            AND s.source_file_sha256=i.source_file_sha256
                           WHERE i.batch_id=%s ORDER BY i.issue_id""", (snapshot["batch_id"],))
            issues = cur.fetchall()
            cur.execute("SELECT count(*) AS n FROM staging.reject WHERE batch_id=%s", (snapshot["batch_id"],))
            structural_rejects = cur.fetchone()["n"]
            cur.execute("""SELECT _source_file_sha256,_source_row_id,_batch_id,raw_record,arrival_date,is_canceled,
                                  country,distribution_channel,market_segment,customer_type,is_repeated_guest,
                                  reserved_room_type,assigned_room_type,adults,children,babies,
                                  stays_in_week_nights,stays_in_weekend_nights,lead_time,adr,hotel
                           FROM staging.v_booking_current ORDER BY _source_row_id""")
            bookings = cur.fetchall()
            cur.execute("""SELECT _source_row_id,date,holiday_name,country,subdivision,scope,category,observed
                           FROM staging.v_holiday_current ORDER BY _source_row_id""")
            holidays = cur.fetchall()
            cur.execute("""SELECT _source_row_id,local_date,temperature_2m_mean,precipitation_sum
                           FROM staging.v_weather_current ORDER BY _source_row_id""")
            weather = cur.fetchall()
            cur.execute("""SELECT count(*) AS n FROM staging.v_booking_current s
                           LEFT JOIN staging.load_batch_source b ON b.batch_id=s._batch_id AND b.source_id='booking'
                            AND b.source_file_sha256=s._source_file_sha256 WHERE b.batch_id IS NULL""")
            bad_first_batch = cur.fetchone()["n"]
    booking = profile_bookings(bookings, bundle)
    context = profile_context(holidays, weather, issues, bundle)
    errors = booking["errors"] + context["errors"]
    if structural_rejects or bad_first_batch or any(r["hotel"] != "City Hotel" for r in bookings):
        errors.append("Structural rejects, invalid first-batch lineage or hotel scope")
    for row in registry:
        observed = {"booking": len(bookings), "holiday": len(holidays), "weather": len(weather)}[row["source_id"]]
        if row["staged_count"] != observed or row["raw_count"] != sum(row[k] for k in
                ("staged_count", "out_of_scope_count", "unidentified_count", "reject_count")):
            errors.append(f"{row['source_id']}: registry/count reconciliation failed")
        for field, expected in bundle["sources"][row["source_id"]].get("expected", {}).items():
            if row.get(field) != expected:
                errors.append(f"{row['source_id']}: {field} differs from selected manifest")
    gaps = [f"{key}: {counts['UNKNOWN']} calendar days UNKNOWN" for key, counts in context["calendar_coverage_days"].items()
            if counts.get("UNKNOWN")]
    build_inputs = {"config_sha256": bundle["config_sha256"], "source_set_fingerprint": bundle["source_set_fingerprint"]}
    return {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "stage": "dw_input_preparation",
            "passed": not errors, "dw_ready": False, "coverage_gaps": gaps, "errors": errors,
            "code_sha256": {name: sha256(ROOT / name) for name in (
                "pipeline/staging_to_dw/config.py", "pipeline/staging_to_dw/preflight.py", "scripts/check_dw_inputs.py")},
            "snapshot": snapshot, "registry": registry, "config_sha256": bundle["config_sha256"],
            "input_fingerprint": hashlib.sha256(json.dumps(build_inputs, sort_keys=True).encode()).hexdigest(),
            "first_batch_differs_from_active_rows": sum(r["_batch_id"] != snapshot["batch_id"] for r in bookings),
            "staging_issue_counts": dict(Counter(i["rule_code"] for i in issues)),
            "booking": booking, "context": context}


def run(bundle: dict, *, dbname: str | None = None) -> dict:
    verify_sources(bundle["sources"])
    with connect(dbname) as conn:
        return report(conn, bundle)
