# Tài liệu dự án

- [detailed_plan.md](detailed_plan.md): phạm vi và yêu cầu nghiệp vụ; [Hotel_booking_Overall_plan.md](Hotel_booking_Overall_plan.md) giữ định hướng mở rộng ban đầu.
- `data_dictionary/`: mô tả nguồn, source set hiện hành và acquisition manifests.
- `etl_spec/`: mapping và contract Source → Staging.
- `dw_design/`: thiết kế 1 Fact + 6 Dim + DailyContext, chỉ Operations Mart.
- [dw_report.md](dw_report.md): kết quả triển khai và evidence DW/Mart.
- [app_runbook.md](app_runbook.md), [staging_runbook.md](staging_runbook.md), [dw_runbook.md](dw_runbook.md): hướng dẫn chạy và xử lý lỗi.
- `ml/`: tích hợp model và API; thực nghiệm tại [notebooks/README.md](../notebooks/README.md).
- `dss_*.md`: thiết kế, hiệu chỉnh và đánh giá DSS.
- `frontend/`: đặc tả và hướng dẫn giao diện.

Các kết quả lịch sử gắn với source/run tương ứng; dùng manifest hiện hành và evidence được báo cáo tham chiếu khi đối chiếu.
