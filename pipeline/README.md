# Pipeline

Luồng dữ liệu: **Raw → Staging → DW → Operations Mart**.

- `ingestion/`: thu thập Booking, sinh Holiday và tải Weather.
- `source_to_staging/`: đọc, kiểm tra, giữ lineage và publish snapshot ba nguồn.
- `staging_to_dw/`: preflight, mapping, biến đổi, nạp DW và publish.
- `dw_to_mart/`: migration, tổng hợp và đối soát Operations Mart.
- `quality/`: profiling và quality checks độc lập.
- `config/`, `mappings/`: cấu hình có version/checksum và bảng mã chuẩn hóa.
- `requirements*.txt`, `Dockerfile`: dependency và môi trường pipeline.

Các module TODO của Event và ba Mart mở rộng được giữ cho Phase 2; luồng hiện hành chỉ nạp Booking/Holiday/Weather và Operations Mart.

Lệnh chạy nằm trong [Staging runbook](../docs/staging_runbook.md) và [DW/Mart runbook](../docs/dw_runbook.md). Các CLI điều phối ở `scripts/`.
