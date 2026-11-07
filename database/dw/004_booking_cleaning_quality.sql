-- Cleaning exclusions remain audited rejections without making the cleaned day incomplete.
ALTER TABLE dw.daily_data_quality
    ADD COLUMN excluded_booking_count bigint NOT NULL DEFAULT 0
        CHECK (excluded_booking_count >= 0 AND excluded_booking_count <= rejected_booking_count);

ALTER TABLE dw.daily_data_quality DROP CONSTRAINT ck_quality_complete;
ALTER TABLE dw.daily_data_quality ADD CONSTRAINT ck_quality_complete CHECK (
    (booking_data_status <> 'COMPLETE' OR rejected_booking_count = excluded_booking_count)
    AND (guest_data_status <> 'COMPLETE' OR
        (rejected_booking_count = excluded_booking_count AND guest_ineligible_booking_count = 0))
    AND (stay_data_status <> 'COMPLETE' OR
        (rejected_booking_count = excluded_booking_count AND stay_ineligible_booking_count = 0))
);
