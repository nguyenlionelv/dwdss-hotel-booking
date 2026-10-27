# Member 2 — STAGING READY và bàn giao

Phạm vi đã triển khai trên `DE-BI/phase-1`: Source → Staging cho **Booking City Hotel, Holiday PT/Lisboa, Weather ERA5 Lisbon**. Event, Resort downstream, DW, Operations Mart và ML không thuộc gate này. Source set/chữ ký file nằm ở [operations_source_set.json](data_dictionary/operations_source_set.json); [data dictionary](data_dictionary/operations_sources.md) và [source-to-target contract](etl_spec/operations_source_to_target.md) là quy tắc hiện hành. [Runbook](staging_runbook.md) có lệnh chạy, truy vấn kiểm tra và gói bàn giao. Raw ba nguồn giữ nguyên và khớp checksum trong [source manifest](data_dictionary/source_manifest_20261017.md).

## Trạng thái sáu task phụ thuộc

| Task | Output đã có | Acceptance/evidence |
|---|---|---|
| 1. Contract triển khai | Dictionary + source-to-target, source set JSON đóng đinh ba checksum/config và expected count theo từng file. | City filter trước Staging; missing theo field, invalid khác missing; 32 Booking fields, 7 Holiday fields, 3 Weather daily variables có kiểu và raw representation. Member 1 cần review **giao diện exposed downstream**, không mở lại phạm vi. |
| 2. Staging DDL | `database/staging/001_staging.sql`, `scripts/setup_db.py`; ba bảng Staging, batch/source, quality issue, reject, active snapshot và bốn active views. | Migration chạy thành công trên PostgreSQL 17.11 và chạy lại idempotent trong integration test. Typed business fields nullable + `raw_record jsonb`; constraint chỉ chặn sai cấu trúc/nguồn, không làm mất record invalid đọc được. |
| 3. Batch/transaction/rerun | `pipeline/source_to_staging/common.py`, `run.py`; content-addressed source rows, fingerprint ba nguồn + contract version, session lock, rollback, active pointer. | Batch `published` chỉ sau đủ ba nguồn/đối soát; same-source rerun `no-op`; fault injection/retry và interrupted attempt test pass; failed batch không thay snapshot cũ. |
| 4. Ba loader | `pipeline/source_to_staging/{booking,holiday,weather}.py`, `scripts/run_pipeline.py`, `pipeline/requirements.txt`. | Booking giữ CSV ordinal trước lọc, chỉ City vào Staging; Holiday giữ nhiều lễ/ngày; Weather giữ từng daily entry và metadata request/grid/model/units. Missing `children='NA'` thành SQL NULL mà record vẫn còn; invalid fixture giữ raw + issue; structural fixture ghi failed batch/reject. |
| 5. Quality/reconciliation | `pipeline/quality/staging_checks.py`, `database/validation/staging_checks.sql`; daily context view một dòng/ngày. | [Quality report](../artifacts/staging/quality_report.json) `passed=true`: Booking 119.390 = 79.330 City + 40.060 Resort + 0 unidentified/reject; Holiday 38; Weather 793; join 79.330 → 79.330. Missing/invalid/ngoài phạm vi là nhóm báo cáo riêng, không trừ nhầm issue count khỏi source count. |
| 6. PostgreSQL test/runbook | `tests/pipeline/test_staging_unit.py`, `test_staging_postgres.py`, [runbook](staging_runbook.md) và [JUnit evidence](../artifacts/staging/pytest.xml). | `python -m pytest -q` **5 passed** trên PostgreSQL 17.11 (test DB tách biệt); first load published batch `4dcc2cfc-bed5-4e22-8a4d-fd4ac3f11715`, [rerun evidence](../artifacts/staging/rerun.json) `no-op`. |

## Baseline kỹ thuật đã chốt

