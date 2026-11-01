CREATE TABLE dw.fact_booking (
    booking_key bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file_sha256 char(64) NOT NULL CHECK (source_file_sha256 ~ '^[0-9a-f]{64}$'),
    source_row_id bigint NOT NULL CHECK (source_row_id >= 2),
    source_first_batch_id uuid NOT NULL REFERENCES staging.load_batch(batch_id),
    dw_run_id uuid NOT NULL REFERENCES dw.load_run(run_id),
    date_key integer NOT NULL REFERENCES dw.dim_date(date_key),
    country_key integer NOT NULL REFERENCES dw.dim_country(country_key),
    channel_key integer NOT NULL REFERENCES dw.dim_channel(channel_key),
    market_segment_key integer NOT NULL REFERENCES dw.dim_market_segment(market_segment_key),
    customer_profile_key integer NOT NULL REFERENCES dw.dim_customer_profile(customer_profile_key),
    reserved_room_type_key integer NOT NULL REFERENCES dw.dim_room_type(room_type_key),
    assigned_room_type_key integer NOT NULL REFERENCES dw.dim_room_type(room_type_key),
    country_raw text,
    booking_count smallint NOT NULL CHECK (booking_count = 1),
    is_canceled smallint NOT NULL CHECK (is_canceled IN (0, 1)),
    adults integer CHECK (adults >= 0),
    children integer CHECK (children >= 0),
    babies integer CHECK (babies >= 0),
    total_guests bigint CHECK (total_guests >= 0),
    guest_eligible boolean NOT NULL,
    stays_in_week_nights integer CHECK (stays_in_week_nights >= 0),
    stays_in_weekend_nights integer CHECK (stays_in_weekend_nights >= 0),
    total_stay_nights bigint CHECK (total_stay_nights >= 0),
    stay_eligible boolean NOT NULL,
    lead_time integer CHECK (lead_time >= 0),
    adr numeric CHECK (adr >= 0 AND adr < 'Infinity'::numeric),
    party_type text NOT NULL CHECK (party_type IN ('SINGLE', 'COUPLE', 'FAMILY', 'OTHER_GROUP', 'UNKNOWN')),
    party_eligible boolean NOT NULL,
    room_changed_flag boolean,
    room_comparison_eligible boolean NOT NULL,
    transformed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_file_sha256, source_row_id),
    FOREIGN KEY (source_file_sha256, source_row_id)
        REFERENCES staging.stg_booking(_source_file_sha256, _source_row_id),
    CONSTRAINT ck_guest_consistency CHECK (
        CASE WHEN adults IS NULL OR children IS NULL OR babies IS NULL
            THEN total_guests IS NULL AND NOT guest_eligible
            ELSE total_guests IS NOT NULL AND total_guests = adults::bigint + children::bigint + babies::bigint
                 AND guest_eligible = (total_guests > 0)
        END
    ),
    CONSTRAINT ck_stay_consistency CHECK (
        CASE WHEN stays_in_week_nights IS NULL OR stays_in_weekend_nights IS NULL
            THEN total_stay_nights IS NULL AND NOT stay_eligible
            ELSE total_stay_nights IS NOT NULL
                 AND total_stay_nights = stays_in_week_nights::bigint + stays_in_weekend_nights::bigint
                 AND stay_eligible
        END
    ),
    CONSTRAINT ck_party_consistency CHECK (
        party_eligible = guest_eligible AND party_type = CASE
            WHEN NOT guest_eligible THEN 'UNKNOWN'
            WHEN children > 0 OR babies > 0 THEN 'FAMILY'
            WHEN adults = 1 THEN 'SINGLE'
            WHEN adults = 2 THEN 'COUPLE'
            ELSE 'OTHER_GROUP' END
    ),
    CONSTRAINT ck_room_comparison CHECK (
        room_comparison_eligible = (reserved_room_type_key <> 0 AND assigned_room_type_key <> 0)
        AND CASE WHEN room_comparison_eligible
            THEN room_changed_flag IS NOT NULL AND room_changed_flag = (reserved_room_type_key <> assigned_room_type_key)
            ELSE room_changed_flag IS NULL END
    )
);
CREATE INDEX ix_fact_date ON dw.fact_booking(date_key);
CREATE INDEX ix_fact_country_date ON dw.fact_booking(country_key, date_key);
CREATE INDEX ix_fact_channel_date ON dw.fact_booking(channel_key, date_key);
CREATE INDEX ix_fact_segment_date ON dw.fact_booking(market_segment_key, date_key);
CREATE INDEX ix_fact_profile_date ON dw.fact_booking(customer_profile_key, date_key);
CREATE INDEX ix_fact_reserved_room_date ON dw.fact_booking(reserved_room_type_key, date_key);
CREATE INDEX ix_fact_assigned_room_date ON dw.fact_booking(assigned_room_type_key, date_key);
CREATE INDEX ix_fact_run ON dw.fact_booking(dw_run_id);
CREATE INDEX ix_fact_first_batch ON dw.fact_booking(source_first_batch_id);

