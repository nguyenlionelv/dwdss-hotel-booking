"""Pydantic schemas for health and metadata API responses."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="'healthy' or 'degraded'")
    db_connected: bool
    mart_published: bool
    matches_active_dw: bool
    data_version: str | None = None
    dw_run_id: str | None = None
    published_at: datetime | None = None
    message: str | None = None


class DateRange(BaseModel):
    actual_start: str
    actual_end: str
    total_days: int


class CountryItem(BaseModel):
    country_key: int
    country_code: str
    country_name: str


class ContextStatusSummary(BaseModel):
    booking_data_status: dict[str, int]
    guest_data_status: dict[str, int]
    holiday_data_status: dict[str, int]
    temperature_status: dict[str, int]
    precipitation_status: dict[str, int]


class MetadataResponse(BaseModel):
    hotel_name: str
    location: str
    timezone: str
    dw_run_id: str
    data_version: str
    published_at: datetime
    date_range: DateRange
    context_status_summary: ContextStatusSummary
    supported_grains: list[str]
    supported_measures: list[str]
    countries: list[CountryItem]