- Khóa vật lý mỗi nguồn là `(_source_file_sha256, _source_row_id)`; CSV data record đầu là 2 (header=1), Weather daily index đầu là 1. City đầu tiên ở raw Booking vị trí **40062**. `_batch_id` trên row là batch nạp row lần đầu; `staging.active_snapshot` + `load_batch_source` xác định ba checksum đang có hiệu lực. Không xóa reservation trùng thuộc tính nhưng khác vị trí raw.
- `stg_booking` chỉ có `hotel='City Hotel'`; Resort đếm out-of-scope ở batch source. Raw Booking vẫn đủ 119.390 record. Typed SQL NULL vì missing được đối chiếu token trong `raw_record`; parse failure có issue `invalid` và raw token, không bị coi là missing. 4 `children='NA'` và 24 `country='NULL'` ở City vẫn giữ record. 167 `ZERO_GUESTS` là warning issue, **không cách ly**.
- Holiday giữ một source row cho mỗi lễ; context gộp nhiều tên cùng ngày trước join. `is_holiday` khi không có record là SQL NULL ở Staging, chưa suy thành ngày thường. Weekday Mon–Fri/weekend Sat–Sun từ arrival date; holiday độc lập.
- Weather daily ở `Europe/Lisbon`, ERA5, request 38.72509/-9.1498, returned grid 38.75/-9.25, °C/mm và date range theo source metadata. Duplicate weather date vẫn giữ Staging + issue; context cho ngày ambiguous trả Weather NULL, không nhân bản booking. Missing precipitation không thành 0.
- Transaction nạp row mới + issue/counts + publish một lần; fatal rollback, log failed/reject riêng. Source set cũ cùng fingerprint no-op; contract/source version mới có batch mới nhưng cùng checksum không tăng số row vật lý.

## Gate và bằng chứng hiện tại

| Kiểm tra | Kết quả |
|---|---|
| Raw/checksum | Ba file khớp source set/manifest; không tải lại hoặc sửa raw. |
| PostgreSQL schema/load | PostgreSQL 17.11; ba bảng Staging + control/issue/reject/views có dữ liệu thật; active batch `4dcc2cfc-bed5-4e22-8a4d-fd4ac3f11715`, contract `staging-v1.1`. |
| Active counts | Booking **79.330**, Holiday **38**, Weather **793**; Resort trong `v_booking_current` **0**; structural reject của active batch **0**. |
| Missing/invalid | `children` SQL NULL **4** (raw token `NA` giữ nguyên), `country` NULL **24**; quality issue `MISSING_CHILDREN` **4**, `ZERO_GUESTS` **167**; không mất City record. |
| Context | **793** ngày duy nhất, Weather ambiguous **0**, unknown precipitation **0** trong source hiện tại; join Booking trước/sau **79.330/79.330**. Fixture test có nhiều lễ/ngày, weather duplicate, holiday/Weather unknown, invalid theo từng nguồn. |
| Rerun/failure | Rerun current source `no-op`; PostgreSQL integration test chứng minh mid-load rollback/retry, checksum mismatch và malformed Weather thành failed/reject, active pointer giữ nguyên. |
| Run/evidence | `docs/staging_runbook.md`, `artifacts/staging/{first_load.json,quality_report.json,rerun.json,pytest.xml}` và SQL validation. |

**Kết luận:** gate **STAGING READY về mặt triển khai và kiểm thử PostgreSQL đã đạt** cho ba checksum trong source set hiện hành. Bề mặt bàn giao là `staging.v_booking_current`, `v_holiday_current`, `v_weather_current`, `v_daily_context_current`, không phải đọc trực tiếp bảng vật lý nhiều phiên bản.

**Cần Member 1 review khi nhận bàn giao:** tên/kiểu cột exposed và lineage sang DW; cách dùng context holiday khi nhiều tên cùng ngày; quy tắc eligibility/biến đổi downstream cho ngày/flag/guest invalid, guest component missing, country/ADR NULL và điều kiện xác nhận non-holiday. Các quyết định đó **chưa áp dụng ở Staging** và không phải lý do sửa raw hoặc lọc bớt City record. Chưa xác minh tái lập trên máy Member 1 vì raw bị Git-ignore; runbook yêu cầu chuyển giao đúng checksum.
