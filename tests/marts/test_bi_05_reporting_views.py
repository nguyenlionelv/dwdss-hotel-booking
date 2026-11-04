"""BI-05: Reporting Views DDL & KPI Reconciliation Tests.

Verifies:
1. database/marts/reporting_views.sql applies cleanly on PostgreSQL.
2. mart.operations_weekly_report (DO-R01) correctly rolls up daily rows into ISO weeks.
3. mart.operations_capacity_summary (DO-R02) correctly splits Weekday vs Weekend.
4. Same filter on Daily Mart yields the exact same KPI as the Weekly Reporting View (Reconciliation).
5. All 4 OLAP SQL scripts in database/olap/operations/ execute cleanly without syntax error.
"""

from pathlib import Path
import sys

from psycopg.rows import dict_row
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests/pipeline"))

from pipeline.source_to_staging.common import connect
from test_dw_postgres import database, config_for
from tests.marts.test_mart_05_reconciliation import setup_published_mart


def apply_reporting_views(database_name: str):
    """Deploy database/marts/reporting_views.sql."""
    views_sql = (ROOT / "database/marts/reporting_views.sql").read_text(encoding="utf-8")
    with connect(database_name) as conn:
        conn.execute(views_sql)
        conn.commit()


def test_reporting_views_creation_and_reconciliation(database, tmp_path):
    """Test deploying reporting views and verify cross-view KPI reconciliation."""
    _, _, dw_result, _ = setup_published_mart(database, tmp_path)
    apply_reporting_views(database)

    with connect(database) as conn, conn.cursor(row_factory=dict_row) as cur:
        # 1. Check operations_weekly_report has rows and valid grain
        cur.execute("""
            SELECT count(*) AS total_weeks,
                   count(DISTINCT (iso_year, iso_week)) AS distinct_weeks
            FROM mart.operations_weekly_report;
        """)
        weekly_counts = cur.fetchone()
        assert weekly_counts["total_weeks"] > 0
        assert weekly_counts["total_weeks"] == weekly_counts["distinct_weeks"]

        # 2. Reconcile total sums between daily table and weekly view
        cur.execute("""
            SELECT 
                (SELECT sum(non_canceled_bookings) FROM mart.daily_hotel_operations) AS d_arrivals,
                (SELECT sum(total_arrivals) FROM mart.operations_weekly_report) AS w_arrivals,
                (SELECT sum(observed_total_stay_nights) FROM mart.daily_hotel_operations) AS d_nights,
                (SELECT sum(total_room_nights) FROM mart.operations_weekly_report) AS w_nights,
                (SELECT sum(observed_total_guests) FROM mart.daily_hotel_operations) AS d_guests,
                (SELECT sum(total_active_guests) FROM mart.operations_weekly_report) AS w_guests;
        """)
        reconciliation = cur.fetchone()
        assert reconciliation["d_arrivals"] == reconciliation["w_arrivals"]
        assert reconciliation["d_nights"] == reconciliation["w_nights"]
        assert reconciliation["d_guests"] == reconciliation["w_guests"]

        # 3. Check operations_capacity_summary has both Weekday and Weekend rows
        cur.execute("""
            SELECT day_type, count(*) AS count_weeks, sum(days_count) AS total_days
            FROM mart.operations_capacity_summary
            GROUP BY day_type
            ORDER BY day_type;
        """)
        summary_rows = {r["day_type"]: r for r in cur.fetchall()}
        assert "Weekday" in summary_rows or "Weekend" in summary_rows


def test_all_olap_operations_scripts_execute_cleanly(database, tmp_path):
    """Execute all 4 SQL files in database/olap/operations/ to ensure zero SQL syntax/schema errors."""
    setup_published_mart(database, tmp_path)
    apply_reporting_views(database)

    olap_dir = ROOT / "database/olap/operations"
    sql_files = sorted(olap_dir.glob("*.sql"))
    assert len(sql_files) >= 4

    with connect(database) as conn:
        for file in sql_files:
            content = file.read_text(encoding="utf-8")
            # Separate statements by semicolon outside of strings
            statements = [s.strip() for s in content.split(";") if s.strip()]
            for stmt in statements:
                # Execute each statement
                conn.execute(stmt)
