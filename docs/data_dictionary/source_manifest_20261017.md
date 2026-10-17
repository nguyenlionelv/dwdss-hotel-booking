# Source manifest — acquisition run 2026-10-17

All timestamps are UTC. Raw files are ignored by Git and must not be force-added. Checksums identify the exact inputs used by the profiling evidence in `artifacts/profiling/run_20261017_full/`.

Current ingestion scope: keep the full Booking raw file unchanged, but load only `hotel = 'City Hotel'` into Staging. Holiday and Weather remain required sources; Event is out of scope. See [data contract](operations_sources.md) for missing/invalid and provenance rules.

The executable source selection (three paths, checksums, settings and checksum-bound expected counts) is [operations_source_set.json](operations_source_set.json). Update it only after reviewing a new source version; do not substitute files by name alone.

## Booking

| Attribute | Value |
|---|---|
| Required dataset | Kaggle `mathsian/hotel-bookings` |
| Dataset URL | https://www.kaggle.com/datasets/mathsian/hotel-bookings/data |
| API metadata URL | https://www.kaggle.com/api/v1/datasets/view/mathsian/hotel-bookings |
| API download URL | https://www.kaggle.com/api/v1/datasets/download/mathsian/hotel-bookings |
| Kaggle version at retrieval | 5; last updated 2025-03-27T06:52:39.11Z |
| License reported by Kaggle | Attribution 4.0 International (CC BY 4.0) |
| Retrieved | 2026-10-17 |
| Archive | `data/raw/booking/hotel-bookings_mathsian_20261017.zip` |
| Archive SHA256 | `4510b096847f95275d980e012bc12850b78d3137dc16d62f27bc98baeffafe5b` |
| Metadata | `data/raw/booking/kaggle_metadata_mathsian_hotel-bookings_20261017.json` |
| Metadata SHA256 | `25e7eaf600f761d49a12a23ac1d9177e8ed1290ceb64652d02368d1ae2209491` |
| Selected source file | `data/raw/booking/mathsian_hotel-bookings_20261017/hotel_bookings.csv` |
| Selected file SHA256 | `7c2ae42a7353905ea136e5c2287f17c92c5435826598bfbb8491c6f0c7b1fc06` |
| Measured shape | 119,390 rows × 32 source columns |
| Measured hotel split | City Hotel 79,330; Resort Hotel 40,060 |
| Measured arrival coverage | 2015-07-01 through 2017-08-31 |

The archive also contains `bookings.csv`, `bookings_2023.csv`, and `bookings_2025.csv`. Kaggle describes them as reduced/preprocessed variants. They are retained unchanged for provenance but are not inputs to the project pipeline.

The research paper describes two separate datasets with 31 variables and 119,390 total observations. The selected Kaggle file combines them and adds the `hotel` discriminator, producing 32 columns. The measured hotel counts and date range match the paper. The paper also establishes the location mapping H2/City Hotel → Lisbon and H1/Resort Hotel → Algarve: https://pmc.ncbi.nlm.nih.gov/articles/PMC6297060/

Reproduction:

```powershell
python pipeline/ingestion/download_booking.py --output-dir data/raw/booking
```

The script refuses to overwrite an existing acquisition.

## Holiday

| Attribute | Value |
|---|---|
| Generator | `python-holidays` 0.106 |
| Documentation | https://holidays.readthedocs.io/en/main/auto_gen_docs/portugal/ |
| Country / subdivision | Portugal `PT`; Lisboa `11` |
| Years | 2015–2017 |
| Category | Public holidays |
| Observed setting | `False` |
| Other generation settings | `language=pt_PT`, `category=PUBLIC`; national rows kept once, Lisboa rows added only for local/different holiday names |
| Generated | 2026-10-17T06:18:06Z |
| CSV | `data/raw/holiday/pt_lisboa_holidays_2015_2017_20261017.csv` |
| CSV SHA256 | `0ee97e00fc4cbb89361454fd9b9e84ef363b29780e40be3cd0ecafaaa7378428` |
| Measured rows | 38: 35 national and 3 Lisboa-specific |

National rows are stored once. The Lisboa calendar contributes only local dates or a different local name on the same date, preventing duplicate national rows in the generated raw file.

Reproduction:

```powershell
python pipeline/ingestion/generate_holidays.py --start-year 2015 --end-year 2017 --output-dir data/raw/holiday
```

## Weather

| Attribute | Value |
|---|---|
| Provider | Open-Meteo Historical Weather API |
| Documentation | https://open-meteo.com/en/docs/historical-weather-api |
| Model | ERA5 |
| Requested coordinate | 38.72509, -9.1498 from Open-Meteo geocoding for Lisbon, Portugal |
| Returned ERA5 grid coordinate | 38.75, -9.25 |
| Coordinate meaning | Representative Lisbon city/grid location; not the anonymized hotel's exact location |
| Timezone | `Europe/Lisbon` |
| Geocoding request | `name=Lisbon&count=10&language=en&format=json&countryCode=PT` at `https://geocoding-api.open-meteo.com/v1/search` |
| Historical request | `latitude=38.72509&longitude=-9.1498&start_date=2015-07-01&end_date=2017-08-31&daily=temperature_2m_mean,precipitation_sum&timezone=Europe/Lisbon&models=era5` at `https://archive-api.open-meteo.com/v1/archive` |
| Variables | Daily `temperature_2m_mean` (°C), `precipitation_sum` (mm) |
| Date range | 2015-07-01 through 2017-08-31 |
| Retrieved | 2026-10-17T06:18:59Z |
| Raw JSON | `data/raw/weather/open_meteo_lisbon_era5_2015-07-01_2017-08-31_20261017.json` |
| Raw JSON SHA256 | `3ffb2abf731ae6df9c562c063ff070b08ae26615331a985e998f1306f57be781` |
| Geocoding JSON | `data/raw/weather/open_meteo_lisbon_geocoding_20261017.json` |
| Geocoding SHA256 | `88bc45c89512aa689b752294695edd819918c073b1a77383277a4c0271fee56e` |
| Measured coverage | 793 daily rows, no missing date/value and no duplicate date |

Reproduction:

```powershell
python pipeline/ingestion/fetch_weather.py --start-date 2015-07-01 --end-date 2017-08-31 --output-dir data/raw/weather
```

ERA5 is historical reanalysis suitable for descriptive association analysis. It is not a weather forecast known at historical model cutoffs and is excluded from the baseline demand-forecast feature contract.
