-- ============================================================================
-- BI-01: OLAP Operations Queries — Portuguese Holiday & Weather Impact
-- Scope: City Hotel (Lisbon, Portugal — Europe/Lisbon)
-- Target Table: mart.daily_hotel_operations
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. HOLIDAY IMPACT ANALYSIS (DO-A03)
-- Đo lường tác động của các ngày Lễ Quốc gia Bồ Đào Nha lên Nhu cầu và Giá phòng
-- ----------------------------------------------------------------------------

-- 1A: So sánh tổng quan Ngày Lễ vs Ngày Thường trên toàn bộ 793 ngày
WITH holiday_comparison AS (
    SELECT 
        CASE 
            WHEN is_holiday THEN 'Holiday Period' 
            ELSE 'Non-Holiday Period' 
        END AS day_category,
        count(*) AS total_days,
        sum(non_canceled_bookings) AS total_arrivals,
        sum(observed_total_stay_nights) AS total_room_nights,
        sum(observed_total_guests) AS total_guests,
        sum(sum_adr) AS total_adr_sum,
        sum(adr_valid_count) AS total_adr_count
    FROM mart.daily_hotel_operations
    GROUP BY is_holiday
)
SELECT 
    day_category,
    total_days,
    round(total_room_nights::numeric / nullif(total_days, 0), 1) AS avg_room_nights_per_day,
    round(total_arrivals::numeric / nullif(total_days, 0), 1) AS avg_arrivals_per_day,
    round(total_guests::numeric / nullif(total_days, 0), 1) AS avg_guests_per_day,
    round(total_adr_sum::numeric / nullif(total_adr_count, 0), 2) AS avg_adr
FROM holiday_comparison;

-- 1B: Danh sách các Ngày Lễ Quốc gia Bồ Đào Nha tạo lực đẩy nhu cầu cao nhất (Top Holiday Lift)
SELECT 
    full_date,
    holiday_names,
    to_char(full_date, 'Dy') AS day_name,
    non_canceled_bookings AS arrivals,
    observed_total_stay_nights AS room_nights,
    observed_total_guests AS active_guests,
    avg_adr,
    round(((observed_total_stay_nights - 304.2) / 304.2 * 100)::numeric, 1) AS lift_pct_vs_annual_mean
FROM mart.daily_hotel_operations
WHERE is_holiday = true
ORDER BY observed_total_stay_nights DESC
LIMIT 10;


-- ----------------------------------------------------------------------------
-- 2. WEATHER CORRELATION ANALYSIS (DO-A04)
-- Tương quan giữa Nhiệt độ trung bình / Lượng mưa và Nhu cầu đêm phòng tại Lisbon
-- ----------------------------------------------------------------------------

-- 2A: Phân dải Nhiệt độ (Temperature Bands) & Tương quan Công suất
WITH weather_bands AS (
    SELECT 
        CASE 
            WHEN temperature_mean >= 22.0 AND (precipitation IS NULL OR precipitation < 1.0) 
                THEN '1. Nắng ấm lý tưởng (>= 22°C, khô ráo)'
            WHEN temperature_mean BETWEEN 15.0 AND 21.99 AND (precipitation IS NULL OR precipitation < 2.0)
                THEN '2. Ôn hòa dễ chịu (15°C - 21.9°C, ít mưa)'
            WHEN temperature_mean < 15.0 OR precipitation >= 5.0
                THEN '3. Lạnh hoặc Mưa mùa đông (< 15°C hoặc >= 5mm mưa)'
            ELSE '4. Thời tiết khác / Mưa rào'
        END AS weather_band,
        observed_total_stay_nights,
        observed_total_guests,
        non_canceled_bookings,
        avg_adr
    FROM mart.daily_hotel_operations
)
SELECT 
    weather_band,
    count(*) AS observed_days_count,
    round(avg(observed_total_stay_nights), 1) AS avg_daily_room_nights,
    round(avg(observed_total_guests), 1) AS avg_daily_active_guests,
    round(avg(non_canceled_bookings), 1) AS avg_daily_arrivals,
    round(avg(avg_adr), 2) AS avg_adr,
    round((avg(observed_total_stay_nights) / nullif((SELECT avg(observed_total_stay_nights) FROM mart.daily_hotel_operations), 0))::numeric, 2) AS demand_index
FROM weather_bands
GROUP BY weather_band
ORDER BY weather_band;

-- 2B: Độ hoàn thiện dữ liệu thời tiết (Weather Data Completeness Ratio)
SELECT 
    count(*) AS total_mart_days,
    count(*) FILTER (WHERE temperature_status = 'OBSERVED') AS valid_temp_days,
    count(*) FILTER (WHERE precipitation_status = 'OBSERVED') AS valid_precip_days,
    round(count(*) FILTER (WHERE temperature_status = 'OBSERVED')::numeric / count(*), 4) AS temp_completeness_ratio
FROM mart.daily_hotel_operations;
