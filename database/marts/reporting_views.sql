-- ============================================================================
-- BI-05: Standardized Executive Reporting Views & KPI Reconciliation
-- Scope: City Hotel (Lisbon, Portugal — Europe/Lisbon)
-- Target Schema: mart
-- Deliverables:
--   1. mart.operations_weekly_report (DO-R01)
--   2. mart.operations_capacity_summary (DO-R02)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. VIEW: mart.operations_weekly_report (DO-R01 — Weekly Demand Report)
-- Grain: (iso_year, iso_week)
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW mart.operations_weekly_report AS
WITH weekly_aggregates AS (
    SELECT 
        iso_year,
        iso_week,
        min(full_date) AS start_date,
        max(full_date) AS end_date,
        count(*) AS total_days,
        sum(total_bookings) AS total_bookings,
        sum(non_canceled_bookings) AS total_arrivals,
        sum(total_cancellations) AS total_cancellations,
        sum(observed_total_stay_nights) AS total_room_nights,
        sum(observed_total_guests) AS total_active_guests,
        round(sum(observed_total_guests)::numeric / nullif(count(*), 0), 1) AS avg_daily_active_guests,
        round(sum(sum_adr)::numeric / nullif(sum(adr_valid_count), 0), 2) AS avg_adr,
        round(sum(total_cancellations)::numeric / nullif(sum(total_bookings), 0), 4) AS cancellation_rate,
        count(*) FILTER (WHERE is_holiday = true) AS holiday_days_count,
        round(count(*) FILTER (WHERE temperature_status = 'OBSERVED')::numeric / count(*), 4) AS weather_completeness_ratio
    FROM mart.daily_hotel_operations
    GROUP BY iso_year, iso_week
),
weekly_peak_days AS (
    SELECT DISTINCT ON (iso_year, iso_week)
        iso_year,
        iso_week,
        full_date AS peak_day_date,
        observed_total_guests AS peak_day_guests,
        non_canceled_bookings AS peak_day_arrivals
    FROM mart.daily_hotel_operations
    ORDER BY iso_year, iso_week, observed_total_guests DESC, non_canceled_bookings DESC, full_date ASC
)
SELECT 
    w.iso_year,
    w.iso_week,
    concat(w.iso_year, '-W', lpad(w.iso_week::text, 2, '0')) AS week_key,
    concat(w.iso_year, ' - Week ', lpad(w.iso_week::text, 2, '0'), ' (', to_char(w.start_date, 'DD/MM'), ' - ', to_char(w.end_date, 'DD/MM'), ')') AS week_label,
    w.start_date,
    w.end_date,
    w.total_days,
    w.total_bookings,
    w.total_arrivals,
    w.total_cancellations,
    w.cancellation_rate,
    w.total_room_nights,
    w.total_active_guests,
    w.avg_daily_active_guests,
    w.avg_adr,
    w.holiday_days_count,
    w.weather_completeness_ratio,
    p.peak_day_date,
    p.peak_day_guests,
    p.peak_day_arrivals
FROM weekly_aggregates w
JOIN weekly_peak_days p ON p.iso_year = w.iso_year AND p.iso_week = w.iso_week;


-- ----------------------------------------------------------------------------
-- 2. VIEW: mart.operations_capacity_summary (DO-R02 — Capacity & Workload Summary)
-- Grain: (iso_year, iso_week, day_type)
-- Phân loại: Weekday (Mon–Thu) vs Weekend (Fri–Sun) theo chuẩn quản trị khách sạn
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW mart.operations_capacity_summary AS
SELECT 
    iso_year,
    iso_week,
    concat(iso_year, '-W', lpad(iso_week::text, 2, '0')) AS week_key,
    CASE 
        WHEN is_weekend THEN 'Weekend' 
        ELSE 'Weekday' 
    END AS day_type,
    count(*) AS days_count,
    sum(non_canceled_bookings) AS total_arrivals,
    round(sum(non_canceled_bookings)::numeric / nullif(count(*), 0), 1) AS avg_daily_arrivals,
    sum(observed_total_stay_nights) AS total_room_nights,
    round(sum(observed_total_stay_nights)::numeric / nullif(count(*), 0), 1) AS avg_daily_room_nights,
    sum(observed_total_guests) AS total_active_guests,
    round(sum(observed_total_guests)::numeric / nullif(count(*), 0), 1) AS avg_daily_active_guests,
    round(sum(sum_adr)::numeric / nullif(sum(adr_valid_count), 0), 2) AS avg_adr,
    round(sum(observed_total_guests)::numeric / nullif(sum(guest_valid_booking_count), 0), 2) AS avg_party_size,
    round(sum(observed_total_stay_nights)::numeric / nullif(sum(stay_valid_booking_count), 0), 2) AS avg_stay_nights
FROM mart.daily_hotel_operations
GROUP BY iso_year, iso_week, is_weekend;
