-- ============================================================================
-- BI-05: KPI Reconciliation Validation Queries
-- Purpose: Prove that Same Filter => Same KPI between Analytics and Reports
-- Scope: City Hotel (Lisbon, Portugal — Europe/Lisbon)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Test 1: Cross-view Reconciliation between Daily Mart and Weekly Reporting View
-- Mục tiêu: Chứng minh tổng toàn bộ các chỉ số của tất cả các tuần trong
-- mart.operations_weekly_report khớp tuyệt đối với mart.daily_hotel_operations.
-- ----------------------------------------------------------------------------

WITH daily_totals AS (
    SELECT 
        sum(total_bookings) AS d_total_bookings,
        sum(non_canceled_bookings) AS d_total_arrivals,
        sum(total_cancellations) AS d_total_cancellations,
        sum(observed_total_stay_nights) AS d_total_room_nights,
        sum(observed_total_guests) AS d_total_active_guests
    FROM mart.daily_hotel_operations
),
weekly_view_totals AS (
    SELECT 
        sum(total_bookings) AS w_total_bookings,
        sum(total_arrivals) AS w_total_arrivals,
        sum(total_cancellations) AS w_total_cancellations,
        sum(total_room_nights) AS w_total_room_nights,
        sum(total_active_guests) AS w_total_active_guests
    FROM mart.operations_weekly_report
)
SELECT 
    d.d_total_bookings,
    w.w_total_bookings,
    (d.d_total_bookings - w.w_total_bookings) AS diff_bookings,

    d.d_total_arrivals,
    w.w_total_arrivals,
    (d.d_total_arrivals - w.w_total_arrivals) AS diff_arrivals,

    d.d_total_room_nights,
    w.w_total_room_nights,
    (d.d_total_room_nights - w.w_total_room_nights) AS diff_room_nights,

    d.d_total_active_guests,
    w.w_total_active_guests,
    (d.d_total_active_guests - w.w_total_active_guests) AS diff_guests,

    CASE 
        WHEN (d.d_total_bookings = w.w_total_bookings) 
         AND (d.d_total_arrivals = w.w_total_arrivals)
         AND (d.d_total_room_nights = w.w_total_room_nights)
         AND (d.d_total_active_guests = w.w_total_active_guests)
        THEN 'PASSED: 100% RECONCILED'
        ELSE 'FAILED: MISMATCH DETECTED'
    END AS reconciliation_status
FROM daily_totals d
CROSS JOIN weekly_view_totals w;


-- ----------------------------------------------------------------------------
-- Test 2: Specific Period Verification (Example: 2017 Week 32: 07/08/2017 - 13/08/2017)
-- Mục tiêu: Kiểm tra đối soát cụ thể trên 1 tuần báo cáo thực tế
-- ----------------------------------------------------------------------------

WITH daily_filter AS (
    SELECT 
        count(*) AS days_count,
        sum(total_bookings) AS daily_bookings,
        sum(non_canceled_bookings) AS daily_arrivals,
        sum(observed_total_stay_nights) AS daily_room_nights,
        sum(observed_total_guests) AS daily_guests,
        round(sum(sum_adr)::numeric / nullif(sum(adr_valid_count), 0), 2) AS daily_avg_adr
    FROM mart.daily_hotel_operations
    WHERE full_date BETWEEN '2017-08-07' AND '2017-08-13'
),
report_view_filter AS (
    SELECT 
        total_days AS view_days,
        total_bookings AS view_bookings,
        total_arrivals AS view_arrivals,
        total_room_nights AS view_room_nights,
        total_active_guests AS view_guests,
        avg_adr AS view_avg_adr
    FROM mart.operations_weekly_report
    WHERE iso_year = 2017 AND iso_week = 32
)
SELECT 
    d.days_count, r.view_days,
    d.daily_arrivals, r.view_arrivals,
    d.daily_room_nights, r.view_room_nights,
    d.daily_guests, r.view_guests,
    d.daily_avg_adr, r.view_avg_adr,
    CASE 
        WHEN d.daily_arrivals = r.view_arrivals 
         AND d.daily_room_nights = r.view_room_nights
         AND d.daily_guests = r.view_guests
         AND d.daily_avg_adr = r.view_avg_adr
        THEN 'PASSED: SAME FILTER EQUALS SAME KPI'
        ELSE 'FAILED: KPI MISMATCH'
    END AS period_kpi_reconciliation_result
FROM daily_filter d
CROSS JOIN report_view_filter r;
