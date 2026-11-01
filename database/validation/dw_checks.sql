-- Independent SQL oracles for a run's pinned source version (also valid before publication).
WITH run AS (SELECT * FROM dw.load_run WHERE run_id=%(run_id)s),
configured_coverage AS (SELECT value AS entry FROM jsonb_array_elements(%(coverage)s::jsonb->'intervals')),
bad AS (
    SELECT i.source_file_sha256,i.source_row_id,array_agg(DISTINCT i.field) AS fields
    FROM staging.quality_issue i JOIN run r ON r.staging_batch_id=i.batch_id
    WHERE i.source_id='booking' AND i.issue_type='invalid' AND i.rule_code<>'ZERO_GUESTS'
    GROUP BY i.source_file_sha256,i.source_row_id
), src AS (
    SELECT b.*,coalesce(bad.fields,'{}'::text[]) AS bad_fields
    FROM run r JOIN staging.load_batch_source bs ON bs.batch_id=r.staging_batch_id AND bs.source_id='booking'
    JOIN staging.stg_booking b ON b._source_file_sha256=bs.source_file_sha256
    LEFT JOIN bad ON bad.source_file_sha256=b._source_file_sha256 AND bad.source_row_id=b._source_row_id
), expected AS (
    SELECT s.*,
        arrival_date IS NOT NULL AND is_canceled IN (0,1)
          AND NOT (bad_fields && ARRAY['arrival_date','arrival_date_year','arrival_date_month','arrival_date_day_of_month','is_canceled']) AS core_valid,
        CASE WHEN adults BETWEEN 0 AND 2147483647 AND adults=trunc(adults) AND NOT ('adults'=ANY(bad_fields)) THEN adults::integer END AS e_adults,
        CASE WHEN children BETWEEN 0 AND 2147483647 AND children=trunc(children) AND NOT ('children'=ANY(bad_fields)) THEN children::integer END AS e_children,
        CASE WHEN babies BETWEEN 0 AND 2147483647 AND babies=trunc(babies) AND NOT ('babies'=ANY(bad_fields)) THEN babies::integer END AS e_babies,
        CASE WHEN stays_in_week_nights>=0 AND NOT ('stays_in_week_nights'=ANY(bad_fields)) THEN stays_in_week_nights END AS e_week,
        CASE WHEN stays_in_weekend_nights>=0 AND NOT ('stays_in_weekend_nights'=ANY(bad_fields)) THEN stays_in_weekend_nights END AS e_weekend,
        CASE WHEN lead_time>=0 AND NOT ('lead_time'=ANY(bad_fields)) THEN lead_time END AS e_lead,
        CASE WHEN adr>=0 AND adr<'Infinity'::numeric AND NOT ('adr'=ANY(bad_fields)) THEN adr END AS e_adr
    FROM src s
), fact AS (SELECT * FROM dw.fact_booking), rejection AS (
    SELECT * FROM dw.booking_rejection WHERE run_id=%(run_id)s
), input_keys AS (SELECT _source_file_sha256 AS sha,_source_row_id AS row_id FROM src),
output_keys AS (SELECT source_file_sha256 AS sha,source_row_id AS row_id FROM fact
               UNION SELECT source_file_sha256,source_row_id FROM rejection),
