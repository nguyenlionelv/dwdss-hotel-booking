# Tests

- `pipeline/`: parser, loader, snapshot và quality Staging.
- `warehouse/`: transform, context, migrations, transaction và CLI DW.
- `marts/`: tổng hợp, reconciliation và SQL reporting/OLAP.
- `backend/`: API metadata, Analytics và Reporting.
- `ml/`, `dss/`: model serving, cutoff dữ liệu, quy tắc DSS và phân bổ.
- `startup/`: điều phối khởi động, model release và policy readiness.
- `fixtures/`: dữ liệu nhỏ và expected values độc lập.

Dùng Python trong `.venv`; PostgreSQL integration tạo và dọn database test riêng. Chọn `--basetemp` mới trong workspace và dùng `--tb=short`.

Lệnh kiểm tra theo [DW/Mart runbook](../docs/dw_runbook.md), [ML serving handoff](../docs/ml/ml_serving_handoff.md) và [DSS allocation](../docs/dss_resource_allocation.md). Kiểm tra frontend nằm trong `frontend/tests/`.
