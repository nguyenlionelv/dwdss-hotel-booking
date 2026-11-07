ALTER TABLE mart.daily_hotel_operations
    ADD COLUMN missing_guest_bookings_count bigint NOT NULL DEFAULT 0
        CHECK (missing_guest_bookings_count >= 0);
ALTER TABLE mart.daily_hotel_operations_by_country
    ADD COLUMN missing_guest_bookings_count bigint NOT NULL DEFAULT 0
        CHECK (missing_guest_bookings_count >= 0);

-- Backfill the published rows from the same DW data version.
WITH missing AS (
    SELECT f.date_key,r.data_version,count(*) AS n
    FROM dw.fact_booking f JOIN dw.load_run r ON r.run_id=f.dw_run_id
    WHERE f.is_canceled=0 AND f.total_guests=0
    GROUP BY f.date_key,r.data_version
)
UPDATE mart.daily_hotel_operations m SET missing_guest_bookings_count=x.n
FROM missing x WHERE x.date_key=m.date_key AND x.data_version=m.data_version;

WITH missing AS (
    SELECT f.date_key,f.country_key,r.data_version,count(*) AS n
    FROM dw.fact_booking f JOIN dw.load_run r ON r.run_id=f.dw_run_id
    WHERE f.is_canceled=0 AND f.total_guests=0
    GROUP BY f.date_key,f.country_key,r.data_version
)
UPDATE mart.daily_hotel_operations_by_country m SET missing_guest_bookings_count=x.n
FROM missing x WHERE x.date_key=m.date_key AND x.country_key=m.country_key AND x.data_version=m.data_version;

-- No known guests contributed to a group containing only missing-guest bookings.
UPDATE mart.daily_hotel_operations
SET observed_total_adults=0,observed_total_children=0,observed_total_babies=0,observed_total_guests=0
WHERE guest_valid_booking_count=0 AND missing_guest_bookings_count>0
  AND non_canceled_bookings=missing_guest_bookings_count;
UPDATE mart.daily_hotel_operations_by_country
SET observed_total_adults=0,observed_total_children=0,observed_total_babies=0,observed_total_guests=0
WHERE guest_valid_booking_count=0 AND missing_guest_bookings_count>0
  AND non_canceled_bookings=missing_guest_bookings_count;