expected_fact_keys AS (SELECT _source_file_sha256 AS sha,_source_row_id AS row_id FROM expected WHERE core_valid),
source_counts AS (SELECT arrival_date,count(*) AS n FROM src WHERE arrival_date IS NOT NULL GROUP BY arrival_date),
rejection_counts AS (SELECT arrival_date,count(*) AS n FROM rejection WHERE arrival_date IS NOT NULL GROUP BY arrival_date),
fact_counts AS (
    SELECT date_key,count(*) AS n,count(*) FILTER (WHERE is_canceled=0) AS active,
      count(*) FILTER (WHERE is_canceled=0 AND NOT guest_eligible) AS guest_bad,
      count(*) FILTER (WHERE is_canceled=0 AND NOT stay_eligible) AS stay_bad,
      count(*) FILTER (WHERE is_canceled=0 AND lead_time IS NULL) AS lead_bad,
      count(*) FILTER (WHERE is_canceled=0 AND adr IS NULL) AS adr_bad,
      count(*) FILTER (WHERE is_canceled=0 AND party_type='UNKNOWN') AS party_bad,
      count(*) FILTER (WHERE is_canceled=0 AND channel_key=0) AS channel_bad,
      count(*) FILTER (WHERE is_canceled=0 AND market_segment_key=0) AS segment_bad,
      count(*) FILTER (WHERE is_canceled=0 AND p.customer_type_code='UNKNOWN') AS type_bad,
      count(*) FILTER (WHERE is_canceled=0 AND p.repeat_status='UNKNOWN') AS repeat_bad,
      count(*) FILTER (WHERE is_canceled=0 AND NOT room_comparison_eligible) AS room_bad
    FROM fact f JOIN dw.dim_customer_profile p USING (customer_profile_key) GROUP BY date_key
), weather_bad AS (
    SELECT i.source_row_id,array_agg(DISTINCT i.field) AS fields
    FROM staging.quality_issue i JOIN run r ON r.staging_batch_id=i.batch_id
    WHERE i.source_id='weather' AND i.issue_type='invalid' AND i.rule_code<>'WEATHER_DUPLICATE_DATE'
    GROUP BY i.source_row_id
), weather_rows AS (
    SELECT w.*,coalesce(b.fields,'{}'::text[]) AS bad_fields
    FROM run r JOIN staging.load_batch_source bs ON bs.batch_id=r.staging_batch_id AND bs.source_id='weather'
    JOIN staging.stg_weather w ON w._source_file_sha256=bs.source_file_sha256
    LEFT JOIN weather_bad b ON b.source_row_id=w._source_row_id
), weather_days AS (
    SELECT local_date,count(*) AS n,
      min(temperature_2m_mean) AS temperature,min(precipitation_sum) AS rain,
      bool_or('temperature_2m_mean'=ANY(bad_fields)) AS temp_bad,
      bool_or('precipitation_sum'=ANY(bad_fields)) AS rain_bad,
      bool_or((raw_record->>'temperature_2m_mean') IS NULL OR raw_record->>'temperature_2m_mean'='') AS temp_missing,
      bool_or((raw_record->>'precipitation_sum') IS NULL OR raw_record->>'precipitation_sum'='') AS rain_missing
    FROM weather_rows WHERE local_date IS NOT NULL GROUP BY local_date
), weather_expected AS (
    SELECT d.date_key,coalesce(w.n,0) AS n,
      CASE WHEN w.n=1 AND NOT w.temp_bad AND w.temperature>'-Infinity'::numeric AND w.temperature<'Infinity'::numeric THEN w.temperature END AS temp,
      CASE WHEN w.n=1 AND NOT w.rain_bad AND w.rain>=0 AND w.rain<'Infinity'::numeric THEN w.rain END AS rain,
      CASE WHEN w.n>1 THEN 'AMBIGUOUS' WHEN w.n=1 THEN
        CASE WHEN w.temp_bad THEN 'INVALID' WHEN w.temp_missing THEN 'MISSING'
             WHEN w.temperature>'-Infinity'::numeric AND w.temperature<'Infinity'::numeric THEN 'COMPLETE' ELSE 'INVALID' END
        WHEN cv.coverage_status IN ('COMPLETE','MISSING') THEN 'MISSING' ELSE 'UNKNOWN' END AS temp_status,
      CASE WHEN w.n>1 THEN 'AMBIGUOUS' WHEN w.n=1 THEN
        CASE WHEN w.rain_bad THEN 'INVALID' WHEN w.rain_missing THEN 'MISSING'
             WHEN w.rain>=0 AND w.rain<'Infinity'::numeric THEN 'COMPLETE' ELSE 'INVALID' END
        WHEN cv.coverage_status IN ('COMPLETE','MISSING') THEN 'MISSING' ELSE 'UNKNOWN' END AS rain_status
    FROM dw.dim_date d LEFT JOIN weather_days w ON w.local_date=d.full_date
    LEFT JOIN dw.source_coverage cv ON cv.run_id=%(run_id)s AND cv.source_id='weather' AND cv.local_date=d.full_date
), holiday_source AS (
    SELECT h.* FROM run r JOIN staging.load_batch_source bs ON bs.batch_id=r.staging_batch_id AND bs.source_id='holiday'
    JOIN staging.stg_holiday h ON h._source_file_sha256=bs.source_file_sha256
), holiday_validity AS (
    SELECT h.*,(h.date IS NOT NULL AND h.country='PT' AND h.category='public' AND h.observed=false AND btrim(h.holiday_name)<>''
      AND ((h.scope='national' AND h.subdivision IS NULL) OR (h.scope='Lisboa' AND h.subdivision='11'))
      AND NOT EXISTS (SELECT 1 FROM staging.quality_issue i JOIN run r ON i.batch_id=r.staging_batch_id WHERE i.source_id='holiday'
                      AND i.source_file_sha256=h._source_file_sha256 AND i.source_row_id=h._source_row_id AND i.issue_type='invalid')) IS TRUE AS valid_row
    FROM holiday_source h
), holiday_rows AS (SELECT * FROM holiday_validity WHERE valid_row
), holiday_days AS (
    SELECT date,count(*) AS n,array_agg(DISTINCT btrim(holiday_name) COLLATE "C" ORDER BY btrim(holiday_name) COLLATE "C") AS names,
      bool_or(scope='national') AS national,bool_or(scope='Lisboa') AS lisboa
    FROM holiday_rows GROUP BY date
), scope_inputs AS (
    SELECT d.date_key,d.full_date,s.scope,
      coalesce((SELECT entry->>'status' FROM configured_coverage WHERE entry->>'source_id'='holiday' AND entry->>'scope'=s.scope
        AND d.full_date BETWEEN (entry->>'start')::date AND (entry->>'end')::date),'UNKNOWN') AS base,
      EXISTS (SELECT 1 FROM holiday_rows h WHERE h.date=d.full_date AND h.scope=s.scope) AS has_holiday,
      EXISTS (SELECT 1 FROM holiday_validity h WHERE NOT h.valid_row AND (h.date IS NULL OR h.date=d.full_date)
                AND (h.scope=s.scope OR h.scope IS NULL OR h.scope NOT IN ('national','Lisboa'))) AS tainted
    FROM dw.dim_date d CROSS JOIN (VALUES ('national'),('Lisboa')) s(scope)
), scope_expected AS (
    SELECT *,CASE WHEN has_holiday THEN true WHEN NOT tainted AND base='COMPLETE' THEN false ELSE NULL::boolean END AS flag,
      CASE WHEN tainted THEN CASE WHEN has_holiday THEN 'PARTIAL' ELSE 'UNKNOWN' END ELSE base END AS status
    FROM scope_inputs
), holiday_expected AS (
    SELECT n.date_key,n.flag AS national,l.flag AS lisboa,
      CASE WHEN n.status=l.status THEN n.status ELSE 'PARTIAL' END AS status
    FROM scope_expected n JOIN scope_expected l USING(date_key) WHERE n.scope='national' AND l.scope='Lisboa'
)
SELECT 'source_key_missing' AS check_name,count(*) AS violations FROM (SELECT * FROM input_keys EXCEPT SELECT * FROM output_keys) x
UNION ALL SELECT 'source_key_extra',count(*) FROM (SELECT * FROM output_keys EXCEPT SELECT * FROM input_keys) x
UNION ALL SELECT 'fact_rejection_overlap',count(*) FROM fact f JOIN rejection r USING (source_file_sha256,source_row_id)
UNION ALL SELECT 'core_acceptance_missing',count(*) FROM (SELECT * FROM expected_fact_keys EXCEPT SELECT source_file_sha256,source_row_id FROM fact) x
UNION ALL SELECT 'core_acceptance_extra',count(*) FROM (SELECT source_file_sha256,source_row_id FROM fact EXCEPT SELECT * FROM expected_fact_keys) x
UNION ALL SELECT 'fact_wrong_run',count(*) FROM fact WHERE dw_run_id<>%(run_id)s
UNION ALL SELECT 'first_batch_lineage',count(*) FROM fact f JOIN src s ON f.source_file_sha256=s._source_file_sha256 AND f.source_row_id=s._source_row_id
    WHERE f.source_first_batch_id<>s._batch_id
