# Source recovery — 2026-11-10

The pipeline rebuild uses fresh acquisitions from the existing scripts. The previous selection is retained in `artifacts/recovery/pipeline_20261110/source_set_before.json`. Raw files and acquisition metadata remain Git-ignored.

| Source | Selected file | SHA-256 |
|---|---|---|
| [Kaggle Booking](https://www.kaggle.com/datasets/mathsian/hotel-bookings) | `data/raw/booking/mathsian_hotel-bookings_20261110/hotel_bookings.csv` | `7c2ae42a7353905ea136e5c2287f17c92c5435826598bfbb8491c6f0c7b1fc06` |
| [PT/Lisboa Holiday](https://holidays.readthedocs.io/en/main/auto_gen_docs/portugal/) | `data/raw/holiday/pt_lisboa_holidays_2015_2017_20261110.csv` | `0ee97e00fc4cbb89361454fd9b9e84ef363b29780e40be3cd0ecafaaa7378428` |
| [Lisbon ERA5 Weather](https://open-meteo.com/en/docs/historical-weather-api) | `data/raw/weather/open_meteo_lisbon_era5_2015-07-01_2017-08-31_20261110.json` | `fccc24f4ba84849005154e31aee6ff7b307ce0d2a8f6556ae44c1e1f28f3339a` |

Booking is Kaggle version 5. Its archive and selected CSV reproduce the October checksums exactly: 119,390 rows, 32 columns, 79,330 City Hotel and 40,060 Resort Hotel. Acquisition metadata and archive checksums are in `data/raw/booking/booking_acquisition_manifest_20261110.json`.

Holiday is generated with python-holidays 0.106, PT / subdivision 11, 2015–2017, public, observed=false, language=pt_PT. The CSV reproduces exactly: 35 national and 3 Lisboa rows. Its actual generation timestamp and checksum are retained in the adjacent `.metadata.json`; no historical acquisition timestamp is fabricated.

Weather uses the same request coordinates (38.72509, -9.1498), ERA5, Europe/Lisbon, date range and variables as the previous contract. The response has the same grid (38.75, -9.25) and units, exactly 793 unique consecutive dates, finite temperatures, and finite nonnegative precipitation. The adjacent `.metadata.json` contains the actual request and acquisition timestamp.

The fresh Weather bytes differ from the selected October 27 checksum. The October raw responses are unavailable, so byte reproduction and full comparison against October 27 cannot be established. A preserved database snapshot provides all 793 daily values from the **October 17** checksum `3ffb2abf731ae6df9c562c063ff070b08ae26615331a985e998f1306f57be781`. Against that snapshot, precipitation matches on every day; 334 temperature values differ (162 by +0.1°C, 141 by −0.1°C, 20 by −0.2°C, 10 by +0.2°C, 1 by +0.3°C). The API includes volatile `generationtime_ms`, but this does not explain the temperature changes. Their upstream cause is undetermined; this recovery selects a new validated source version and does not claim value equivalence.

Validation, metadata checksums and comparison evidence are in `artifacts/recovery/pipeline_20261110/source_verification.json`; the preserved series and publication state are in `database_before.json`. `operations_source_set.json`, coverage v3 and the pinned DW coverage checksum select these verified inputs. Parsing, business rules and expected source counts remain unchanged. Booking completeness retains the existing checksum-bound accepted assumption, and Holiday retains the existing replay evidence. Weather completeness is supported by the new independent verification.

The existing `hotel_dwdss` database was inspected and preserved. The rebuild runs in `hotel_dwdss_rebuild_20261110`, selected through the local ignored `.env`, with a separate login. No database or volume was reset or dropped.
