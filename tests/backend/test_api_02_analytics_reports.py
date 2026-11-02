"""Integration tests for API-02: Analytics & Reports endpoints on Operations Mart."""

from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests/pipeline"))

from backend.app.main import create_app
from test_dw_postgres import database
from tests.marts.test_mart_05_reconciliation import setup_published_mart


def test_unpublished_mart_returns_503_for_analytics_and_reports(database):
    """When mart is not initialized, endpoints should return 503 Service Unavailable."""
    app = create_app(dbname=database)
    client = TestClient(app)

    for path in (
        "/api/analytics/operations/trend",
        "/api/analytics/operations/pivot",
        "/api/analytics/operations/impact",
        "/api/reports/operations/weekly-demand",
        "/api/reports/operations/capacity-summary",
        "/api/reports/operations/export.csv",
    ):
        resp = client.get(path)
        assert resp.status_code == 503, f"Expected 503 on {path}, got {resp.status_code}"


def test_analytics_trend_across_grains_and_filters(database, tmp_path):
    """Verify /api/analytics/operations/trend across all supported grains and slice/dice filters."""
    _, _, dw_res, _ = setup_published_mart(database, tmp_path)
    app = create_app(dbname=database)
    client = TestClient(app)

    # 1. Test all 5 grains
    for grain in ("day", "week", "month", "quarter", "year"):
        res = client.get(f"/api/analytics/operations/trend?grain={grain}")
        assert res.status_code == 200
        body = res.json()
        assert body["grain"] == grain
        assert body["data_version"] == str(dw_res["data_version"])
        assert len(body["series"]) >= 1
        assert body["summary"]["total_bookings"] == sum(r["total_bookings"] for r in body["series"])
        assert body["summary"]["non_canceled_bookings"] == sum(
            r["non_canceled_bookings"] for r in body["series"]
        )
        assert body["summary"]["observed_total_stay_nights"] == sum(
            r["observed_total_stay_nights"] for r in body["series"]
        )

    # 2. Test country slice filter (PRT)
    res_prt = client.get("/api/analytics/operations/trend?grain=day&country_code=PRT")
    assert res_prt.status_code == 200
    prt_body = res_prt.json()
    assert prt_body["filters_applied"]["country_code"] == "PRT"
    assert prt_body["summary"]["total_bookings"] > 0

    # 3. Test invalid grain returns 422
    res_invalid = client.get("/api/analytics/operations/trend?grain=decade")
    assert res_invalid.status_code == 422


def test_analytics_pivot_and_impact_endpoints(database, tmp_path):
    """Verify /api/analytics/operations/pivot and /api/analytics/operations/impact."""
    setup_published_mart(database, tmp_path)
    app = create_app(dbname=database)
    client = TestClient(app)

    # 1. Pivot by country
    res_country = client.get("/api/analytics/operations/pivot?col_dim=country&measure=room_nights")
    assert res_country.status_code == 200
    p_country = res_country.json()
    assert len(p_country["columns"]) >= 2
    assert len(p_country["rows"]) >= 1
    assert p_country["grand_total"] == sum(r["total"] for r in p_country["rows"])

    # 2. Pivot by day_type
    res_daytype = client.get("/api/analytics/operations/pivot?col_dim=day_type&measure=arrivals")
    assert res_daytype.status_code == 200
    p_daytype = res_daytype.json()
    assert p_daytype["columns"] == ["Weekday", "Weekend", "Holiday"]
    assert p_daytype["grand_total"] == sum(r["total"] for r in p_daytype["rows"])

    # 3. Impact endpoint
    res_impact = client.get("/api/analytics/operations/impact")
    assert res_impact.status_code == 200
    impact = res_impact.json()
    assert "holiday_impact" in impact
    assert "weather_impact" in impact
    assert "top_countries" in impact
    assert len(impact["weather_impact"]["bands"]) >= 1
    assert len(impact["top_countries"]) >= 1


def test_reports_weekly_demand_capacity_and_csv_export(database, tmp_path):
    """Verify DO-R01 weekly-demand (and /weekly alias), DO-R02 capacity-summary, and CSV export."""
    setup_published_mart(database, tmp_path)
    app = create_app(dbname=database)
    client = TestClient(app)

    # 1. Weekly demand report via canonical path and alias
    res_w1 = client.get("/api/reports/operations/weekly-demand?week=2017-W31")
    res_w2 = client.get("/api/reports/operations/weekly?week=2017-W31")
    assert res_w1.status_code == 200
    assert res_w2.status_code == 200
    w_data = res_w1.json()
    assert w_data["report_id"] == "DO-R01"
    assert len(w_data["daily_rows"]) == 3
    assert w_data["summary"]["non_canceled_bookings"] == sum(
        r["arrivals"] for r in w_data["daily_rows"]
    )
    assert w_data["summary"]["observed_total_stay_nights"] == sum(
        r["room_nights"] for r in w_data["daily_rows"]
    )

    # 2. Capacity summary (DO-R02)
    res_cap = client.get("/api/reports/operations/capacity-summary?week=2017-W31")
    assert res_cap.status_code == 200
    cap_data = res_cap.json()
    assert cap_data["report_id"] == "DO-R02"
    assert len(cap_data["groups"]) >= 1
    assert "front_desk_directive" in cap_data["capacity_summary"]

    # 3. CSV export
    res_csv = client.get("/api/reports/operations/export.csv?week=2017-W31")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "attachment; filename=" in res_csv.headers["content-disposition"]
    csv_lines = [line for line in res_csv.text.strip().splitlines() if line.strip()]
    # 1 header + 3 daily rows
    assert len(csv_lines) == 4


def test_kpi_reconciliation_between_analytics_and_reports_api(database, tmp_path):
    """Prove BI-05 / API-02 invariant: Same date filter => Same KPI across Analytics and Reports."""
    setup_published_mart(database, tmp_path)
    app = create_app(dbname=database)
    client = TestClient(app)

    r_analytics = client.get(
        "/api/analytics/operations/trend?grain=day&start_date=2017-08-01&end_date=2017-08-03"
    )
    r_report = client.get(
        "/api/reports/operations/weekly-demand?start_date=2017-08-01&end_date=2017-08-03"
    )
    assert r_analytics.status_code == 200
    assert r_report.status_code == 200

    a_sum = r_analytics.json()["summary"]
    rep_sum = r_report.json()["summary"]

    assert a_sum["total_bookings"] == rep_sum["total_bookings"]
    assert a_sum["non_canceled_bookings"] == rep_sum["non_canceled_bookings"]
    assert a_sum["total_cancellations"] == rep_sum["total_cancellations"]
    assert a_sum["observed_total_guests"] == rep_sum["observed_total_guests"]
    assert a_sum["observed_total_stay_nights"] == rep_sum["observed_total_stay_nights"]
    assert a_sum["avg_adr"] == pytest.approx(rep_sum["avg_adr"])
