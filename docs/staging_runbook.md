# STAGING READY — chạy, kiểm tra và bàn giao

Phạm vi: ba raw source trong [source set JSON](data_dictionary/operations_source_set.json): Booking chỉ `City Hotel`, Holiday PT/Lisboa, Weather ERA5 Lisbon; không nạp Event/Resort. [Data dictionary](data_dictionary/operations_sources.md) và [Source → Staging contract](etl_spec/operations_source_to_target.md) định nghĩa field/missing/invalid. Raw file **không sửa/không tải lại** khi checksum khớp.

## Chuẩn bị

- Python 3.12, Docker/Compose và PostgreSQL 17. Đặt ba raw file cùng metadata acquisition theo manifest; raw bị Git-ignore nên cần chuyển giao đúng SHA-256 hoặc tái thu thập bằng acquisition scripts.
- Tạo `.env` từ `.env.example`, đặt `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` cho máy cục bộ. Không commit `.env` hay in mật khẩu vào log.
- Cài `python -m pip install -r pipeline/requirements.txt -r pipeline/requirements-dev.txt` nếu chạy test. Ingestion/profiling thuần file có requirements riêng trong `pipeline/ingestion/` và `pipeline/quality/`.

## Lệnh chạy từ root repo

```powershell
docker compose up -d db
python scripts/setup_db.py
python scripts/run_pipeline.py --to staging --report artifacts/staging/first_load.json
python pipeline/quality/staging_checks.py --report artifacts/staging/quality_report.json
python -m pytest -q tests/pipeline
python scripts/run_pipeline.py --to staging --report artifacts/staging/rerun.json
```

`setup_db.py` áp dụng DDL idempotent tại `database/staging/001_staging.sql`. Lệnh nạp kiểm tra SHA-256 ba file và metadata acquisition trước khi xử lý, đối soát riêng từng nguồn, rồi **công bố atomically** ba nguồn bằng `staging.active_snapshot`. Nếu checksum đã published, rerun trả `no-op` mà không thêm record. Lỗi cấu trúc/đối soát làm batch `failed`, ghi reject/error, không đổi active snapshot; lỗi nghiệp vụ đọc được vẫn ở Staging với raw value + issue. Một attempt bị ngắt được đánh dấu `failed` khi lần chạy kế tiếp lấy session lock. Không chạy `scripts/run_pipeline.py` với đích DW/Mart ở gate này.

## Kiểm tra PostgreSQL

Chạy SQL read-only trong [staging_checks.sql](../database/validation/staging_checks.sql) hoặc dùng `staging_checks.py`. Chỉ các view `staging.v_booking_current`, `v_holiday_current`, `v_weather_current`, `v_daily_context_current` được dùng để bàn giao snapshot đang published; bảng vật lý có thể giữ nhiều phiên bản nguồn. `_source_row_id` Booking/Holiday tính theo **record CSV gốc**, header=1, data đầu=2; Weather = index daily +1. `_batch_id` ở dòng vật lý là batch đầu tiên nạp dòng đó, còn `active_snapshot` + `load_batch_source` xác định version đang có hiệu lực.

Với đúng checksum hiện tại, kỳ vọng `119390 = 79330 City staged + 40060 Resort out-of-scope + 0 unidentified + 0 reject`, Holiday `38 = 38 + 0`, Weather `793 = 793 + 0`; các expected count được ràng với checksum trong source set JSON, **không** là quy tắc cho version mới. Missing/invalid **không trừ** khỏi record staged; issue count có thể chồng lấp. Source mới cần manifest/checksum/config/expected count mới được review trước khi chạy.

`v_daily_context_current` có một dòng cho mỗi City arrival date trong khoảng nguồn. Weekday là thứ Hai–thứ Sáu, weekend thứ Bảy–Chủ nhật; holiday độc lập. Nhiều lễ cùng ngày được gộp tên, không nhân bản Booking. `is_holiday=NULL` khi không có record lễ tại Staging, chưa tự diễn giải là ngày thường. Weather duplicate ngày giữ cả raw records/issue nhưng context đặt Weather `NULL`, `weather_ambiguous=true`; thiếu mưa không là 0. Lịch sử ERA5 không phải forecast thời tiết tại cutoff ML.

## Evidence và handoff

Sau khi chạy, lưu cùng nhau: batch ID, fingerprint/checksum, `artifacts/staging/first_load.json`, `quality_report.json`, `rerun.json`, output `pytest` trên PostgreSQL 17 và output SQL mẫu ở `database/validation/staging_checks.sql`. Test integration tạo một database test tên ngẫu nhiên `staging_test_*`, chỉ xóa **đúng database do fixture vừa tạo** sau khi test; không xóa `hotel_dwdss` hay raw source. File report có thể chứa path/metadata nguồn nhưng không có password.

Member 1 nhận contract, migration/loader/runbook, active-view interface, manifest, quality/reconciliation + issue/reject counts và test evidence. Quy tắc eligibility Staging → DW (guest component thiếu/invalid, ADR/country, holiday coverage) vẫn là quyết định downstream riêng, **chưa áp dụng trong Staging**.
