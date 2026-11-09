"""MART-05: Data Mart dependency + validation tests.

Acceptance Criteria:
- Mart totals reconcile 100% with Data Warehouse facts (dw.fact_booking).
- Clear grain: exactly 1 row = 1 date in mart.daily_hotel_operations, no accidental duplication.
- Country breakdown grain: exactly 1 row = (date_key, country_key) in mart.daily_hotel_operations_by_country.
- Cross-table reconciliation: sum of country measures equals daily total measures for every date.
- Python reference validation via validate_operations() and quality report() passes.
"""

from decimal import Decimal
import json
from pathlib import Path
import sys

from uuid import UUID

from psycopg.rows import dict_row
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests/pipeline"))

from pipeline.dw_to_mart.checks import validate_operations
from pipeline.dw_to_mart.migrations import apply_mart_migration
from pipeline.dw_to_mart.run import run as refresh_mart
from pipeline.quality.mart_checks import report as mart_quality_report
from pipeline.source_to_staging.common import connect
from pipeline.source_to_staging.run import run as stage_sources
from pipeline.staging_to_dw.config import load_config
from pipeline.staging_to_dw.run import run as load_dw
from test_dw_inputs_postgres import make_sources
from test_dw_postgres import config_for, database


def setup_published_mart(database_name: str, tmp_path: Path):
    """Seed test database through Staging -> DW -> Operations Mart."""
    manifest = make_sources(tmp_path)
    stage_sources(manifest, dbname=database_name)
    config = config_for(tmp_path, manifest)
    dw_result = load_dw(config, dbname=database_name)
    with connect(database_name) as conn:
        apply_mart_migration(conn)
    mart_result = refresh_mart(config, dbname=database_name)
    assert mart_result["status"] == "published"
    return manifest, config, dw_result, mart_result


def test_mart_05_grain_and_no_accidental_duplication(database, tmp_path):
    """Verify unique key constraints, grain integrity, and zero duplicate rows."""
    _, _, dw_result, _ = setup_published_mart(database, tmp_path)
    run_id = dw_result["run_id"]

    with connect(database) as conn, conn.cursor(row_factory=dict_row) as cur:
        # 1. Verify daily_hotel_operations grain: 1 row per date_key
        cur.execute("""
            SELECT count(*) AS total_rows,
                   count(DISTINCT date_key) AS distinct_dates,
                   count(DISTINCT full_date) AS distinct_full_dates
            FROM mart.daily_hotel_operations;
        """)
        daily_grain = cur.fetchone()
        assert daily_grain["total_rows"] > 0
        assert daily_grain["total_rows"] == daily_grain["distinct_dates"]
        assert daily_grain["total_rows"] == daily_grain["distinct_full_dates"]

        # Check that no date_key appears more than once (no duplication)
        cur.execute("""
            SELECT date_key, count(*) AS cnt
            FROM mart.daily_hotel_operations
            GROUP BY date_key
            HAVING count(*) > 1;
        """)
        assert cur.fetchall() == []

        # 2. Verify daily_hotel_operations_by_country grain: 1 row per (date_key, country_key)
        cur.execute("""
            SELECT count(*) AS total_rows,
                   count(DISTINCT (date_key, country_key)) AS distinct_pairs
            FROM mart.daily_hotel_operations_by_country;
        """)
        country_grain = cur.fetchone()
        assert country_grain["total_rows"] > 0
        assert country_grain["total_rows"] == country_grain["distinct_pairs"]

        # Check for duplicates in country table
        cur.execute("""
            SELECT date_key, country_key, count(*) AS cnt
            FROM mart.daily_hotel_operations_by_country
            GROUP BY date_key, country_key
            HAVING count(*) > 1;
        """)
        assert cur.fetchall() == []

        # 3. Verify Foreign Keys link back to valid dimension records
        cur.execute("""
            SELECT count(*) AS orphan_dates
            FROM mart.daily_hotel_operations m
            LEFT JOIN dw.dim_date d ON d.date_key = m.date_key
            WHERE d.date_key IS NULL;
        """)
        assert cur.fetchone()["orphan_dates"] == 0

        cur.execute("""
            SELECT count(*) AS orphan_countries
            FROM mart.daily_hotel_operations_by_country m
            LEFT JOIN dw.dim_country c ON c.country_key = m.country_key
            WHERE c.country_key IS NULL;
        """)
        assert cur.fetchone()["orphan_countries"] == 0


