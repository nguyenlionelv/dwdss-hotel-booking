# Hotel Booking DWDSS

Đồ án Data Warehouse và Decision Support System phục vụ vận hành **City Hotel**, với một domain **Operations Mart**.

## Chức năng

- Phân tích OLAP theo thời gian, country và lịch vận hành.
- Báo cáo KPI về booking, lượng khách đến và nhu cầu vận hành.
- Dự báo lượng khách đến trong 7 ngày tiếp theo và gợi ý chuẩn bị nguồn lực.

## Công nghệ

React + Vite · FastAPI · PostgreSQL 17 · Python ETL/ML · Docker Compose.

`Raw → Staging → Data Warehouse → Operations Mart → OLAP / Reporting / Mining-DSS`

## Tài liệu hiện hành

| Tài liệu | Nội dung |
|---|---|
| [Detailed plan](docs/detailed_plan.md) | Phạm vi, kiến trúc, yêu cầu nghiệp vụ và tiến độ |
| [STAGING READY / Member 2](docs/member2_execution_plan.md) | Trạng thái gate, số liệu đối soát và bàn giao |
| [Staging runbook](docs/staging_runbook.md) | Lệnh nạp ba nguồn, kiểm tra PostgreSQL và rerun |
[Master plan](docs/Hotel_booking_Overall_plan.md) là tài liệu tham khảo về kiến trúc và định hướng mở rộng; phạm vi triển khai theo các tài liệu hiện hành ở trên.
