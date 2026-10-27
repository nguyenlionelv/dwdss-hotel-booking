# Hotel Booking — Source Profiling

Source: `dwdss-hotel-booking\data\raw\booking\mathsian_hotel-bookings_20261017\hotel_bookings.csv`
SHA256: `7c2ae42a7353905ea136e5c2287f17c92c5435826598bfbb8491c6f0c7b1fc06`

## Row overview

- Raw rows: **119,390**
- City Hotel rows: **79,330**
- Non-City Hotel rows: **40,060**
- City Hotel rows with detected issues: **171**

## Issue counts (City Hotel only)

| Rule | Rows |
|---|---:|
| `missing_or_invalid_children` | 4 |
| `zero_total_guests` | 167 |

Counts per rule can overlap; do not sum to estimate rejected rows.

## Null profiles

| Field | Null count | Rate |
|---|---:|---:|
| `hotel` | 0 | 0.00% |
| `is_canceled` | 0 | 0.00% |
| `lead_time` | 0 | 0.00% |
| `arrival_date_year` | 0 | 0.00% |
| `arrival_date_month` | 0 | 0.00% |
| `arrival_date_week_number` | 0 | 0.00% |
| `arrival_date_day_of_month` | 0 | 0.00% |
| `stays_in_weekend_nights` | 0 | 0.00% |
| `stays_in_week_nights` | 0 | 0.00% |
| `adults` | 0 | 0.00% |
| `children` | 0 | 0.00% |
| `babies` | 0 | 0.00% |
| `meal` | 0 | 0.00% |
| `country` | 0 | 0.00% |
| `market_segment` | 0 | 0.00% |
| `distribution_channel` | 0 | 0.00% |
| `is_repeated_guest` | 0 | 0.00% |
| `previous_cancellations` | 0 | 0.00% |
| `previous_bookings_not_canceled` | 0 | 0.00% |
| `reserved_room_type` | 0 | 0.00% |
| `assigned_room_type` | 0 | 0.00% |
| `booking_changes` | 0 | 0.00% |
| `deposit_type` | 0 | 0.00% |
| `agent` | 0 | 0.00% |
| `company` | 0 | 0.00% |
| `days_in_waiting_list` | 0 | 0.00% |
| `customer_type` | 0 | 0.00% |
| `adr` | 0 | 0.00% |
| `required_car_parking_spaces` | 0 | 0.00% |
| `total_of_special_requests` | 0 | 0.00% |
| `reservation_status` | 0 | 0.00% |
| `reservation_status_date` | 0 | 0.00% |

## Arrival-date coverage

| Hotel | Minimum | Maximum | Valid rows |
|---|---|---|---:|
| Resort Hotel | 2015-07-01 | 2017-08-31 | 40,060 |
| City Hotel | 2015-07-01 | 2017-08-31 | 79,330 |

## Caveats

- Date is **scheduled arrival date**, not booking creation date.
- This phase does not modify raw or perform DW exclusions.
- Duplicate-looking booking rows are only reported, never dropped.
- Missing ADR/country is reported but does not automatically reject rows.
- Source identity, geography and upstream provenance must be independently documented.
