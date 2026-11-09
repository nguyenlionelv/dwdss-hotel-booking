"""Pydantic schemas for Operations Mart Analytics endpoints (API-02 / BI-01)."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class TrendFiltersApplied(BaseModel):
    start_date: str
    end_date: str
    grain: str
    country_code: str | None = None
    day_type: str | None = None
    is_weekend: bool | None = None
    is_holiday: bool | None = None


class TrendCoverageSummary(BaseModel):
    calendar_days_count: int
    booking_complete_days: int
    guest_complete_days: int
    guest_partial_days: int
    overall_guest_status: str
    rejected_booking_count: int
    guest_ineligible_booking_count: int


class PeakDemandDayItem(BaseModel):
    full_date: str
    observed_total_guests: int
    observed_total_stay_nights: int
    guest_data_status: str


class TrendSummary(BaseModel):
    # Canonical fields
    total_bookings: int
    non_canceled_bookings: int
    total_cancellations: int
    cancellation_rate: float | None = None
    observed_total_adults: int
    observed_total_children: int
    observed_total_babies: int
    observed_total_guests: int
    target_guests: int | None = None
    strict_avg_guests_per_day: float | None = None
    observed_avg_guests_per_day: float | None = None
    observed_total_stay_nights: int
    avg_party_size: float | None = None
    avg_stay_nights: float | None = None
    avg_lead_time: float | None = None
    avg_adr: float | None = None
    peak_demand_days: list[PeakDemandDayItem] = Field(default_factory=list)

    # UI convenience fields for OperationsAnalyticsPage
    total_arrivals: int
    total_room_nights: int
    avg_daily_active_guests: int
    peak_period: str
    peak_room_nights: int


class TrendSeriesItem(BaseModel):
    period_key: str
    period_label: str
    period_start: str
    period_end: str
    calendar_days_count: int
    guest_data_status: str
    total_bookings: int
    non_canceled_bookings: int
    total_cancellations: int
    cancellation_rate: float | None = None
    observed_total_guests: int
    target_guests: int | None = None
    strict_avg_guests_per_day: float | None = None
    observed_avg_guests_per_day: float | None = None
    observed_total_stay_nights: int
    avg_party_size: float | None = None
    avg_stay_nights: float | None = None
    avg_lead_time: float | None = None
    avg_adr: float | None = None

    # UI convenience fields
    arrivals: int
    room_nights: int
    active_guests: int
    adr: float
    is_holiday_period: bool = False
    is_peak: bool = False


class TrendResponse(BaseModel):
    data_version: str
    grain: str
    filters_applied: TrendFiltersApplied
    coverage: TrendCoverageSummary
    summary: TrendSummary
    series: list[TrendSeriesItem]


class PivotColumnDef(BaseModel):
    col_key: str
    col_label: str


class PivotChildRow(BaseModel):
    row_key: str
    row_label: str
    values: dict[str, float | int]
    cells: dict[str, float | int]
    total: float | int
    row_total: float | int


class PivotRowItem(BaseModel):
    row_key: str
    row_label: str
    values: dict[str, float | int]
    cells: dict[str, float | int]
    total: float | int
    row_total: float | int
    is_expandable: bool = False
    is_highlighted: bool = False
    children: list[PivotChildRow] | None = None


class PivotResponse(BaseModel):
    data_version: str
    row_dim: str
    col_dim: str
    measure: str
    columns: list[str]
    column_defs: list[PivotColumnDef]
    rows: list[PivotRowItem]
    column_totals: dict[str, float | int]
    grand_total: float | int


class HolidayGroupItem(BaseModel):
    group_key: str
    group_label: str
    days_count: int
    total_bookings: int
    non_canceled_bookings: int
    cancellation_rate: float | None = None
    observed_total_guests: int
    observed_avg_guests_per_day: float | None = None
    observed_total_stay_nights: int
    avg_stay_nights: float | None = None
    avg_party_size: float | None = None
    avg_adr: float | None = None


class HolidayHighlightItem(BaseModel):
    date: str
    local_name: str
    lift_pct: str


class HolidayImpactSummary(BaseModel):
    holiday_days_count: int
    non_holiday_days_count: int
    holiday_avg_room_nights: float
    non_holiday_avg_room_nights: float
    lift_pct: float
    holiday_avg_arrivals: float
    non_holiday_avg_arrivals: float
    holiday_avg_adr: float
    non_holiday_avg_adr: float
    upcoming_holidays: list[HolidayHighlightItem] = Field(default_factory=list)
    groups: list[HolidayGroupItem] = Field(default_factory=list)


class WeatherBandItem(BaseModel):
    band_label: str
    days_count: int
    avg_room_nights: float
    avg_active_guests: float
    avg_arrivals: float
    avg_adr: float
    demand_index: float


class WeatherImpactSummary(BaseModel):
    bands: list[WeatherBandItem]
    completeness_ratio: float
    missing_days: int
    insight: str


class TopCountryImpactItem(BaseModel):
    code: str
    name: str
    bookings: int
    guests: int
    room_nights: int
    share_pct: float
    yoy_growth: str | None = None


class ImpactResponse(BaseModel):
    data_version: str
    holiday_impact: HolidayImpactSummary
    weather_impact: WeatherImpactSummary
    top_countries: list[TopCountryImpactItem]
