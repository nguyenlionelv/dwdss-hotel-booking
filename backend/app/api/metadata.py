"""API router for health checks and dataset metadata."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
import psycopg

from backend.app.core.config import Settings, get_settings
from backend.app.db.connection import read_only_tx
from backend.app.schemas.metadata import (
    ContextStatusSummary,
    CountryItem,
    DateRange,
    HealthResponse,
    MetadataResponse,
)

router = APIRouter(tags=["Metadata & Health"])

SUPPORTED_GRAINS = ["day", "week", "month", "quarter", "year"]

SUPPORTED_MEASURES = [
    "total_bookings",
    "non_canceled_bookings",
    "total_cancellations",
    "cancellation_rate",
    "observed_total_guests",
    "observed_total_stay_nights",
    "avg_party_size",
    "avg_stay_nights",
    "avg_lead_time",
    "avg_adr",
]


def get_db(request: Request):
    """Dependency yielding a database connection within a read-only transaction."""
    dbname = getattr(request.app.state, "dbname", None)
    with read_only_tx(dbname) as conn:
        yield conn


@router.get("/health", response_model=HealthResponse)
def health_check(request: Request, settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Check connectivity and whether Operations Mart is published and matches active DW."""
    dbname = getattr(request.app.state, "dbname", None)
    db_connected = False
    try:
        with read_only_tx(dbname) as conn:
            db_connected = True
            cur = conn.cursor()
            # Verify mart.dataset_state and alignment with dw.active_dataset
            try:
                cur.execute("""
                    SELECT s.dw_run_id, s.data_version, s.published_at,
                           a.run_id AS active_dw_run_id,
                           (a.run_id = s.dw_run_id) AS matches_active_dw
                    FROM mart.dataset_state s
                    LEFT JOIN dw.active_dataset a ON a.singleton_id = s.singleton_id
                    WHERE s.singleton_id = 1
                """)
                row = cur.fetchone()
            except psycopg.errors.UndefinedTable:
                return HealthResponse(
                    status="degraded",
                    db_connected=True,
                    mart_published=False,
                    matches_active_dw=False,
                    message="Database connected, but Operations Mart schema or table does not exist.",
                )

            if not row:
                return HealthResponse(
                    status="degraded",
                    db_connected=True,
                    mart_published=False,
                    matches_active_dw=False,
                    message="Database connected, but Operations Mart is not yet published.",
                )

            matches_active = bool(row["matches_active_dw"])
            return HealthResponse(
                status="healthy" if matches_active else "degraded",
                db_connected=True,
                mart_published=True,
                matches_active_dw=matches_active,
                data_version=str(row["data_version"]),
                dw_run_id=str(row["dw_run_id"]),
                published_at=row["published_at"],
                message=None if matches_active else "Mart data_version does not match active DW run.",
            )
    except psycopg.Error as exc:
        return HealthResponse(
            status="degraded",
            db_connected=db_connected,
            mart_published=False,
            matches_active_dw=False,
            message=f"Database connection error: {exc}",
        )


@router.get("/api/metadata", response_model=MetadataResponse)
def get_metadata(
    conn: psycopg.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MetadataResponse:
    """Return published Operations Mart metadata, available dates, countries, and status summary."""
    cur = conn.cursor()
    # 1. Check published state
    try:
        cur.execute("""
            SELECT s.dw_run_id, s.data_version, s.published_at, s.actual_start, s.actual_end,
                   a.run_id AS active_dw_run_id, (a.run_id = s.dw_run_id) AS matches_active_dw
            FROM mart.dataset_state s
            LEFT JOIN dw.active_dataset a ON a.singleton_id = s.singleton_id
            WHERE s.singleton_id = 1
        """)
        state = cur.fetchone()
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Operations Mart schema or state inaccessible: {exc}",
        )

    if not state or not state["matches_active_dw"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operations Mart dataset is not initialized or out of sync with active DW run.",
        )

    actual_start = state["actual_start"]
    actual_end = state["actual_end"]
    total_days = (actual_end - actual_start).days + 1

    # 2. Gather context status distribution across the mart
    status_columns = [
        "booking_data_status",
        "guest_data_status",
        "holiday_data_status",
        "temperature_status",
        "precipitation_status",
    ]
    status_summary: dict[str, dict[str, int]] = {}
    for col in status_columns:
        cur.execute(f"SELECT {col}, COUNT(*) AS cnt FROM mart.daily_hotel_operations GROUP BY {col}")
        status_summary[col] = {r[col]: r["cnt"] for r in cur.fetchall()}

    # 3. List countries available in the mart
    cur.execute("""
        SELECT DISTINCT country_key, country_code, country_name
        FROM mart.daily_hotel_operations_by_country
        ORDER BY country_code
    """)
    countries = [
        CountryItem(
            country_key=r["country_key"],
            country_code=r["country_code"],
            country_name=r["country_name"],
        )
        for r in cur.fetchall()
    ]

    return MetadataResponse(
        hotel_name=settings.hotel_name,
        location=settings.location,
        timezone=settings.timezone,
        dw_run_id=str(state["dw_run_id"]),
        data_version=str(state["data_version"]),
        published_at=state["published_at"],
        date_range=DateRange(
            actual_start=actual_start.isoformat(),
            actual_end=actual_end.isoformat(),
            total_days=total_days,
        ),
        context_status_summary=ContextStatusSummary(
            booking_data_status=status_summary.get("booking_data_status", {}),
            guest_data_status=status_summary.get("guest_data_status", {}),
            holiday_data_status=status_summary.get("holiday_data_status", {}),
            temperature_status=status_summary.get("temperature_status", {}),
            precipitation_status=status_summary.get("precipitation_status", {}),
        ),
        supported_grains=SUPPORTED_GRAINS,
        supported_measures=SUPPORTED_MEASURES,
        countries=countries,
    )