UNION ALL SELECT 'fact_source_measures',count(*) FROM fact f JOIN expected e ON f.source_file_sha256=e._source_file_sha256 AND f.source_row_id=e._source_row_id
    WHERE ROW(f.is_canceled,f.adults,f.children,f.babies,f.stays_in_week_nights,f.stays_in_weekend_nights,f.lead_time,f.adr,f.country_raw)
       IS DISTINCT FROM ROW(e.is_canceled,e.e_adults,e.e_children,e.e_babies,e.e_week,e.e_weekend,e.e_lead,e.e_adr,e.raw_record->>'country')
UNION ALL SELECT 'arrival_date_key',count(*) FROM fact f JOIN src s ON f.source_file_sha256=s._source_file_sha256 AND f.source_row_id=s._source_row_id
    JOIN dw.dim_date d ON d.date_key=f.date_key WHERE d.full_date IS DISTINCT FROM s.arrival_date
UNION ALL SELECT 'unknown_date_rejection',count(*) FROM rejection WHERE arrival_date IS NULL
UNION ALL SELECT 'context_dates_missing',count(*) FROM (SELECT date_key FROM dw.dim_date EXCEPT SELECT date_key FROM dw.daily_hotel_context) x
UNION ALL SELECT 'quality_dates_missing',count(*) FROM (SELECT date_key FROM dw.dim_date EXCEPT SELECT date_key FROM dw.daily_data_quality) x
UNION ALL SELECT 'context_wrong_run',count(*) FROM dw.daily_hotel_context WHERE dw_run_id<>%(run_id)s
UNION ALL SELECT 'quality_wrong_run',count(*) FROM dw.daily_data_quality WHERE dw_run_id<>%(run_id)s
UNION ALL SELECT 'coverage_missing',count(*) FROM (
    SELECT s.source_id,d.full_date FROM dw.dim_date d CROSS JOIN (VALUES ('booking'),('holiday'),('weather')) s(source_id)
    EXCEPT SELECT source_id,local_date FROM dw.source_coverage WHERE run_id=%(run_id)s) x
