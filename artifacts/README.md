# Artifacts

Đầu ra và bằng chứng theo từng lần chạy; một số thư mục chỉ xuất hiện sau khi thực thi.

- `staging/`, `dw/`, `mart/`: load, quality, rerun và nghiệm thu từng lớp.
- `profiling/`, `recovery/`: khảo sát nguồn, lineage và bằng chứng phục hồi.
- `ml_serving/`, `startup/`: snapshot/model releases và report khởi động.
- `allocation/`, `dss_v2/`: hiệu chỉnh, validation và đánh giá DSS.
- `forecasting/`, `notebook_execution/`, `notebook_review/`: đầu ra thực nghiệm notebook.
- `tests/`: kết quả kiểm thử và probe theo thư mục run riêng.

Giữ evidence được cấu hình/manifest hoặc báo cáo tham chiếu. Snapshot, fitted models và một số đầu ra lớn được Git-ignore; xem [App runbook](../docs/app_runbook.md) để tạo release mới.
