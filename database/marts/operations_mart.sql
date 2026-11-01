CREATE SCHEMA mart;

CREATE TABLE mart.schema_migration (
    version text PRIMARY KEY,
    file_sha256 char(64) NOT NULL CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE mart.dataset_state (
    singleton_id smallint PRIMARY KEY CHECK (singleton_id = 1),
    dw_run_id uuid NOT NULL REFERENCES dw.load_run(run_id),
    data_version uuid NOT NULL REFERENCES dw.load_run(data_version),
    build_fingerprint char(64) NOT NULL,
    actual_start date NOT NULL,
    actual_end date NOT NULL CHECK (actual_end >= actual_start),
    row_counts jsonb NOT NULL,
    published_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE mart.daily_hotel_operations (
    date_key integer PRIMARY KEY REFERENCES dw.dim_date(date_key),
    full_date date NOT NULL UNIQUE,
    year integer NOT NULL,
    quarter integer NOT NULL,
    month integer NOT NULL,
    iso_year integer NOT NULL,
    iso_week integer NOT NULL,
    day_of_week integer NOT NULL,
    is_weekend boolean NOT NULL,
    data_version uuid NOT NULL REFERENCES dw.load_run(data_version),
    is_holiday boolean,
    has_national_holiday boolean,
    has_lisboa_holiday boolean,
    holiday_names text[] NOT NULL,
    temperature_mean numeric,
    precipitation numeric,
    holiday_data_status text NOT NULL,
    temperature_status text NOT NULL,
    precipitation_status text NOT NULL,
    booking_data_status text NOT NULL CHECK (booking_data_status IN ('COMPLETE','PARTIAL','MISSING','UNKNOWN')),
    guest_data_status text NOT NULL CHECK (guest_data_status IN ('COMPLETE','PARTIAL','MISSING','UNKNOWN')),
    stay_data_status text NOT NULL CHECK (stay_data_status IN ('COMPLETE','PARTIAL','MISSING','UNKNOWN')),
    rejected_booking_count bigint NOT NULL CHECK (rejected_booking_count >= 0),
    guest_ineligible_booking_count bigint NOT NULL CHECK (guest_ineligible_booking_count >= 0),
    stay_ineligible_booking_count bigint NOT NULL CHECK (stay_ineligible_booking_count >= 0),
    total_bookings bigint CHECK (total_bookings >= 0),
    non_canceled_bookings bigint CHECK (non_canceled_bookings >= 0),
    total_cancellations bigint CHECK (total_cancellations >= 0),
    guest_valid_booking_count bigint NOT NULL CHECK (guest_valid_booking_count >= 0),
    stay_valid_booking_count bigint NOT NULL CHECK (stay_valid_booking_count >= 0),
    lead_time_valid_count bigint NOT NULL CHECK (lead_time_valid_count >= 0),
    adr_valid_count bigint NOT NULL CHECK (adr_valid_count >= 0),
    observed_total_adults bigint CHECK (observed_total_adults >= 0),
    observed_total_children bigint CHECK (observed_total_children >= 0),
    observed_total_babies bigint CHECK (observed_total_babies >= 0),
    observed_total_guests bigint CHECK (observed_total_guests >= 0),
    observed_total_stay_nights bigint CHECK (observed_total_stay_nights >= 0),
    sum_lead_time bigint CHECK (sum_lead_time >= 0),
    sum_adr numeric CHECK (sum_adr >= 0 AND sum_adr < 'Infinity'::numeric),
    cancellation_rate numeric CHECK (cancellation_rate BETWEEN 0 AND 1),
    avg_party_size numeric,
    avg_stay_nights numeric,
    avg_lead_time numeric,
    avg_adr numeric,
    target_guests bigint CHECK (target_guests >= 0),
    CHECK (is_holiday IS NOT DISTINCT FROM (has_national_holiday OR has_lisboa_holiday)),
    CHECK (target_guests IS NOT DISTINCT FROM
           CASE WHEN guest_data_status='COMPLETE' THEN observed_total_guests END)
);

-- LIKE copies column/CHECK definitions, but not primary/unique/foreign keys.
CREATE TABLE mart.daily_hotel_operations_by_country (
    LIKE mart.daily_hotel_operations INCLUDING CONSTRAINTS,
    country_key integer NOT NULL REFERENCES dw.dim_country(country_key),
    country_code text NOT NULL,
    country_name text NOT NULL,
    PRIMARY KEY (date_key,country_key),
    FOREIGN KEY (date_key) REFERENCES dw.dim_date(date_key),
    FOREIGN KEY (data_version) REFERENCES dw.load_run(data_version)
);
CREATE INDEX ix_operations_country_date ON mart.daily_hotel_operations_by_country(country_key,date_key);
