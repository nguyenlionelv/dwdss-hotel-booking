# Database

SQL cho PostgreSQL, phục vụ City Hotel và Operations Mart.

- `staging/`: schema tiếp nhận nguồn, registry, issues và published snapshot.
- `dw/`: migration theo thứ tự `001`–`004`, gồm bảng điều khiển, sáu dimension, fact, context và daily quality.
- `marts/`: DDL, refresh và reporting views của Operations Mart.
- `olap/operations/`: các truy vấn slice/dice, roll-up/drill-down, pivot và ngữ cảnh.
- `validation/`: SQL kiểm tra chất lượng và đối soát.

SQL TODO và các thư mục OLAP của Guest/Customer, Revenue/Cancellation, Booking Performance được giữ cho Phase 2, chưa tham gia migration hiện hành.

Dùng CLI theo [Staging runbook](../docs/staging_runbook.md) và [DW/Mart runbook](../docs/dw_runbook.md). Giữ nguyên SQL migration đã được ghi checksum trong database.
