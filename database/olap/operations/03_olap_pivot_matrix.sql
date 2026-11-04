-- ============================================================================
-- BI-01: OLAP Operations Queries — Multi-Dimensional Pivot Matrix
-- Scope: City Hotel (Lisbon, Portugal — Europe/Lisbon)
-- Target Table: mart.daily_hotel_operations & mart.daily_hotel_operations_by_country
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. PIVOT MATRIX 1: Time Dimension x Day Type (Weekday / Weekend / Holiday)
-- Hàng = Quý (Year, Quarter)
-- Cột = Loại ngày (Weekday, Weekend, Holiday)
-- Measure = Tổng đêm phòng (Room Nights) & Lượt đến (Arrivals)
-- ----------------------------------------------------------------------------

SELECT 
    year,
    quarter,
    concat(year, ' - Q', quarter) AS time_period,
    
    -- Measure 1: Room Nights theo loại ngày
    coalesce(sum(observed_total_stay_nights) FILTER (WHERE NOT is_weekend AND NOT is_holiday), 0) AS weekday_room_nights,
    coalesce(sum(observed_total_stay_nights) FILTER (WHERE is_weekend AND NOT is_holiday), 0) AS weekend_room_nights,
    coalesce(sum(observed_total_stay_nights) FILTER (WHERE is_holiday), 0) AS holiday_room_nights,
    coalesce(sum(observed_total_stay_nights), 0) AS total_room_nights,

    -- Measure 2: Arrivals theo loại ngày
    coalesce(sum(non_canceled_bookings) FILTER (WHERE NOT is_weekend AND NOT is_holiday), 0) AS weekday_arrivals,
    coalesce(sum(non_canceled_bookings) FILTER (WHERE is_weekend AND NOT is_holiday), 0) AS weekend_arrivals,
    coalesce(sum(non_canceled_bookings) FILTER (WHERE is_holiday), 0) AS holiday_arrivals,
    coalesce(sum(non_canceled_bookings), 0) AS total_arrivals

FROM mart.daily_hotel_operations
GROUP BY year, quarter
ORDER BY year, quarter;


-- ----------------------------------------------------------------------------
-- 2. PIVOT MATRIX 2: Time Dimension x Top Geographic Markets
-- Hàng = Quý (Year, Quarter)
-- Cột = Top 5 thị trường quốc tế (PRT, FRA, DEU, GBR, ESP) + OTHER
-- Measure = Tổng đêm phòng (Room Nights)
-- ----------------------------------------------------------------------------

SELECT 
    d.year,
    d.quarter,
    concat(d.year, ' - Q', d.quarter) AS time_period,
    
    -- Cột theo từng Quốc gia
    coalesce(sum(m.observed_total_stay_nights) FILTER (WHERE m.country_code = 'PRT'), 0) AS prt_portugal,
    coalesce(sum(m.observed_total_stay_nights) FILTER (WHERE m.country_code = 'FRA'), 0) AS fra_france,
    coalesce(sum(m.observed_total_stay_nights) FILTER (WHERE m.country_code = 'DEU'), 0) AS deu_germany,
    coalesce(sum(m.observed_total_stay_nights) FILTER (WHERE m.country_code = 'GBR'), 0) AS gbr_uk,
    coalesce(sum(m.observed_total_stay_nights) FILTER (WHERE m.country_code = 'ESP'), 0) AS esp_spain,
    coalesce(sum(m.observed_total_stay_nights) FILTER (WHERE m.country_code NOT IN ('PRT', 'FRA', 'DEU', 'GBR', 'ESP')), 0) AS other_markets,
    
    -- Tổng cộng dòng (Row Total)
    coalesce(sum(m.observed_total_stay_nights), 0) AS total_room_nights

FROM mart.daily_hotel_operations_by_country m
JOIN dw.dim_date d ON d.date_key = m.date_key
GROUP BY d.year, d.quarter
ORDER BY d.year, d.quarter;