-- Keep Staging immutable; verify lineage without adding an index/constraint there.
CREATE FUNCTION dw.check_booking_first_batch() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    first_batch uuid;
BEGIN
    SELECT _batch_id INTO first_batch FROM staging.stg_booking
    WHERE _source_file_sha256 = NEW.source_file_sha256 AND _source_row_id = NEW.source_row_id
    FOR KEY SHARE;
    IF NOT FOUND OR first_batch IS DISTINCT FROM NEW.source_first_batch_id THEN
        RAISE EXCEPTION 'Booking first-batch lineage must match the source row' USING ERRCODE = '23503';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER check_booking_first_batch
    BEFORE INSERT OR UPDATE OF source_file_sha256, source_row_id, source_first_batch_id ON dw.fact_booking
    FOR EACH ROW EXECUTE FUNCTION dw.check_booking_first_batch();

CREATE TABLE dw.daily_hotel_context (
    date_key integer PRIMARY KEY REFERENCES dw.dim_date(date_key),
    dw_run_id uuid NOT NULL REFERENCES dw.load_run(run_id),
    is_holiday boolean,
    has_national_holiday boolean,
    has_lisboa_holiday boolean,
    holiday_names text[] NOT NULL DEFAULT '{}',
    holiday_record_count integer NOT NULL CHECK (holiday_record_count >= 0),
    holiday_data_status text NOT NULL CHECK (holiday_data_status IN ('COMPLETE', 'PARTIAL', 'MISSING', 'UNKNOWN')),
    holiday_source_sha256 char(64) NOT NULL CHECK (holiday_source_sha256 ~ '^[0-9a-f]{64}$'),
    temperature_mean numeric CHECK (temperature_mean > '-Infinity'::numeric AND temperature_mean < 'Infinity'::numeric),
    precipitation numeric CHECK (precipitation >= 0 AND precipitation < 'Infinity'::numeric),
    temperature_status text NOT NULL CHECK (temperature_status IN ('COMPLETE', 'MISSING', 'INVALID', 'AMBIGUOUS', 'UNKNOWN')),
    precipitation_status text NOT NULL CHECK (precipitation_status IN ('COMPLETE', 'MISSING', 'INVALID', 'AMBIGUOUS', 'UNKNOWN')),
    weather_record_count integer NOT NULL CHECK (weather_record_count >= 0),
    weather_ambiguous boolean NOT NULL,
    weather_source_sha256 char(64) NOT NULL CHECK (weather_source_sha256 ~ '^[0-9a-f]{64}$'),
    transformed_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_holiday_or CHECK (is_holiday IS NOT DISTINCT FROM (has_national_holiday OR has_lisboa_holiday)),
    CONSTRAINT ck_holiday_complete CHECK (
        holiday_data_status <> 'COMPLETE' OR (has_national_holiday IS NOT NULL AND has_lisboa_holiday IS NOT NULL)
    ),
    CONSTRAINT ck_holiday_records CHECK (
        array_position(holiday_names, NULL) IS NULL AND NOT ('' = ANY(holiday_names))
        AND cardinality(holiday_names) <= holiday_record_count
        AND (cardinality(holiday_names) = 0 OR array_ndims(holiday_names) = 1)
        AND CASE WHEN holiday_record_count > 0
            THEN cardinality(holiday_names) > 0 AND is_holiday IS TRUE
            ELSE cardinality(holiday_names) = 0 AND is_holiday IS NOT TRUE END
    ),
    CONSTRAINT ck_weather_ambiguity CHECK (
        weather_ambiguous = (weather_record_count > 1)
        AND (temperature_status = 'AMBIGUOUS') = weather_ambiguous
        AND (precipitation_status = 'AMBIGUOUS') = weather_ambiguous
    ),
    CONSTRAINT ck_weather_values CHECK (
        (temperature_status = 'COMPLETE') = (temperature_mean IS NOT NULL)
        AND (precipitation_status = 'COMPLETE') = (precipitation IS NOT NULL)
        AND (weather_record_count <> 0 OR
            (temperature_status IN ('MISSING', 'UNKNOWN') AND precipitation_status IN ('MISSING', 'UNKNOWN')))
    )
);
CREATE INDEX ix_context_run ON dw.daily_hotel_context(dw_run_id);