def test_mart_05_reconciliation_dw_totals_match_mart(database, tmp_path):
    """Verify that all core metrics in Operations Mart reconcile 100% with dw.fact_booking."""
    _, _, dw_result, _ = setup_published_mart(database, tmp_path)
    run_id = dw_result["run_id"]

    with connect(database) as conn, conn.cursor(row_factory=dict_row) as cur:
        # Calculate ground truth directly from dw.fact_booking for this published run
        cur.execute("""
            SELECT
                count(*) AS dw_total_bookings,
                count(*) FILTER (WHERE is_canceled = 0) AS dw_non_canceled,
                count(*) FILTER (WHERE is_canceled = 1) AS dw_cancellations,
                count(*) FILTER (WHERE is_canceled = 0 AND guest_eligible) AS dw_guest_valid,
                count(*) FILTER (WHERE is_canceled = 0 AND total_guests = 0) AS dw_guest_missing,
                sum(adults) FILTER (WHERE is_canceled = 0 AND guest_eligible) AS dw_adults,
                sum(children) FILTER (WHERE is_canceled = 0 AND guest_eligible) AS dw_children,
                sum(babies) FILTER (WHERE is_canceled = 0 AND guest_eligible) AS dw_babies,
                sum(total_guests) FILTER (WHERE is_canceled = 0 AND guest_eligible) AS dw_guests,
                sum(total_stay_nights) FILTER (WHERE is_canceled = 0 AND stay_eligible) AS dw_stay_nights,
                sum(lead_time) FILTER (WHERE is_canceled = 0 AND lead_time IS NOT NULL) AS dw_lead_time,
                sum(adr) FILTER (WHERE is_canceled = 0 AND adr IS NOT NULL) AS dw_sum_adr
            FROM dw.fact_booking
            WHERE dw_run_id = %s;
        """, (run_id,))
        dw_totals = cur.fetchone()

        # Aggregate from mart.daily_hotel_operations
        cur.execute("""
            SELECT
                sum(total_bookings) AS mart_total_bookings,
                sum(non_canceled_bookings) AS mart_non_canceled,
                sum(total_cancellations) AS mart_cancellations,
                sum(guest_valid_booking_count) AS mart_guest_valid,
                sum(missing_guest_bookings_count) AS mart_guest_missing,
                sum(observed_total_adults) AS mart_adults,
                sum(observed_total_children) AS mart_children,
                sum(observed_total_babies) AS mart_babies,
                sum(observed_total_guests) AS mart_guests,
                sum(observed_total_stay_nights) AS mart_stay_nights,
                sum(sum_lead_time) AS mart_lead_time,
                sum(sum_adr) AS mart_sum_adr
            FROM mart.daily_hotel_operations;
        """)
        mart_totals = cur.fetchone()

        # Assert 100% exact reconciliation between DW and Mart
        assert mart_totals["mart_total_bookings"] == dw_totals["dw_total_bookings"]
        assert mart_totals["mart_non_canceled"] == dw_totals["dw_non_canceled"]
        assert mart_totals["mart_cancellations"] == dw_totals["dw_cancellations"]
        assert mart_totals["mart_guest_valid"] == dw_totals["dw_guest_valid"]
        assert mart_totals["mart_guest_missing"] == dw_totals["dw_guest_missing"]
        assert mart_totals["mart_adults"] == dw_totals["dw_adults"]
        assert mart_totals["mart_children"] == dw_totals["dw_children"]
        assert mart_totals["mart_babies"] == dw_totals["dw_babies"]
        assert mart_totals["mart_guests"] == dw_totals["dw_guests"]
        assert mart_totals["mart_stay_nights"] == dw_totals["dw_stay_nights"]
        assert mart_totals["mart_lead_time"] == dw_totals["dw_lead_time"]

        # Float / Decimal reconciliation with numerical tolerance
        assert float(mart_totals["mart_sum_adr"]) == pytest.approx(float(dw_totals["dw_sum_adr"]), rel=1e-6)


