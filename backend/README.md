# Backend

FastAPI đọc snapshot DW/Mart đã publish, cung cấp Analytics, Reporting và dự báo/DSS.

- `app/main.py`: khởi tạo ứng dụng và đăng ký router.
- `app/api/`, `app/schemas/`: endpoint và cấu trúc request/response.
- `app/core/`, `app/db/`: cấu hình và kết nối PostgreSQL chỉ đọc.
- `app/repositories/`: truy vấn Operations Mart.
- `app/services/`: tính KPI, báo cáo và suy luận; `decision_engine/` diễn giải nhu cầu và phân bổ nguồn lực.
- `requirements.txt`, `Dockerfile`: dependency và đóng gói backend.

Các repository Booking/Guest/Revenue chỉ giữ TODO cho Phase 2; hiện tại API dùng `operations_repository.py`.

Chạy hệ thống theo [App runbook](../docs/app_runbook.md); model được huấn luyện ngoại tuyến trong `ml/`.