CREATE TABLE dw.daily_data_quality (
    date_key integer PRIMARY KEY REFERENCES dw.dim_date(date_key),
    dw_run_id uuid NOT NULL REFERENCES dw.load_run(run_id),
    source_booking_count bigint NOT NULL CHECK (source_booking_count >= 0),
    fact_booking_count bigint NOT NULL CHECK (fact_booking_count >= 0),
    rejected_booking_count bigint NOT NULL CHECK (rejected_booking_count >= 0),
    non_canceled_booking_count bigint NOT NULL CHECK (non_canceled_booking_count >= 0),
    guest_ineligible_booking_count bigint NOT NULL CHECK (guest_ineligible_booking_count >= 0),
    stay_ineligible_booking_count bigint NOT NULL CHECK (stay_ineligible_booking_count >= 0),
    lead_time_unknown_booking_count bigint NOT NULL CHECK (lead_time_unknown_booking_count >= 0),
    adr_unknown_booking_count bigint NOT NULL CHECK (adr_unknown_booking_count >= 0),
    unknown_party_booking_count bigint NOT NULL CHECK (unknown_party_booking_count >= 0),
    unknown_channel_booking_count bigint NOT NULL CHECK (unknown_channel_booking_count >= 0),
    unknown_segment_booking_count bigint NOT NULL CHECK (unknown_segment_booking_count >= 0),
    unknown_customer_type_booking_count bigint NOT NULL CHECK (unknown_customer_type_booking_count >= 0),
    unknown_repeat_booking_count bigint NOT NULL CHECK (unknown_repeat_booking_count >= 0),
    room_ineligible_booking_count bigint NOT NULL CHECK (room_ineligible_booking_count >= 0),
    booking_data_status text NOT NULL CHECK (booking_data_status IN ('COMPLETE', 'PARTIAL', 'MISSING', 'UNKNOWN')),
    guest_data_status text NOT NULL CHECK (guest_data_status IN ('COMPLETE', 'PARTIAL', 'MISSING', 'UNKNOWN')),
    stay_data_status text NOT NULL CHECK (stay_data_status IN ('COMPLETE', 'PARTIAL', 'MISSING', 'UNKNOWN')),
    reason_codes text[] NOT NULL DEFAULT '{}',
    CONSTRAINT ck_quality_counts CHECK (
        source_booking_count = fact_booking_count + rejected_booking_count
        AND non_canceled_booking_count <= fact_booking_count
        AND guest_ineligible_booking_count <= non_canceled_booking_count
        AND stay_ineligible_booking_count <= non_canceled_booking_count
        AND lead_time_unknown_booking_count <= non_canceled_booking_count
        AND adr_unknown_booking_count <= non_canceled_booking_count
        AND unknown_party_booking_count <= non_canceled_booking_count
        AND unknown_channel_booking_count <= non_canceled_booking_count
        AND unknown_segment_booking_count <= non_canceled_booking_count
        AND unknown_customer_type_booking_count <= non_canceled_booking_count
        AND unknown_repeat_booking_count <= non_canceled_booking_count
        AND room_ineligible_booking_count <= non_canceled_booking_count
    ),
    CONSTRAINT ck_quality_complete CHECK (
        (booking_data_status <> 'COMPLETE' OR rejected_booking_count = 0)
        AND (guest_data_status <> 'COMPLETE' OR (rejected_booking_count = 0 AND guest_ineligible_booking_count = 0))
        AND (stay_data_status <> 'COMPLETE' OR (rejected_booking_count = 0 AND stay_ineligible_booking_count = 0))
    ),
    CHECK (array_position(reason_codes, NULL) IS NULL AND NOT ('' = ANY(reason_codes))
           AND (cardinality(reason_codes) = 0 OR array_ndims(reason_codes) = 1))
);
CREATE INDEX ix_quality_run ON dw.daily_data_quality(dw_run_id);
