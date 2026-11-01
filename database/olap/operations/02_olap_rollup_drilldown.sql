-- ============================================================================
-- BI-01: OLAP Operations Queries — Roll-up & Drill-down Operators
-- Scope: City Hotel (Lisbon, Portugal — Europe/Lisbon)
-- Target Table: mart.daily_hotel_operations
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. ROLL-UP OPERATOR
-- Tổng hợp dữ liệu từ mức chi tiết lên mức cao hơn theo phân cấp thời gian:
-- Phân cấp: Ngày (Daily) -> Tuần ISO (Weekly) -> Tháng (Monthly) -> Quý (Quarterly) -> Năm (Yearly)
-- ----------------------------------------------------------------------------

-- Roll-up 1A: Tổng hợp từ Tháng -> Quý -> Năm bằng GROUP BY ROLLUP
-- Tự động sinh dòng tổng phụ cho từng Quý, từng Năm và Dòng tổng cộng toàn kỳ
SELECT 
    coalesce(year::text, 'ALL YEARS') AS year_label,
    coalesce(quarter::text, 'ALL QUARTERS') AS quarter_label,
    coalesce(month::text, 'ALL MONTHS') AS month_label,
    count(*) AS total_days,
    sum(total_bookings) AS total_bookings,
    sum(non_canceled_bookings) AS arrivals,
    sum(observed_total_stay_nights) AS room_nights,
    sum(observed_total_guests) AS active_guests,
    round(sum(sum_adr)::numeric / nullif(sum(adr_valid_count), 0), 2) AS reconciled_avg_adr
FROM mart.daily_hotel_operations
GROUP BY ROLLUP(year, quarter, month)
ORDER BY year NULLS LAST, quarter NULLS LAST, month NULLS LAST;

-- Roll-up 1B: Tổng hợp theo Tuần ISO (iso_year, iso_week)
-- Phục vụ chuyển tiếp dữ liệu mượt mà sang Báo cáo Vận hành Tuần (DO-R01)
SELECT 
    iso_year,
    iso_week,
    min(full_date) AS week_start_date,
    max(full_date) AS week_end_date,
    count(*) AS days_in_week,
    sum(non_canceled_bookings) AS weekly_arrivals,
    sum(observed_total_stay_nights) AS weekly_room_nights,
    sum(observed_total_guests) AS weekly_active_guests,
    round(sum(observed_total_guests)::numeric / nullif(count(*), 0), 2) AS avg_guests_per_day,
    count(*) FILTER (WHERE is_holiday = true) AS holiday_count
FROM mart.daily_hotel_operations
GROUP BY iso_year, iso_week
ORDER BY iso_year, iso_week;


-- ----------------------------------------------------------------------------
-- 2. DRILL-DOWN OPERATOR
-- Đi sâu từ mức tổng quát xuống mức chi tiết, giữ nguyên bộ lọc và không làm lệch tổng
-- Phân cấp: Năm 2016 -> Quý 3 (Mùa hè) -> Tháng 8 (Peak Month) -> Từng ngày (31 ngày)
-- ----------------------------------------------------------------------------

-- Bước 1: Mức Năm (Year 2016)
SELECT 
    year,
    count(*) AS days,
    sum(non_canceled_bookings) AS arrivals,
    sum(observed_total_stay_nights) AS room_nights,
    round(sum(sum_adr)::numeric / nullif(sum(adr_valid_count), 0), 2) AS avg_adr
FROM mart.daily_hotel_operations
WHERE year = 2016
GROUP BY year;

-- Bước 2: Drill-down xuống Quý 3/2016 (Peak Quarter)
SELECT 
    year,
    quarter,
    count(*) AS days,
    sum(non_canceled_bookings) AS arrivals,
    sum(observed_total_stay_nights) AS room_nights,
    round(sum(sum_adr)::numeric / nullif(sum(adr_valid_count), 0), 2) AS avg_adr
FROM mart.daily_hotel_operations
WHERE year = 2016 AND quarter = 3
GROUP BY year, quarter;

-- Bước 3: Drill-down tiếp xuống Tháng 8/2016 (Peak Month)
SELECT 
    year,
    quarter,
    month,
    count(*) AS days,
    sum(non_canceled_bookings) AS arrivals,
    sum(observed_total_stay_nights) AS room_nights,
    round(sum(sum_adr)::numeric / nullif(sum(adr_valid_count), 0), 2) AS avg_adr
FROM mart.daily_hotel_operations
WHERE year = 2016 AND month = 8
GROUP BY year, quarter, month;

-- Bước 4: Drill-down sâu nhất xuống từng ngày trong Tháng 8/2016 (31 ngày chi tiết)
-- Quan sát từng đỉnh sóng công suất, ngày lễ Assumption of Mary (15/08) và các ngày cuối tuần
SELECT 
    full_date,
    day_of_week,
    CASE 
        WHEN is_weekend THEN 'Weekend' 
        ELSE 'Weekday' 
    END AS day_type,
    is_holiday,
    holiday_names,
    temperature_mean,
    precipitation,
    non_canceled_bookings AS arrivals,
    observed_total_stay_nights AS room_nights,
    observed_total_guests AS active_guests,
    avg_adr
FROM mart.daily_hotel_operations
WHERE year = 2016 AND month = 8
ORDER BY full_date;
