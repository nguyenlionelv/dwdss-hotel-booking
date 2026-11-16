# Scripts

Các entry point chạy từ thư mục gốc repository.

- `start_app.py`: chuẩn bị dữ liệu/model/policy và khởi động hệ thống bằng Docker.
- `prepare_app.py`, `prepare_dss.py`: chuẩn bị release và hiệu chỉnh DSS policies.
- `setup_db.py`, `run_pipeline.py`: migration và điều phối Staging/DW/Mart.
- `check_dw_inputs.py`, `run_dw.py`, `refresh_marts.py`: kiểm tra đầu vào, wrapper DW và refresh Mart.
- `profile_booking.py`, `train_models.py`: profiling nguồn và huấn luyện ML.
- `calibrate_*.py`, `audit_dss_sensitivity.py`, `validate_dss_sensitivity.py`, `backtest_dss.py`: hiệu chỉnh và đánh giá DSS.
- `verify_dss_client.py`: kiểm chứng FastAPI qua API client frontend.

Thứ tự chạy theo [App runbook](../docs/app_runbook.md), [Staging runbook](../docs/staging_runbook.md) và [DW/Mart runbook](../docs/dw_runbook.md).