UNION ALL SELECT 'coverage_extra',count(*) FROM (
    SELECT source_id,local_date FROM dw.source_coverage WHERE run_id=%(run_id)s
    EXCEPT SELECT s.source_id,d.full_date FROM dw.dim_date d CROSS JOIN (VALUES ('booking'),('holiday'),('weather')) s(source_id)) x
UNION ALL SELECT 'daily_quality_counts',count(*) FROM dw.daily_data_quality q JOIN dw.dim_date d USING(date_key)
    LEFT JOIN source_counts s ON s.arrival_date=d.full_date LEFT JOIN fact_counts f ON f.date_key=d.date_key
    LEFT JOIN rejection_counts r ON r.arrival_date=d.full_date
    WHERE ROW(q.source_booking_count,q.fact_booking_count,q.rejected_booking_count,q.non_canceled_booking_count,
              q.guest_ineligible_booking_count,q.stay_ineligible_booking_count,q.lead_time_unknown_booking_count,q.adr_unknown_booking_count,
              q.unknown_party_booking_count,q.unknown_channel_booking_count,q.unknown_segment_booking_count,q.unknown_customer_type_booking_count,
              q.unknown_repeat_booking_count,q.room_ineligible_booking_count)
    IS DISTINCT FROM ROW(coalesce(s.n,0),coalesce(f.n,0),coalesce(r.n,0),coalesce(f.active,0),coalesce(f.guest_bad,0),coalesce(f.stay_bad,0),
                         coalesce(f.lead_bad,0),coalesce(f.adr_bad,0),coalesce(f.party_bad,0),coalesce(f.channel_bad,0),coalesce(f.segment_bad,0),
                         coalesce(f.type_bad,0),coalesce(f.repeat_bad,0),coalesce(f.room_bad,0))
