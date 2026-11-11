# Hotel Booking DWDSS

Đồ án Data Warehouse và Decision Support System phục vụ vận hành **City Hotel**, với một domain **Operations Mart**.

## Chức năng

- Phân tích OLAP theo thời gian, country và lịch vận hành.
- Báo cáo KPI về booking, lượng khách đến và nhu cầu vận hành.
- Dự báo lượng khách đến trong 7 ngày tiếp theo và gợi ý chuẩn bị nguồn lực.

## Công nghệ

React + Vite · FastAPI · PostgreSQL 17 · Python ETL/ML · Docker Compose.

`Raw → Staging → Data Warehouse → Operations Mart → OLAP / Reporting / Mining-DSS`

## Chạy toàn bộ hệ thống

Mở Docker Desktop, từ root repository chạy:

```powershell
python scripts/start_app.py
```

Lệnh tự kiểm tra raw sources, chạy lại Staging → DW → Mart cùng quality gates, chuẩn bị model đúng data version, build Docker images và khởi động app. Model còn hợp lệ được tái sử dụng; model thiếu hoặc khác version được train vào release mới. Giữ nguyên database/volume và `.env` đang có.

- App: [localhost:5173](http://localhost:5173/dss/demand-forecast)
- API: [localhost:8000/docs](http://localhost:8000/docs)

Cần Python 3.12+ và Docker Compose v2; dependency ETL/ML được cài trong Docker. Raw files đã xác minh phải có sẵn vì không được lưu trong Git. Xem [hướng dẫn chạy](docs/app_runbook.md) cho lần thiết lập đầu và xử lý lỗi.

## Tài liệu hiện hành

| Tài liệu | Nội dung |
|---|---|
| [Detailed plan](docs/detailed_plan.md) | Phạm vi, kiến trúc, yêu cầu nghiệp vụ và tiến độ |
| [STAGING READY / Member 2](docs/member2_execution_plan.md) | Trạng thái gate, số liệu đối soát và bàn giao |
| [Staging runbook](docs/staging_runbook.md) | Lệnh nạp ba nguồn, kiểm tra PostgreSQL và rerun |
| [Thiết kế DW đã chốt](docs/dw_design/dw_design.md) | 1 FactBooking + 6 Dim + 1 DailyContext; đầu ra Operations Mart; attributes, mapping, kế hoạch code và nghiệm thu |
| [DW runbook](docs/dw_runbook.md) | Staging → DW đã chạy local: snapshot, loader, quality, rerun và evidence DW READY |
| [DW READY / Member 1](docs/dw_report.md) | Quá trình triển khai, danh mục file, quy tắc dữ liệu và kết quả nghiệm thu |
[Master plan](docs/Hotel_booking_Overall_plan.md) là tài liệu tham khảo về kiến trúc và định hướng mở rộng; phạm vi triển khai theo các tài liệu hiện hành ở trên.
