"""Independent Python reconciliation of SQL Mart rows against DW facts."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, localcontext

from psycopg import sql
from psycopg.rows import dict_row

from pipeline.staging_to_dw.preflight import measure_values
from .migrations import verify_mart_schema
from .operations import (COLUMNS, CONTEXT_COLUMNS, COUNT_COLUMNS, COUNTRY_COLUMNS, DATE_COLUMNS, KPI_COLUMNS,
                         QUALITY_COLUMNS, SUM_COLUMNS, TABLES, build_fingerprint)


def expected_measures(facts: list[dict], coverage: str, rejected: int) -> dict:
    """Reuse preflight reference arithmetic, independent of the SQL aggregate."""
    values = measure_values(facts,coverage,rejected)
    return {name:values[name] for name in (*COUNT_COLUMNS,*SUM_COLUMNS,*KPI_COLUMNS)}


def same_value(field: str, actual, expected) -> bool:
    if field not in KPI_COLUMNS or actual is None or expected is None:
        return actual == expected
    expected = Decimal(str(expected))
    return actual.is_finite() and abs(actual - expected) <= Decimal("1e-12") * max(Decimal(1), abs(expected))


def validate_operations(conn, run_id, bundle: dict, *, require_state: bool = True) -> dict:
    """Run in the caller's stable transaction; candidate DW runs may be loading."""
    verify_mart_schema(conn)
    version, config_hash = conn.execute("SELECT data_version,config_sha256 FROM dw.load_run WHERE run_id=%s", (run_id,)).fetchone()
    if config_hash != bundle["config_sha256"]:
        raise ValueError("Mart requires the configuration used by this DW run")
    actual = bundle["config"]["actual"]
    start, end = date.fromisoformat(actual["start"]), date.fromisoformat(actual["end"])
    expected_dates = {start + timedelta(days=i) for i in range((end-start).days+1)}
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT date_key,full_date,year,quarter,month,iso_year,iso_week,day_of_week,is_weekend FROM dw.dim_date")
        dates = {row["date_key"]: row for row in cur if row["full_date"] in expected_dates}
        cur.execute("""SELECT date_key,country_key,is_canceled,adults,children,babies,total_guests,guest_eligible,
                              total_stay_nights,stay_eligible,stays_in_week_nights,stays_in_weekend_nights,
                              lead_time,adr FROM dw.fact_booking WHERE dw_run_id=%s""", (run_id,))
        by_date, by_country = defaultdict(list), defaultdict(list)
        for row in cur:
            by_date[row["date_key"]].append(row)
            by_country[(row["date_key"],row["country_key"])].append(row)
        cur.execute("SELECT country_key,country_code,country_name FROM dw.dim_country")
        accepted_countries = {key[1] for key in by_country} | {0}
        countries = {row["country_key"]: row for row in cur if row["country_key"] in accepted_countries}
        cur.execute("SELECT * FROM dw.daily_hotel_context WHERE dw_run_id=%s", (run_id,))
        contexts = {row["date_key"]: row for row in cur}
        cur.execute("SELECT * FROM dw.daily_data_quality WHERE dw_run_id=%s", (run_id,))
        qualities = {row["date_key"]: row for row in cur}
    coverage = dict(conn.execute("SELECT local_date,coverage_status FROM dw.source_coverage WHERE run_id=%s AND source_id='booking'", (run_id,)))
    checks = {"actual_calendar": len(expected_dates ^ {r["full_date"] for r in dates.values()}),
              "country_dictionary": len(accepted_countries ^ set(countries)),
              "context_dates": len(set(dates)-set(contexts)), "quality_dates": len(set(dates)-set(qualities)),
              "coverage_dates": len(expected_dates-set(coverage))}
    counts = {}
    for table, daily in zip(TABLES, (True, False), strict=True):
        wanted = {(day,) for day in dates} if daily else {(day,country) for day in dates for country in accepted_countries}
        seen = set()
        problems = {"keys": 0, "calendar": 0, "context": 0, "quality": 0, "measures": 0, "version": 0, "country": 0}
        columns = COLUMNS if daily else (*COLUMNS, *COUNTRY_COLUMNS)
        count = 0
        # Named cursor bounds memory for the full calendar x country output.
        with conn.cursor(name="check_" + table, row_factory=dict_row) as cur, localcontext() as arithmetic:
            arithmetic.prec = 80
            cur.execute(sql.SQL("SELECT {} FROM mart.{}").format(
                sql.SQL(",").join(map(sql.Identifier, columns)), sql.Identifier(table)))
            for row in cur:
                count += 1
                day = row["date_key"]
                key = (day,) if daily else (day,row["country_key"])
                problems["keys"] += key in seen
                seen.add(key)
                if key not in wanted or day not in contexts or day not in qualities or dates[day]["full_date"] not in coverage:
                    continue
                problems["calendar"] += any(row[c] != dates[day][c] for c in DATE_COLUMNS)
                problems["context"] += any(row[c] != contexts[day][c] for c in CONTEXT_COLUMNS)
                problems["quality"] += any(row[c] != qualities[day][c] for c in QUALITY_COLUMNS)
                problems["version"] += row["data_version"] != version
                if not daily:
                    problems["country"] += any(row[c] != countries[row["country_key"]][c] for c in COUNTRY_COLUMNS)
                facts = by_date.get(day, []) if daily else by_country.get(key, [])
                expected = expected_measures(facts, coverage[dates[day]["full_date"]], qualities[day]["rejected_booking_count"])
                expected["target_guests"] = expected["observed_total_guests"] if qualities[day]["guest_data_status"] == "COMPLETE" else None
                problems["measures"] += any(not same_value(field,row[field],value) for field,value in expected.items())
        problems["keys"] += len(wanted ^ seen)
        counts[table] = count
        checks.update({f"{table}_{name}": value for name,value in problems.items()})
    # Reconcile additive country values only; context/day-level quality is not additive.
    fields = ("total_bookings", "non_canceled_bookings", "total_cancellations", "guest_valid_booking_count",
              "stay_valid_booking_count", "lead_time_valid_count", "adr_valid_count", *SUM_COLUMNS)
    rollup = sql.SQL(",").join(sql.SQL("sum({0}) AS {0}").format(sql.Identifier(c)) for c in fields)
    # Empty country cells can be zero while a populated, entirely ineligible group
    # has an unknown daily sum. Per-cell checks above already enforce that case.
    comparisons = sql.SQL(" OR ").join(
        sql.SQL("(d.{0} IS NOT NULL AND d.{0} IS DISTINCT FROM c.{0})").format(sql.Identifier(c))
        if c in SUM_COLUMNS else sql.SQL("d.{0} IS DISTINCT FROM c.{0}").format(sql.Identifier(c)) for c in fields)
    checks["country_daily_reconciliation"] = conn.execute(sql.SQL("""SELECT count(*) FROM mart.daily_hotel_operations d
        JOIN (SELECT date_key,{} FROM mart.daily_hotel_operations_by_country GROUP BY date_key) c USING(date_key)
        WHERE {}""").format(rollup, comparisons)).fetchone()[0]
    if require_state:
        state = conn.execute("""SELECT dw_run_id,data_version,build_fingerprint,actual_start,actual_end,row_counts
                                FROM mart.dataset_state WHERE singleton_id=1""").fetchone()
        checks["dataset_state"] = int(state != (run_id,version,build_fingerprint(version,bundle),start,end,counts))
    statuses = dict(conn.execute("SELECT guest_data_status,count(*) FROM mart.daily_hotel_operations GROUP BY guest_data_status"))
    totals = conn.execute("""SELECT sum(total_bookings),sum(non_canceled_bookings),sum(total_cancellations),
                                   sum(observed_total_guests),sum(observed_total_stay_nights),sum(sum_adr)
                            FROM mart.daily_hotel_operations""").fetchone()
    return {"passed": not any(checks.values()), "run_id": str(run_id), "data_version": str(version),
            "build_fingerprint": build_fingerprint(version,bundle), "checks": checks,
            "errors": [f"{name}: {value} violations" for name,value in checks.items() if value],
            "counts": counts, "actual_guest_quality_days": statuses,
            "observed_totals": dict(zip(("bookings", "non_canceled_bookings", "cancellations",
                                          "eligible_non_canceled_guests", "eligible_non_canceled_nights", "non_canceled_adr_sum"), totals))}
