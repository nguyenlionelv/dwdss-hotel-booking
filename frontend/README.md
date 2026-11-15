# Frontend

Giao diện React + Vite cho Analytics, Reporting và Demand Forecasting của City Hotel.

- `src/app/`, `src/main.jsx`: router và điểm khởi tạo ứng dụng.
- `src/pages/`: các màn hình; trang Phase 2 hiện chỉ giải thích phạm vi mở rộng.
- `src/components/`: layout, bộ lọc, biểu đồ, bảng và UI dùng chung.
- `src/services/`: gọi API; `src/hooks/`: trạng thái hệ thống.
- `src/lib/`: định dạng, tổng hợp báo cáo và tiện ích.
- `src/data/mockData.js`: dữ liệu mẫu cho Demo Mode được bật rõ ràng.
- `tests/`: kiểm tra dữ liệu hiển thị, API client và trình duyệt.
- `vite.config.js`, `Dockerfile`: proxy API và cấu hình chạy/build.

Khởi động theo [App runbook](../docs/app_runbook.md). Quy ước giao diện tại [DESIGN.md](DESIGN.md).
