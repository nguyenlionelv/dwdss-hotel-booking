"""Pydantic schemas for Operations Mart Reporting endpoints (API-02 / BI-05)."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class ReportPeriodInfo(BaseModel):
    iso_year: int
    iso_week: int
    week_key: str
    week_label: str
    start_date: str
    end_date: str
    calendar_days_count: int
    is_complete_week: bool
    overall_guest_status: str
    total_arrivals: int
    total_departures: int | None = None
    total_room_nights: int
    avg_daily_active_guests: int
    peak_day_date: str
    peak_day_guests: int
    holiday_days_count: int
    weather_Completeness_ratio: float
    weather_completeness_ratio: float = 1.0
    yoy_arrivals_delta: str | None = None
    yoy_room_nights_delta: str | None = None


class WeeklyDemandSummary(BaseModel):
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
    peak_day_date: str
    peak_day_guests: int


class WeeklyDailyLogRow(BaseModel):
    # Canonical fields
    date_key: int
    full_date: str
    day_of_week_num: int
    is_weekend: bool
    is_holiday: bool
    holiday_names: list[str] = Field(default_factory=list)
    temperature_mean: float | None = None
    precipitation: float | None = None
    total_bookings: int
    non_canceled_bookings: int
    total_cancellations: int
    cancellation_rate: float | None = None
    observed_total_adults: int
    observed_total_children: int
    observed_total_babies: int
    observed_total_guests: int
    target_guests: int | None = None
    observed_total_stay_nights: int
    guest_valid_booking_count: int = 0
    stay_valid_booking_count: int = 0
    lead_time_valid_count: int = 0
    adr_valid_count: int = 0
    sum_lead_time: int = 0
    sum_adr: float = 0.0
    avg_party_size: float | None = None
    avg_stay_nights: float | None = None
    avg_lead_time: float | None = None
    avg_adr: float | None = None
    guest_data_status: str

    # UI convenience fields for OperationsReportsPage
    stay_date: str
    date_display: str
    day_of_week: str
    day_type: str
    arrivals: int
    departures: int | None = None
    active_stays: int
    room_nights: int
    active_guests: int
    adr: float
    is_pt_holiday: bool
    holiday_local_name: str | None = None
    weather_temp_mean: float | None = None
    weather_precip_sum: float | None = None
    weather_status: str
    is_peak_day: bool = False


class CapacityShiftSummary(BaseModel):
    report_code: str = "DO-R02"
    weekday_avg_arrivals: int
    weekend_avg_arrivals: int
    weekend_surge_pct: str
    weekday_avg_guests: int
    weekend_avg_guests: int
    front_desk_directive: str
    housekeeping_directive: str
    fb_directive: str


class WeeklyDemandResponse(BaseModel):
    report_id: str = "DO-R01"
    report_code: str = "DO-R01"
    report_name: str = "Weekly Demand Report"
    hotel_name: str = "City Hotel"
    hotel_scope: str = "City Hotel"
    timezone: str = "Europe/Lisbon"
    data_version: str
    dataset_release_id: str
    published_at: datetime | None = None
    period: ReportPeriodInfo
    period_summary: ReportPeriodInfo
    summary: WeeklyDemandSummary
    daily_rows: list[WeeklyDailyLogRow]
    capacity_summary: CapacityShiftSummary


class CapacityGroupBreakdown(BaseModel):
    day_type: str
    days_count: int
    total_arrivals: int
    avg_daily_arrivals: float
    total_room_nights: int
    avg_daily_room_nights: float
    total_active_guests: int
    avg_daily_active_guests: float
    avg_adr: float | None = None
    avg_party_size: float | None = None
    avg_stay_nights: float | None = None


class CapacitySummaryResponse(BaseModel):
    report_id: str = "DO-R02"
    report_code: str = "DO-R02"
    report_name: str = "Operations Capacity Summary"
    hotel_name: str = "City Hotel"
    data_version: str
    iso_year: int
    iso_week: int
    week_key: str
    groups: list[CapacityGroupBreakdown]
    capacity_summary: CapacityShiftSummary
