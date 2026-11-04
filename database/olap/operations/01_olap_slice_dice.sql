-- ============================================================================
-- BI-01: OLAP Operations Queries — Slice & Dice Operators
-- Scope: City Hotel (Lisbon, Portugal — Europe/Lisbon)
-- Target Table: mart.daily_hotel_operations & mart.daily_hotel_operations_by_country
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. SLICE OPERATOR
-- Cố định một chiều phân tích (Dimension) để quan sát sự biến thiên của các chỉ số.
-- ----------------------------------------------------------------------------

-- Slice 1A: Cố định Năm 2016 — Xem xu hướng nhu cầu theo từng Tháng
SELECT 
    year,
    month,
    to_char(min(full_date), 'Mon YYYY') AS period_label,
    count(*) AS total_days,
    sum(total_bookings) AS total_bookings,
    sum(non_canceled_bookings) AS non_canceled_arrivals,
    sum(total_cancellations) AS cancellations,
    round(sum(total_cancellations)::numeric / nullif(sum(total_bookings), 0), 4) AS cancellation_rate,
    sum(observed_total_stay_nights) AS total_room_nights,
    sum(observed_total_guests) AS total_active_guests,
    round(sum(observed_total_guests)::numeric / nullif(count(*), 0), 2) AS avg_guests_per_day,
    round(sum(sum_adr)::numeric / nullif(sum(adr_valid_count), 0), 2) AS avg_adr
FROM mart.daily_hotel_operations
WHERE year = 2016
GROUP BY year, month
ORDER BY year, month;

-- Slice 1B: Cố định Loại ngày — Chỉ xét các ngày Cuối tuần (Weekend: Thứ Sáu - Chủ Nhật)
SELECT 
    year,
    quarter,
    count(*) AS weekend_days,
    sum(non_canceled_bookings) AS weekend_arrivals,
    sum(observed_total_stay_nights) AS weekend_room_nights,
    round(sum(observed_total_stay_nights)::numeric / nullif(count(*), 0), 2) AS avg_weekend_room_nights_per_day,
    round(sum(sum_adr)::numeric / nullif(sum(adr_valid_count), 0), 2) AS avg_weekend_adr
FROM mart.daily_hotel_operations
WHERE is_weekend = true
GROUP BY year, quarter
ORDER BY year, quarter;

-- Slice 1C: Cố định Chiều Quốc gia — Chỉ xét thị trường nội địa Bồ Đào Nha (PRT)
SELECT 
    year,
    quarter,
    country_code,
    country_name,
    sum(total_bookings) AS prt_total_bookings,
    sum(non_canceled_bookings) AS prt_arrivals,
    sum(observed_total_stay_nights) AS prt_room_nights,
    sum(observed_total_guests) AS prt_guests
FROM mart.daily_hotel_operations_by_country
WHERE country_code = 'PRT'
GROUP BY year, quarter, country_code, country_name
ORDER BY year, quarter;


-- ----------------------------------------------------------------------------
-- 2. DICE OPERATOR
-- Cắt khối dữ liệu (Dice) bằng cách lọc đồng thời nhiều chiều/điều kiện logic.
-- ----------------------------------------------------------------------------

-- Dice 2A: Quý 3 Mùa Hè 2016 (Peak Season) + Cuối tuần (is_weekend) + Ngày có Lễ PT
SELECT 
    full_date,
    day_of_week,
    holiday_names,
    temperature_mean,
    precipitation,
    non_canceled_bookings AS arrivals,
    observed_total_stay_nights AS room_nights,
    observed_total_guests AS active_guests,
    avg_adr
FROM mart.daily_hotel_operations
WHERE year = 2016 
  AND quarter = 3
  AND is_weekend = true
  AND is_holiday = true
ORDER BY full_date;

-- Dice 2B: Ngày thường (Weekday) + Không mưa (precipitation = 0) + Nhiệt độ ấm (> 22°C)
-- Đo lường hiệu suất vận hành cơ sở trong điều kiện thời tiết lý tưởng tại Lisbon
SELECT 
    year,
    quarter,
    count(*) AS ideal_weather_weekdays,
    sum(non_canceled_bookings) AS arrivals,
    sum(observed_total_stay_nights) AS room_nights,
    round(sum(observed_total_stay_nights)::numeric / nullif(count(*), 0), 2) AS avg_daily_room_nights,
    round(sum(sum_adr)::numeric / nullif(sum(adr_valid_count), 0), 2) AS avg_adr
FROM mart.daily_hotel_operations
WHERE is_weekend = false
  AND precipitation = 0
  AND temperature_mean >= 22.0
GROUP BY year, quarter
ORDER BY year, quarter;
