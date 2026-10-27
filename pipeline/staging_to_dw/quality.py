"""Source coverage and daily Booking quality, keeping technical zero counts explicit."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from .config import coverage_status
from .context import combined_coverage


QUALITY_COUNTS = ("source_booking_count", "fact_booking_count", "rejected_booking_count", "non_canceled_booking_count",
    "guest_ineligible_booking_count", "stay_ineligible_booking_count", "lead_time_unknown_booking_count", "adr_unknown_booking_count",
    "unknown_party_booking_count", "unknown_channel_booking_count", "unknown_segment_booking_count", "unknown_customer_type_booking_count",
    "unknown_repeat_booking_count", "room_ineligible_booking_count")
QUALITY_COLUMNS = ("date_key", "dw_run_id", *QUALITY_COUNTS, "booking_data_status", "guest_data_status", "stay_data_status", "reason_codes")


def build_coverage(calendar: list[dict], context: list[dict], bundle: dict) -> list[dict]:
    output = []
    for calendar_row, context_row in zip(calendar, context, strict=True):
        day = calendar_row["full_date"]
        for sid in ("booking", "holiday", "weather"):
            scopes = ("national", "Lisboa") if sid == "holiday" else ("all",)
            states = [coverage_status(bundle["coverage"], sid, scope, day) for scope in scopes]
            status = context_row["holiday_data_status"] if sid == "holiday" else combined_coverage(states)
            matches = [e for e in bundle["coverage"]["intervals"] if e["source_id"] == sid
                       and date.fromisoformat(e["start"]) <= day <= date.fromisoformat(e["end"])]
            refs = {(e["evidence"]["file"], e["evidence"]["sha256"]) for e in matches}
            if len(refs) == 1:
                ref, checksum = next(iter(refs))
            elif refs:
                ref, checksum = bundle["config"]["coverage"]["file"], bundle["config"]["coverage"]["sha256"]
            else:
                ref, checksum = None, None
            output.append({"source_id": sid, "local_date": day, "coverage_status": status,
                           "evidence_ref": ref, "evidence_sha256": checksum,
                           "reason": "; ".join(f"{scope}={state}" for scope, state in zip(scopes, states, strict=True))
                                     + ("; Holiday issues affect completeness" if sid == "holiday" and status != combined_coverage(states) else "")})
    return output


def build_daily_quality(calendar: list[dict], source: list[dict], facts: list[dict], rejections: list[dict], coverage: dict) -> list[dict]:
    source_by_day, fact_by_day, rejected_by_day = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in source:
        if row["arrival_date"] is not None:
            source_by_day[row["arrival_date"]].append(row)
    for row in facts:
        fact_by_day[row["arrival_date"]].append(row)
    for row in rejections:
        if row["arrival_date"] is not None:
            rejected_by_day[row["arrival_date"]].append(row)
    output = []
    for calendar_row in calendar:
        day = calendar_row["full_date"]
        all_facts, rejected = fact_by_day[day], rejected_by_day[day]
        active = [r for r in all_facts if r["is_canceled"] == 0]
        row = {"date_key": calendar_row["date_key"], "source_booking_count": len(source_by_day[day]),
               "fact_booking_count": len(all_facts), "rejected_booking_count": len(rejected), "non_canceled_booking_count": len(active)}
        conditions = {
            "guest_ineligible_booking_count": lambda f: not f["guest_eligible"],
            "stay_ineligible_booking_count": lambda f: not f["stay_eligible"],
            "lead_time_unknown_booking_count": lambda f: f["lead_time"] is None,
            "adr_unknown_booking_count": lambda f: f["adr"] is None,
            "unknown_party_booking_count": lambda f: f["party_type"] == "UNKNOWN",
            "unknown_channel_booking_count": lambda f: f["channel_code"] == "UNKNOWN",
            "unknown_segment_booking_count": lambda f: f["market_segment_code"] == "UNKNOWN",
            "unknown_customer_type_booking_count": lambda f: f["customer_type_code"] == "UNKNOWN",
            "unknown_repeat_booking_count": lambda f: f["repeat_status"] == "UNKNOWN",
            "room_ineligible_booking_count": lambda f: not f["room_comparison_eligible"],
        }
        row.update({key: sum(condition(f) for f in active) for key, condition in conditions.items()})
        base = coverage_status(coverage, "booking", "all", day)
        row["booking_data_status"] = "PARTIAL" if rejected else base
        row["guest_data_status"] = "PARTIAL" if rejected or row["guest_ineligible_booking_count"] else base
        row["stay_data_status"] = "PARTIAL" if rejected or row["stay_ineligible_booking_count"] else base
        reasons = [f"BOOKING_COVERAGE_{base}"] if base != "COMPLETE" else []
        if rejected:
            reasons.append("CORE_REJECTION")
        if row["guest_ineligible_booking_count"]:
            reasons.append("GUEST_INELIGIBLE")
        if row["stay_ineligible_booking_count"]:
            reasons.append("STAY_INELIGIBLE")
        row["reason_codes"] = sorted(reasons)
        output.append(row)
    return output
