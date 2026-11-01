"""Build the two Operations aggregates inside the caller's DW transaction."""

from __future__ import annotations

import hashlib
import json

from psycopg import sql
from psycopg.types.json import Jsonb

from pipeline.source_to_staging.common import ROOT, sha256
from .migrations import verify_mart_schema


DATE_COLUMNS = ("date_key", "full_date", "year", "quarter", "month", "iso_year", "iso_week", "day_of_week", "is_weekend")
CONTEXT_COLUMNS = ("is_holiday", "has_national_holiday", "has_lisboa_holiday", "holiday_names", "temperature_mean",
                   "precipitation", "holiday_data_status", "temperature_status", "precipitation_status")
QUALITY_COLUMNS = ("booking_data_status", "guest_data_status", "stay_data_status", "rejected_booking_count",
                   "guest_ineligible_booking_count", "stay_ineligible_booking_count")
COUNT_COLUMNS = ("total_bookings", "non_canceled_bookings", "total_cancellations", "guest_valid_booking_count",
                 "stay_valid_booking_count", "lead_time_valid_count", "adr_valid_count")
SUM_COLUMNS = ("observed_total_adults", "observed_total_children", "observed_total_babies", "observed_total_guests",
               "observed_total_stay_nights", "sum_lead_time", "sum_adr")
KPI_COLUMNS = ("cancellation_rate", "avg_party_size", "avg_stay_nights", "avg_lead_time", "avg_adr")
COLUMNS = (*DATE_COLUMNS, "data_version", *CONTEXT_COLUMNS, *QUALITY_COLUMNS,
           *COUNT_COLUMNS, *SUM_COLUMNS, *KPI_COLUMNS, "target_guests")
COUNTRY_COLUMNS = ("country_key", "country_code", "country_name")
TABLES = ("daily_hotel_operations", "daily_hotel_operations_by_country")
RUNTIME_FILES = ("database/marts/operations_mart.sql", "database/marts/refresh_operations.sql",
                 "pipeline/dw_to_mart/operations.py", "pipeline/dw_to_mart/migrations.py",
                 "pipeline/dw_to_mart/checks.py", "pipeline/dw_to_mart/run.py",
                 "pipeline/staging_to_dw/preflight.py", "pipeline/quality/mart_checks.py")


def runtime_version() -> str:
    hashes = {name: sha256(ROOT / name) for name in RUNTIME_FILES}
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def build_fingerprint(data_version, bundle: dict) -> str:
    material = {"data_version": str(data_version), "config_sha256": bundle["config_sha256"], "code": runtime_version()}
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def clear_operations(conn) -> None:
    """Delete children before DW parents; MVCC readers retain the prior snapshot."""
    conn.execute("DELETE FROM mart.daily_hotel_operations_by_country")
    conn.execute("DELETE FROM mart.daily_hotel_operations")
    conn.execute("DELETE FROM mart.dataset_state")


def refresh_operations(conn, run_id, data_version, bundle: dict) -> None:
    """No commit here: both grains and DW must publish together."""
    verify_mart_schema(conn)
    # Full refresh changes run IDs before autovacuum can update statistics.
    # Stale estimates can otherwise repeat the aggregate for every country/day.
    conn.execute("""ANALYZE dw.fact_booking, dw.dim_date, dw.dim_country,
                    dw.daily_hotel_context, dw.daily_data_quality, dw.source_coverage""")
    actual = bundle["config"]["actual"]
    conn.execute((ROOT / "database/marts/refresh_operations.sql").read_text(encoding="utf-8"),
                 {"run_id": run_id, "data_version": data_version, "start": actual["start"], "end": actual["end"]})
    clear_operations(conn)
    for table, daily in zip(TABLES, (True, False), strict=True):
        columns = COLUMNS if daily else (*COLUMNS, *COUNTRY_COLUMNS)
        names = sql.SQL(",").join(map(sql.Identifier, columns))
        conn.execute(sql.SQL("INSERT INTO mart.{} ({}) SELECT {} FROM operations_candidate WHERE is_daily=%s").format(
            sql.Identifier(table), names, names), (daily,))


def publish_state(conn, run_id, data_version, bundle: dict, counts: dict) -> None:
    actual = bundle["config"]["actual"]
    conn.execute("""INSERT INTO mart.dataset_state
                    (singleton_id,dw_run_id,data_version,build_fingerprint,actual_start,actual_end,row_counts)
                    VALUES (1,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(singleton_id) DO UPDATE SET
                    dw_run_id=EXCLUDED.dw_run_id,data_version=EXCLUDED.data_version,
                    build_fingerprint=EXCLUDED.build_fingerprint,actual_start=EXCLUDED.actual_start,
                    actual_end=EXCLUDED.actual_end,row_counts=EXCLUDED.row_counts,published_at=now()""",
                 (run_id, data_version, build_fingerprint(data_version, bundle), actual["start"], actual["end"], Jsonb(counts)))
