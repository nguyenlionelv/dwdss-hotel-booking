"""Explain nested feature eligibility without changing source-quality policy."""
from collections import Counter
from datetime import timedelta

from .contracts import local_date


def filtering_analysis(snapshot, frames, config):
    full = frames["V3"]
    actual = {r.full_date: r for r in snapshot.rows}
    result = {
        "reservation_rows": snapshot.quality.get("dw_quality", {}).get("counts", {}).get("fact_booking"),
        "daily_observations": len(snapshot.rows),
        "aggregation_note": "Reservations are aggregated by arrival date; booking rows and daily forecasting samples have different grains.",
        "partitions": {},
    }
    for partition, split in config["splits"].items():
        start, end = local_date(split["start"]), local_date(split["end"])
        rows = full.loc[full.full_date.between(start, end)]
        dates = set(rows.full_date)
        complete = set(rows.loc[rows.target_ready, "full_date"])
        eligible = {label: set(frame.loc[frame.full_date.between(start, end) & frame.train_ready, "full_date"])
                    for label, frame in frames.items()}
        if not eligible["V3"] <= eligible["V2"] <= eligible["V1"] <= complete <= dates:
            raise ValueError("Feature eligibility masks are not nested")
        stages = []
        before = dates
        for stage, after, condition in [
            ("COMPLETE targets", complete, "Target status is COMPLETE and target is not NULL"),
            ("V1", eligible["V1"], "COMPLETE target and COMPLETE actual at exactly d-7"),
            ("V2", eligible["V2"], "V1 plus all seven preceding calendar dates COMPLETE"),
            ("V3", eligible["V3"], "V2 plus all fourteen preceding calendar dates COMPLETE"),
        ]:
            excluded = sorted(before - after)
            examples = []
            for day in excluded[:5]:
                lookback = 0 if stage == "COMPLETE targets" else 7 if stage in {"V1", "V2"} else 14
                offsets = [7] if stage == "V1" else range(1, lookback + 1)
                unavailable = []
                for offset in offsets:
                    historical = day - timedelta(days=offset)
                    row = actual.get(historical)
                    if row is None or row.guest_data_status != "COMPLETE" or row.target_guests is None:
                        unavailable.append({"date": str(historical),
                                            "status": row.guest_data_status if row else "OUTSIDE_ACTUAL_RANGE"})
                examples.append({"date": str(day), "target_status": actual[day].guest_data_status,
                                 "unavailable_history": unavailable})
            stages.append({"stage": stage, "before": len(before), "condition": condition,
                           "newly_excluded": len(excluded), "remaining": len(after),
                           "excluded_dates": [str(day) for day in excluded], "examples": examples})
            before = after
        combinations = Counter(tuple(sorted(reasons)) for reasons in rows.reason_codes)
        monthly = []
        for month in sorted({str(day)[:7] for day in dates}):
            group = {day for day in dates if str(day).startswith(month)}
            monthly.append({"month": month, "calendar_days": len(group), "complete_targets": len(group & complete),
                            "partial_targets": sum(actual[day].guest_data_status == "PARTIAL" for day in group),
                            **{label: len(group & mask) for label, mask in eligible.items()}})
        result["partitions"][partition] = {
            "start": str(start), "end": str(end), "calendar_days": (end - start).days + 1,
            "mart_days": len(dates), "target_status_counts": dict(Counter(rows.guest_data_status)),
            "stages": stages, "monthly": monthly,
            "marginal_exclusions": dict(Counter(reason for reasons in rows.reason_codes for reason in reasons)),
            "other_validation_failures": 0,
            "exclusive_combinations": [{"reasons": list(reasons), "days": count}
                                       for reasons, count in sorted(combinations.items())],
        }
    return result
