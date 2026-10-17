CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.load_batch (
    batch_id uuid PRIMARY KEY,
    source_set_fingerprint char(64) NOT NULL,
    contract_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('loading', 'published', 'failed')),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    error_summary text
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_published_source_set
    ON staging.load_batch (source_set_fingerprint) WHERE status = 'published';

CREATE TABLE IF NOT EXISTS staging.load_batch_source (
    batch_id uuid NOT NULL REFERENCES staging.load_batch(batch_id),
    source_id text NOT NULL CHECK (source_id IN ('booking', 'holiday', 'weather')),
    source_file text NOT NULL,
    source_file_sha256 char(64) NOT NULL,
    source_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    raw_count bigint NOT NULL CHECK (raw_count >= 0),
    staged_count bigint NOT NULL CHECK (staged_count >= 0),
    out_of_scope_count bigint NOT NULL DEFAULT 0 CHECK (out_of_scope_count >= 0),
    unidentified_count bigint NOT NULL DEFAULT 0 CHECK (unidentified_count >= 0),
    reject_count bigint NOT NULL DEFAULT 0 CHECK (reject_count >= 0),
    missing_counts jsonb NOT NULL DEFAULT '{}'::jsonb,
    invalid_counts jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (batch_id, source_id)
);

CREATE TABLE IF NOT EXISTS staging.active_snapshot (
    singleton_id smallint PRIMARY KEY CHECK (singleton_id = 1),
    batch_id uuid NOT NULL REFERENCES staging.load_batch(batch_id),
    published_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staging.stg_booking (
    _source_id text NOT NULL DEFAULT 'booking' CHECK (_source_id = 'booking'),
    _source_file text NOT NULL,
    _source_file_sha256 char(64) NOT NULL,
    _source_row_id bigint NOT NULL CHECK (_source_row_id >= 2),
    _batch_id uuid NOT NULL REFERENCES staging.load_batch(batch_id),
    _ingested_at timestamptz NOT NULL DEFAULT now(),
    raw_record jsonb NOT NULL,
    hotel text NOT NULL CHECK (hotel = 'City Hotel'),
    is_canceled smallint,
    lead_time integer,
    arrival_date_year integer,
    arrival_date_month text,
    arrival_date_week_number integer,
    arrival_date_day_of_month integer,
    stays_in_weekend_nights integer,
    stays_in_week_nights integer,
    adults numeric,
    children numeric,
    babies numeric,
    meal text,
    country text,
    market_segment text,
    distribution_channel text,
    is_repeated_guest smallint,
    previous_cancellations integer,
    previous_bookings_not_canceled integer,
    reserved_room_type text,
    assigned_room_type text,
    booking_changes integer,
    deposit_type text,
    agent text,
    company text,
    days_in_waiting_list integer,
    customer_type text,
    adr numeric,
    required_car_parking_spaces integer,
    total_of_special_requests integer,
    reservation_status text,
    reservation_status_date date,
    arrival_date date,
    PRIMARY KEY (_source_file_sha256, _source_row_id)
);
CREATE INDEX IF NOT EXISTS ix_stg_booking_arrival_date ON staging.stg_booking(arrival_date);

CREATE TABLE IF NOT EXISTS staging.stg_holiday (
    _source_id text NOT NULL DEFAULT 'holiday' CHECK (_source_id = 'holiday'),
    _source_file text NOT NULL,
    _source_file_sha256 char(64) NOT NULL,
    _source_row_id bigint NOT NULL CHECK (_source_row_id >= 2),
    _batch_id uuid NOT NULL REFERENCES staging.load_batch(batch_id),
    _ingested_at timestamptz NOT NULL DEFAULT now(),
    raw_record jsonb NOT NULL,
    date date,
    holiday_name text,
    country text,
    subdivision text,
    scope text,
    category text,
    observed boolean,
    PRIMARY KEY (_source_file_sha256, _source_row_id)
);
CREATE INDEX IF NOT EXISTS ix_stg_holiday_date ON staging.stg_holiday(date);

CREATE TABLE IF NOT EXISTS staging.stg_weather (
    _source_id text NOT NULL DEFAULT 'weather' CHECK (_source_id = 'weather'),
    _source_file text NOT NULL,
    _source_file_sha256 char(64) NOT NULL,
    _source_row_id bigint NOT NULL CHECK (_source_row_id >= 1),
    _batch_id uuid NOT NULL REFERENCES staging.load_batch(batch_id),
    _ingested_at timestamptz NOT NULL DEFAULT now(),
    raw_record jsonb NOT NULL,
    local_date date,
    temperature_2m_mean numeric,
    precipitation_sum numeric,
    PRIMARY KEY (_source_file_sha256, _source_row_id)
);
CREATE INDEX IF NOT EXISTS ix_stg_weather_date ON staging.stg_weather(local_date);

CREATE TABLE IF NOT EXISTS staging.quality_issue (
    issue_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id uuid NOT NULL REFERENCES staging.load_batch(batch_id),
    source_id text NOT NULL CHECK (source_id IN ('booking', 'holiday', 'weather')),
    source_file_sha256 char(64) NOT NULL,
    source_row_id bigint NOT NULL,
    field text NOT NULL,
    rule_code text NOT NULL,
    issue_type text NOT NULL CHECK (issue_type IN ('missing', 'invalid')),
    raw_value text,
    reason text NOT NULL,
    severity text NOT NULL CHECK (severity IN ('info', 'warning', 'error')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_quality_issue_batch ON staging.quality_issue(batch_id, source_id);

CREATE TABLE IF NOT EXISTS staging.reject (
    reject_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id uuid NOT NULL REFERENCES staging.load_batch(batch_id),
    source_id text NOT NULL,
    source_file_sha256 char(64),
    source_locator text,
    raw_fragment text,
    rule_code text NOT NULL,
    reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW staging.v_booking_current AS
SELECT s.* FROM staging.stg_booking AS s
JOIN staging.active_snapshot AS a ON a.singleton_id = 1
JOIN staging.load_batch_source AS bs
  ON bs.batch_id = a.batch_id AND bs.source_id = 'booking'
 AND bs.source_file_sha256 = s._source_file_sha256;

CREATE OR REPLACE VIEW staging.v_holiday_current AS
SELECT s.* FROM staging.stg_holiday AS s
JOIN staging.active_snapshot AS a ON a.singleton_id = 1
JOIN staging.load_batch_source AS bs
  ON bs.batch_id = a.batch_id AND bs.source_id = 'holiday'
 AND bs.source_file_sha256 = s._source_file_sha256;

CREATE OR REPLACE VIEW staging.v_weather_current AS
SELECT s.* FROM staging.stg_weather AS s
JOIN staging.active_snapshot AS a ON a.singleton_id = 1
JOIN staging.load_batch_source AS bs
  ON bs.batch_id = a.batch_id AND bs.source_id = 'weather'
 AND bs.source_file_sha256 = s._source_file_sha256;

CREATE OR REPLACE VIEW staging.v_daily_context_current AS
WITH dates AS (
    SELECT generate_series(min(arrival_date), max(arrival_date), interval '1 day')::date AS local_date
    FROM staging.v_booking_current WHERE arrival_date IS NOT NULL
), holidays AS (
    SELECT date AS local_date, count(*) AS holiday_count,
           array_agg(DISTINCT holiday_name ORDER BY holiday_name) AS holiday_names
    FROM staging.v_holiday_current WHERE date IS NOT NULL GROUP BY date
), weather AS (
    SELECT local_date, count(*) AS weather_count,
           min(temperature_2m_mean) AS temperature_2m_mean,
           min(precipitation_sum) AS precipitation_sum
    FROM staging.v_weather_current WHERE local_date IS NOT NULL GROUP BY local_date
)
SELECT 'City Hotel'::text AS hotel, d.local_date,
       (extract(isodow FROM d.local_date) IN (6, 7)) AS is_weekend,
       CASE WHEN h.holiday_count > 0 THEN true ELSE NULL::boolean END AS is_holiday,
       h.holiday_names,
       CASE WHEN w.weather_count = 1 THEN w.temperature_2m_mean ELSE NULL END AS temperature_2m_mean,
       CASE WHEN w.weather_count = 1 THEN w.precipitation_sum ELSE NULL END AS precipitation_sum,
       coalesce(w.weather_count > 1, false) AS weather_ambiguous
FROM dates AS d
LEFT JOIN holidays AS h USING (local_date)
LEFT JOIN weather AS w USING (local_date);
