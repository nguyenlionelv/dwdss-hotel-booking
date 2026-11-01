"""Tests for API-01: FastAPI health check, DB connection, and Operations Mart metadata endpoints."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]
PIPELINE_TESTS = ROOT / "tests/pipeline"
if str(PIPELINE_TESTS) not in sys.path:
    sys.path.insert(0, str(PIPELINE_TESTS))

from backend.app.core.config import Settings
from backend.app.main import create_app
from pipeline.dw_to_mart.migrations import apply_mart_migration
from pipeline.dw_to_mart.run import run as refresh_mart
from pipeline.source_to_staging.common import connect
from pipeline.source_to_staging.run import run as stage
from pipeline.staging_to_dw.migrations import apply_dw_migrations
from pipeline.staging_to_dw.run import run as load_dw
from test_dw_inputs_postgres import make_sources
from test_dw_postgres import config_for


@pytest.fixture
def disposable_db():
    name = "backend_api_test_" + uuid4().hex[:12]
    with connect() as admin:
        admin.autocommit = True
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield name
    finally:
        with connect() as admin:
            admin.autocommit = True
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def test_health_when_database_connection_fails(monkeypatch):
    """When DB is unreachable, health endpoint reports degraded with db_connected=False."""
    monkeypatch.setenv("POSTGRES_PORT", "59999")
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["db_connected"] is False
    assert data["mart_published"] is False
    assert "Database connection error" in data["message"]


def test_health_and_metadata_when_mart_not_initialized(disposable_db):
    """When DB is connected but mart schema is missing, health is degraded and metadata returns 503."""
    app = create_app(dbname=disposable_db)
    client = TestClient(app)

    # Health check should indicate DB is reachable but mart is not published
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["status"] == "degraded"
    assert health_data["db_connected"] is True
    assert health_data["mart_published"] is False

    # Metadata should return 503 Service Unavailable
    meta_resp = client.get("/api/metadata")
    assert meta_resp.status_code == 503
    assert "inaccessible" in meta_resp.json()["detail"] or "not initialized" in meta_resp.json()["detail"]


def test_health_and_metadata_with_published_mart(disposable_db, tmp_path):
    """Full integration test: published Operations Mart returns healthy and rich metadata."""
    # 1. Setup Staging, DW, and Mart in disposable database
    with connect(disposable_db) as conn:
        conn.execute((ROOT / "database/staging/001_staging.sql").read_text(encoding="utf-8"))
        conn.commit()
        apply_dw_migrations(conn)

    manifest = make_sources(tmp_path)
    stage(manifest, dbname=disposable_db)
    config = config_for(tmp_path, manifest)
    loaded = load_dw(config, dbname=disposable_db)

    with connect(disposable_db) as conn:
        apply_mart_migration(conn)
    refresh_result = refresh_mart(config, dbname=disposable_db)
    assert refresh_result["status"] == "published"

    # 2. Test FastAPI endpoints
    app = create_app(dbname=disposable_db)
    client = TestClient(app)

    # Health check
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["status"] == "healthy"
    assert health_data["db_connected"] is True
    assert health_data["mart_published"] is True
    assert health_data["matches_active_dw"] is True
    assert health_data["data_version"] == loaded["data_version"]
    assert health_data["dw_run_id"] == loaded["run_id"]
    assert health_data["published_at"] is not None

    # Metadata endpoint
    meta_resp = client.get("/api/metadata")
    assert meta_resp.status_code == 200
    meta_data = meta_resp.json()

    assert meta_data["hotel_name"] == "City Hotel"
    assert meta_data["location"] == "Lisbon, Portugal"
    assert meta_data["timezone"] == "Europe/Lisbon"
    assert meta_data["dw_run_id"] == loaded["run_id"]
    assert meta_data["data_version"] == loaded["data_version"]
    assert meta_data["date_range"]["actual_start"] == "2017-08-01"
    assert meta_data["date_range"]["actual_end"] == "2017-08-03"
    assert meta_data["date_range"]["total_days"] == 3

    assert "guest_data_status" in meta_data["context_status_summary"]
    assert meta_data["supported_grains"] == ["day", "week", "month", "quarter", "year"]
    assert "observed_total_guests" in meta_data["supported_measures"]
    assert "total_bookings" in meta_data["supported_measures"]

    country_codes = [c["country_code"] for c in meta_data["countries"]]
    assert len(country_codes) > 0
    assert "PRT" in country_codes or "UNK" in country_codes


def test_status_endpoints_for_future_modules():
    """Ensure placeholder routers for Analytics, Reports, and DSS respond properly."""
    app = create_app()
    client = TestClient(app)

    r_analytics = client.get("/api/analytics/status")
    assert r_analytics.status_code == 200
    assert r_analytics.json()["module"] == "analytics"

    r_reports = client.get("/api/reports/status")
    assert r_reports.status_code == 200
    assert r_reports.json()["module"] == "reports"

    r_dss = client.get("/api/dss/status")
    assert r_dss.status_code == 200
    assert r_dss.json()["module"] == "dss"