UNION ALL SELECT 'daily_quality_status',count(*) FROM dw.daily_data_quality q JOIN dw.dim_date d USING(date_key)
    JOIN dw.source_coverage cv ON cv.run_id=%(run_id)s AND cv.source_id='booking' AND cv.local_date=d.full_date
    WHERE ROW(q.booking_data_status,q.guest_data_status,q.stay_data_status) IS DISTINCT FROM ROW(
        CASE WHEN q.rejected_booking_count>0 THEN 'PARTIAL' ELSE cv.coverage_status END,
        CASE WHEN q.rejected_booking_count>0 OR q.guest_ineligible_booking_count>0 THEN 'PARTIAL' ELSE cv.coverage_status END,
        CASE WHEN q.rejected_booking_count>0 OR q.stay_ineligible_booking_count>0 THEN 'PARTIAL' ELSE cv.coverage_status END)
UNION ALL SELECT 'weather_context',count(*) FROM dw.daily_hotel_context c JOIN weather_expected w USING(date_key)
    WHERE ROW(c.weather_record_count,c.temperature_mean,c.precipitation,c.temperature_status,c.precipitation_status)
    IS DISTINCT FROM ROW(w.n,w.temp,w.rain,w.temp_status,w.rain_status)
UNION ALL SELECT 'holiday_context',count(*) FROM dw.daily_hotel_context c JOIN dw.dim_date d USING(date_key)
    LEFT JOIN holiday_days h ON h.date=d.full_date
    WHERE c.holiday_record_count IS DISTINCT FROM coalesce(h.n,0)
       OR c.holiday_names IS DISTINCT FROM coalesce(h.names,'{}'::text[])
       OR (h.national AND c.has_national_holiday IS DISTINCT FROM true)
       OR (h.lisboa AND c.has_lisboa_holiday IS DISTINCT FROM true)
UNION ALL SELECT 'holiday_scope_coverage',count(*) FROM dw.daily_hotel_context c JOIN holiday_expected h USING(date_key)
    WHERE ROW(c.has_national_holiday,c.has_lisboa_holiday,c.holiday_data_status) IS DISTINCT FROM ROW(h.national,h.lisboa,h.status)
UNION ALL SELECT 'source_coverage_declaration',count(*) FROM dw.source_coverage c LEFT JOIN dw.dim_date d ON d.full_date=c.local_date
    WHERE c.run_id=%(run_id)s AND c.source_id IN ('booking','weather') AND c.coverage_status IS DISTINCT FROM
      coalesce((SELECT entry->>'status' FROM configured_coverage WHERE entry->>'source_id'=c.source_id AND entry->>'scope'='all'
                AND c.local_date BETWEEN (entry->>'start')::date AND (entry->>'end')::date),'UNKNOWN')
UNION ALL SELECT 'context_source_versions',count(*) FROM dw.daily_hotel_context c CROSS JOIN run r
    WHERE c.holiday_source_sha256 IS DISTINCT FROM (SELECT source_file_sha256 FROM staging.load_batch_source WHERE batch_id=r.staging_batch_id AND source_id='holiday')
       OR c.weather_source_sha256 IS DISTINCT FROM (SELECT source_file_sha256 FROM staging.load_batch_source WHERE batch_id=r.staging_batch_id AND source_id='weather')
UNION ALL SELECT 'dimension_context_join',abs((SELECT count(*) FROM fact)-(SELECT count(*) FROM fact f
    JOIN dw.dim_date d USING(date_key) JOIN dw.dim_country c USING(country_key) JOIN dw.dim_channel ch USING(channel_key)
    JOIN dw.dim_market_segment m USING(market_segment_key) JOIN dw.dim_customer_profile p USING(customer_profile_key)
    JOIN dw.dim_room_type rr ON rr.room_type_key=f.reserved_room_type_key JOIN dw.dim_room_type ar ON ar.room_type_key=f.assigned_room_type_key
    JOIN dw.daily_hotel_context x ON x.date_key=f.date_key));
