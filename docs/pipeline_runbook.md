# Chạy ETL bằng Docker

## Chuẩn bị

- Mở Docker Desktop; chạy lệnh từ root repository.
- Chuẩn bị `.env` theo [.env.example](../.env.example).
- Có đủ raw và acquisition metadata theo [manifest](data_dictionary/operations_source_set.json), cùng evidence coverage được tham chiếu trong `pipeline/config/coverage_selected_source_set.json`.

## Chạy toàn luồng

```powershell
docker compose run --rm --build etl
```

Lệnh build image, chờ PostgreSQL healthy rồi chạy:

**Kiểm tra input → setup/nạp/quality/rerun Staging → preflight/migration/nạp/quality/rerun DW và Operations Mart.**

ETL dùng `db:5432` trong mạng Docker, mount raw chỉ đọc và lưu kết quả trên máy qua thư mục `artifacts`. Mỗi lần gọi chạy đủ luồng; cùng input hợp lệ thì các bước nạp trả `no-op`. Service ETL không tự chạy khi bật app bằng `docker compose up -d`.

## Xem kết quả

Console in đường dẫn `artifacts/etl/run_<id>/`. Kiểm tra:

- `summary.json`: `status=completed`, `verified=true`, `mart_verified=true`.
- `staging_quality.json`: quality Staging đạt.
- `dw/summary.json` và `dw/quality_report.json`: DW/Mart hoàn tất, quality đạt.

Khi lỗi, lệnh trả mã khác `0`; xem `failed_step` và report tương ứng. Runner dừng ở bước lỗi; các publication đã commit ở bước trước vẫn có hiệu lực.

Tùy chọn `--config`, `--dbname`, `--output-dir` dùng qua `python scripts/run_etl.py` sau tên service; đường dẫn phải là đường dẫn trong container, output chưa tồn tại và database được chỉ định đã có sẵn. Ví dụ:

```powershell
docker compose run --rm etl python scripts/run_etl.py --output-dir /app/artifacts/etl/my_new_run
```
