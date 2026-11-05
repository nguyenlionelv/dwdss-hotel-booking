"""Frozen chronological origins, recursive backtesting and explicit coverage."""
from collections import Counter, defaultdict
from datetime import timedelta
import math
import statistics

from .contracts import DemandError, local_date
from .predict import forecast_demand

def origins_for_partition(snapshot, partition, history_days=14):
    start, end = local_date(partition["start"]), local_date(partition["end"])
    actual = {r.full_date:r for r in snapshot.rows}
    calendar = {r.full_date for r in snapshot.calendar}
    eligible, excluded = [], []
    origin = start - timedelta(days=1)
    while origin + timedelta(days=7) <= end:
        reasons = []
        if origin not in actual:
            reasons.append("CUTOFF_OUTSIDE_ACTUAL_RANGE")
        if any((r := actual.get(origin-timedelta(days=i))) is None or r.guest_data_status != "COMPLETE"
               or r.target_guests is None for i in range(history_days)):
            reasons.append("HISTORY_NOT_COMPLETE")
        if any((r := actual.get(origin+timedelta(days=i))) is None or r.guest_data_status != "COMPLETE"
               or r.target_guests is None for i in range(1,8)):
            reasons.append("OUTCOMES_NOT_COMPLETE")
        if any(origin+timedelta(days=i) not in calendar for i in range(1,8)):
            reasons.append("HORIZON_CALENDAR_UNAVAILABLE")
        if reasons:
            excluded.append({"as_of_date":origin.isoformat(),"reason_codes":reasons})
        else:
            eligible.append(origin.isoformat())
        origin += timedelta(days=1)
    return {"history_days":history_days,"eligible":eligible,"excluded":excluded,
            "exclusion_counts":dict(Counter(reason for r in excluded for reason in r["reason_codes"]))}

def nonoverlapping(origins):
    result = []
    for origin in origins:
        if not result or (local_date(origin)-local_date(result[-1])).days >= 7:
            result.append(origin)
    return result

def metrics(points):
    if not points:
        return {"mae":None,"rmse":None,"bias":None,"origins":0,"points":0}
    errors = [float(r["predicted_guest_count"])-float(r["actual_guest_count"]) for r in points]
    if any(not math.isfinite(e) for e in errors):
        raise DemandError("INVALID_METRIC", "Metric inputs must be finite")
    return {"mae":statistics.fmean(abs(e) for e in errors),
            "rmse":math.sqrt(statistics.fmean(e*e for e in errors)),
            "bias":statistics.fmean(errors),"origins":len({r["as_of_date"] for r in points}),"points":len(points)}

def summarize(points):
    result = metrics(points)
    result["by_horizon"] = {str(h):metrics([r for r in points if r["horizon"]==h]) for h in range(1,8)}
    groups = {}
    for group, key in (("weekday_weekend",lambda r:"weekend" if local_date(r["forecast_date"]).weekday()>=5 else "weekday"),
                       ("month",lambda r:r["forecast_date"][:7])):
        buckets = defaultdict(list)
        for row in points:
            buckets[key(row)].append(row)
        groups[group] = {name:{**metrics(rows),"small_group":len(rows)<7} for name,rows in sorted(buckets.items())}
    result["error_groups"] = groups
    result["largest_errors"] = sorted(points,key=lambda r:abs(r["predicted_guest_count"]-r["actual_guest_count"]),reverse=True)[:10]
    return result

def evaluate_bundle(bundle, snapshot, origins):
    actual = {r.full_date:r.target_guests for r in snapshot.rows if r.guest_data_status=="COMPLETE"}
    points = []
    for raw in origins:
        cutoff = local_date(raw)
        calendar = [r for r in snapshot.calendar if cutoff < r.full_date <= cutoff+timedelta(days=7)]
        result = forecast_demand(bundle,snapshot,calendar,cutoff)
        if result.status != "ok":
            raise DemandError("EVALUATION_UNAVAILABLE", "Frozen origin is not forecastable")
        for row in result.forecasts:
            day = local_date(row["forecast_date"])
            if day not in actual or actual[day] is None:
                raise DemandError("INVALID_ORIGIN", "Frozen origin has an incomplete scoring outcome")
            points.append({k:row[k] for k in ("as_of_date","forecast_date","horizon","predicted_guest_count")} |
                          {"actual_guest_count":actual[day],"model_name":bundle.manifest["model_name"]})
    score = summarize(points)
    subset = set(nonoverlapping(origins))
    score["nonoverlapping"] = summarize([r for r in points if r["as_of_date"] in subset])
    return score, points
