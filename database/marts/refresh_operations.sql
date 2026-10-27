-- One aggregate pass at both grains; context joins happen after aggregation.
CREATE TEMP TABLE operations_candidate ON COMMIT DROP AS
WITH aggregates AS (
    SELECT f.date_key,f.country_key,grouping(f.country_key)=1 AS is_daily,
           count(*) AS total_bookings,
           count(*) FILTER (WHERE is_canceled=0) AS non_canceled_bookings,
           count(*) FILTER (WHERE is_canceled=1) AS total_cancellations,
           count(*) FILTER (WHERE is_canceled=0 AND guest_eligible) AS guest_valid_booking_count,
           count(*) FILTER (WHERE is_canceled=0 AND stay_eligible) AS stay_valid_booking_count,
           count(*) FILTER (WHERE is_canceled=0 AND lead_time IS NOT NULL) AS lead_time_valid_count,
           count(*) FILTER (WHERE is_canceled=0 AND adr IS NOT NULL) AS adr_valid_count,
           sum(adults) FILTER (WHERE is_canceled=0 AND guest_eligible) AS observed_total_adults,
           sum(children) FILTER (WHERE is_canceled=0 AND guest_eligible) AS observed_total_children,
           sum(babies) FILTER (WHERE is_canceled=0 AND guest_eligible) AS observed_total_babies,
           sum(total_guests) FILTER (WHERE is_canceled=0 AND guest_eligible) AS observed_total_guests,
           sum(total_stay_nights) FILTER (WHERE is_canceled=0 AND stay_eligible) AS observed_total_stay_nights,
           sum(lead_time) FILTER (WHERE is_canceled=0 AND lead_time IS NOT NULL) AS sum_lead_time,
           sum(adr) FILTER (WHERE is_canceled=0 AND adr IS NOT NULL) AS sum_adr
    FROM dw.fact_booking f WHERE f.dw_run_id=%(run_id)s
    GROUP BY GROUPING SETS ((f.date_key),(f.date_key,f.country_key))
), countries AS (
    SELECT c.country_key,c.country_code,c.country_name
    FROM dw.dim_country c
    WHERE c.country_key=0 OR EXISTS (
        SELECT 1 FROM dw.fact_booking f WHERE f.country_key=c.country_key AND f.dw_run_id=%(run_id)s)
), axes AS (
    SELECT NULL::integer AS country_key,NULL::text AS country_code,NULL::text AS country_name,true AS is_daily
    UNION ALL SELECT country_key,country_code,country_name,false FROM countries
), joined AS (
    SELECT d.date_key,d.full_date,d.year,d.quarter,d.month,d.iso_year,d.iso_week,d.day_of_week,d.is_weekend,
           %(data_version)s::uuid AS data_version,
           x.is_holiday,x.has_national_holiday,x.has_lisboa_holiday,x.holiday_names,
           x.temperature_mean,x.precipitation,x.holiday_data_status,x.temperature_status,x.precipitation_status,
           q.booking_data_status,q.guest_data_status,q.stay_data_status,
           q.rejected_booking_count,q.guest_ineligible_booking_count,q.stay_ineligible_booking_count,
           c.country_key,c.country_code,c.country_name,c.is_daily,
           (v.coverage_status='COMPLETE' AND q.rejected_booking_count=0) AS allow_empty,
           coalesce(a.total_bookings,0) AS n,coalesce(a.non_canceled_bookings,0) AS b,
           coalesce(a.total_cancellations,0) AS canceled,
           coalesce(a.guest_valid_booking_count,0) AS g,coalesce(a.stay_valid_booking_count,0) AS s,
           coalesce(a.lead_time_valid_count,0) AS l,coalesce(a.adr_valid_count,0) AS r,
           a.observed_total_adults,a.observed_total_children,a.observed_total_babies,
           a.observed_total_guests,a.observed_total_stay_nights,a.sum_lead_time,a.sum_adr
    FROM dw.dim_date d CROSS JOIN axes c
    JOIN dw.daily_hotel_context x ON x.date_key=d.date_key AND x.dw_run_id=%(run_id)s
    JOIN dw.daily_data_quality q ON q.date_key=d.date_key AND q.dw_run_id=%(run_id)s
    JOIN dw.source_coverage v ON v.local_date=d.full_date AND v.run_id=%(run_id)s AND v.source_id='booking'
    LEFT JOIN aggregates a ON a.date_key=d.date_key AND a.is_daily=c.is_daily
                          AND (c.is_daily OR a.country_key=c.country_key)
    WHERE d.full_date BETWEEN %(start)s::date AND %(end)s::date
), measures AS (
    SELECT date_key,full_date,year,quarter,month,iso_year,iso_week,day_of_week,is_weekend,data_version,
           is_holiday,has_national_holiday,has_lisboa_holiday,holiday_names,temperature_mean,precipitation,
           holiday_data_status,temperature_status,precipitation_status,
           booking_data_status,guest_data_status,stay_data_status,
           rejected_booking_count,guest_ineligible_booking_count,stay_ineligible_booking_count,
           CASE WHEN n>0 OR allow_empty THEN n END AS total_bookings,
           CASE WHEN n>0 OR allow_empty THEN b END AS non_canceled_bookings,
           CASE WHEN n>0 OR allow_empty THEN canceled END AS total_cancellations,
           g AS guest_valid_booking_count,s AS stay_valid_booking_count,l AS lead_time_valid_count,r AS adr_valid_count,
           CASE WHEN g>0 THEN observed_total_adults WHEN b=0 AND allow_empty THEN 0 END::bigint AS observed_total_adults,
           CASE WHEN g>0 THEN observed_total_children WHEN b=0 AND allow_empty THEN 0 END::bigint AS observed_total_children,
           CASE WHEN g>0 THEN observed_total_babies WHEN b=0 AND allow_empty THEN 0 END::bigint AS observed_total_babies,
           CASE WHEN g>0 THEN observed_total_guests WHEN b=0 AND allow_empty THEN 0 END::bigint AS observed_total_guests,
           CASE WHEN s>0 THEN observed_total_stay_nights WHEN b=0 AND allow_empty THEN 0 END::bigint AS observed_total_stay_nights,
           CASE WHEN l>0 THEN sum_lead_time WHEN b=0 AND allow_empty THEN 0 END::bigint AS sum_lead_time,
           CASE WHEN r>0 THEN sum_adr WHEN b=0 AND allow_empty THEN 0 END AS sum_adr,
           country_key,country_code,country_name,is_daily
    FROM joined
)
SELECT date_key,full_date,year,quarter,month,iso_year,iso_week,day_of_week,is_weekend,data_version,
       is_holiday,has_national_holiday,has_lisboa_holiday,holiday_names,temperature_mean,precipitation,
       holiday_data_status,temperature_status,precipitation_status,
       booking_data_status,guest_data_status,stay_data_status,
       rejected_booking_count,guest_ineligible_booking_count,stay_ineligible_booking_count,
       total_bookings,non_canceled_bookings,total_cancellations,
       guest_valid_booking_count,stay_valid_booking_count,lead_time_valid_count,adr_valid_count,
       observed_total_adults,observed_total_children,observed_total_babies,observed_total_guests,
       observed_total_stay_nights,sum_lead_time,sum_adr,
       total_cancellations::numeric/nullif(total_bookings,0) AS cancellation_rate,
       observed_total_guests::numeric/nullif(guest_valid_booking_count,0) AS avg_party_size,
       observed_total_stay_nights::numeric/nullif(stay_valid_booking_count,0) AS avg_stay_nights,
       sum_lead_time::numeric/nullif(lead_time_valid_count,0) AS avg_lead_time,
       sum_adr/nullif(adr_valid_count,0) AS avg_adr,
       CASE WHEN guest_data_status='COMPLETE' THEN observed_total_guests END AS target_guests,
       country_key,country_code,country_name,is_daily
FROM measures;