def test_mart_05_reconciliation_country_breakdown_matches_daily(database, tmp_path):
    """Verify that summing country breakdown rows yields the exact daily total on every date."""
    _, _, _, _ = setup_published_mart(database, tmp_path)

    with connect(database) as conn, conn.cursor(row_factory=dict_row) as cur:
        # Sum by date from country breakdown and join to daily table
        cur.execute("""
            WITH country_sum AS (
                SELECT
                    date_key,
                    sum(total_bookings) AS c_total_bookings,
                    sum(non_canceled_bookings) AS c_non_canceled,
                    sum(total_cancellations) AS c_cancellations,
                    sum(observed_total_guests) AS c_guests,
                    sum(guest_valid_booking_count) AS c_guest_valid,
                    sum(missing_guest_bookings_count) AS c_guest_missing,
                    sum(observed_total_stay_nights) AS c_stay_nights,
                    sum(sum_adr) AS c_sum_adr
                FROM mart.daily_hotel_operations_by_country
                GROUP BY date_key
            )
            SELECT
                d.date_key,
                d.full_date,
                d.total_bookings AS d_total_bookings,
                c.c_total_bookings,
                d.non_canceled_bookings AS d_non_canceled,
                c.c_non_canceled,
                d.total_cancellations AS d_cancellations,
                c.c_cancellations,
                d.observed_total_guests AS d_guests,
                c.c_guests,
                d.guest_valid_booking_count AS d_guest_valid,
                c.c_guest_valid,
                d.missing_guest_bookings_count AS d_guest_missing,
                c.c_guest_missing,
                d.observed_total_stay_nights AS d_stay_nights,
                c.c_stay_nights,
                d.sum_adr AS d_sum_adr,
                c.c_sum_adr
            FROM mart.daily_hotel_operations d
            JOIN country_sum c ON c.date_key = d.date_key;
        """)

        rows = cur.fetchall()
        assert len(rows) > 0
        for r in rows:
            assert r["d_total_bookings"] == r["c_total_bookings"], f"Bookings mismatch on date_key {r['date_key']}"
            assert r["d_non_canceled"] == r["c_non_canceled"], f"Non-canceled mismatch on date_key {r['date_key']}"
            assert r["d_cancellations"] == r["c_cancellations"], f"Cancellations mismatch on date_key {r['date_key']}"
            assert r["d_guests"] == r["c_guests"], f"Guests mismatch on date_key {r['date_key']}"
            assert r["d_guest_valid"] == r["c_guest_valid"]
            assert r["d_guest_missing"] == r["c_guest_missing"]
            assert r["d_stay_nights"] == r["c_stay_nights"], f"Stay nights mismatch on date_key {r['date_key']}"
            if r["d_sum_adr"] is not None:
                assert float(r["d_sum_adr"]) == pytest.approx(float(r["c_sum_adr"]), rel=1e-6)


def test_mart_05_quality_report_and_independent_validation_pass(database, tmp_path):
    """Run pipeline.quality.mart_checks and validate_operations, verifying overall pass."""
    _, config_path, dw_result, _ = setup_published_mart(database, tmp_path)
    bundle = load_config(config_path)

    with connect(database) as conn:
        run_uuid = UUID(str(dw_result["run_id"]))
        # 1. Independent Python arithmetic validator
        validation = validate_operations(conn, run_uuid, bundle)
        assert validation["passed"] is True
        assert validation["errors"] == []

    # 2. Mart Quality Report runner (requires an idle connection)
    with connect(database) as conn:
        quality = mart_quality_report(conn, bundle)
        assert quality["passed"] is True
        assert quality["errors"] == []
        assert quality["dw_quality"]["passed"] is True
        assert validation["errors"] == []

        # 2. Mart Quality Report runner
        quality = mart_quality_report(conn, bundle)
        assert quality["passed"] is True
        assert quality["errors"] == []
        assert quality["dw_quality"]["passed"] is True
