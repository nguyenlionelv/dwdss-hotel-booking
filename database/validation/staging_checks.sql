-- Read-only spot checks for the active, published source set.
SELECT b.batch_id, b.status, b.source_set_fingerprint, a.published_at
FROM staging.active_snapshot AS a
JOIN staging.load_batch AS b ON b.batch_id = a.batch_id;

SELECT source_id, source_file_sha256, raw_count, staged_count,
       out_of_scope_count, unidentified_count, reject_count,
       missing_counts, invalid_counts
FROM staging.load_batch_source
WHERE batch_id = (SELECT batch_id FROM staging.active_snapshot WHERE singleton_id = 1)
ORDER BY source_id;

SELECT 'booking' AS source_id, count(*) AS active_rows FROM staging.v_booking_current
UNION ALL SELECT 'holiday', count(*) FROM staging.v_holiday_current
UNION ALL SELECT 'weather', count(*) FROM staging.v_weather_current;

SELECT source_id, issue_type, rule_code, count(*) AS issue_count,
       count(DISTINCT (source_file_sha256, source_row_id)) AS affected_records
FROM staging.quality_issue
WHERE batch_id = (SELECT batch_id FROM staging.active_snapshot WHERE singleton_id = 1)
GROUP BY source_id, issue_type, rule_code ORDER BY source_id, issue_type, rule_code;

SELECT count(*) AS daily_context_rows, count(DISTINCT local_date) AS distinct_context_dates,
       count(*) FILTER (WHERE weather_ambiguous) AS ambiguous_weather_dates,
       count(*) FILTER (WHERE temperature_2m_mean IS NULL) AS unknown_temperature_dates,
       count(*) FILTER (WHERE precipitation_sum IS NULL) AS unknown_precipitation_dates
FROM staging.v_daily_context_current;

SELECT count(*) AS booking_after_context_join
FROM staging.v_booking_current AS b
LEFT JOIN staging.v_daily_context_current AS c ON c.local_date = b.arrival_date AND c.hotel = b.hotel;
