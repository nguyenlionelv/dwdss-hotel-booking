# Các vấn đề sau Mart cần xử lý

Ngày kiểm tra: **09/11/2026** · Nhánh: `RE-CHECK/phase-6`.

Phạm vi: SQL truy xuất, backend/API, frontend. **Cửa sổ dashboard 2 năm gần nhất là lựa chọn đã chấp nhận, không tính là lỗi.** ML/DSS hiện là mẫu thử. Lỗi checksum Mart đã sửa; quality DW và Mart đã đạt. Các vấn đề dưới đây chưa được sửa.

## 1. P1 — API lỗi nhưng frontend vẫn báo Healthy và trả số liệu mẫu

- **Vị trí:** `frontend/src/services/apiClient.js:48`, `analyticsApi.js:45`, `frontend/src/components/layout/Header.jsx:46`.
- **Minh chứng:** Mô phỏng request thất bại vẫn nhận `healthy`, `db_connected=true`, `mart_published=true` và 77.386 booking mẫu. UI không xử lý cờ `is_mock`.
- **Yêu cầu:** Hiển thị lỗi/mất kết nối; chỉ dùng mock trong chế độ demo có nhãn rõ ràng.

## 2. P2 — Coverage thời tiết kiểm tra sai trạng thái

- **Vị trí:** `backend/app/repositories/operations_repository.py:626`, `backend/app/services/reporting_service.py:206`, `database/marts/reporting_views.sql:32`, `database/olap/operations/04_holiday_weather_impact.sql:91`.
- **Minh chứng:** Mart có 793 ngày weather `COMPLETE`; impact API cho 04–31/08/2017 lại báo coverage 0%, thiếu 28 ngày vì code tìm `OBSERVED`.
- **Yêu cầu:** Dùng `COMPLETE` theo contract DW; kiểm thử giá trị coverage kỳ vọng.

## 3. P2 — Frontend roll-up KPI sai mẫu số

- **Vị trí:** `frontend/src/pages/Reports/Operations/OperationsReportsPage.jsx:152`.
- **Minh chứng:** Kỳ 04–31/08/2017, lead time từ Mart là **143,1 ngày**, công thức frontend cho **140,5 ngày**. Code trọng số theo toàn bộ booking; party size/stay length/ADR cũng chưa dùng valid count riêng.
- **Yêu cầu:** API cung cấp sum và valid count; frontend cộng rồi chia lại theo từng measure, kể cả khi lọc ngày.

## 4. P2 — Capacity API tính sai KPI theo weekday/weekend

- **Vị trí:** `backend/app/services/reporting_service.py:401`, dòng 413–414.
- **Minh chứng:** Kỳ 04–31/08/2017, ADR weekday/weekend đúng là **136,91 / 138,67**, API trả **137,38 / 139,62**. Party size đúng **2,1487 / 2,1927**, API trả cùng **2,1616**.
- **Yêu cầu:** Tính sum/count riêng cho từng nhóm; không average daily averages hoặc sao chép tỷ lệ toàn kỳ.

## 5. P2 — CSV biến NULL thành số liệu có vẻ đầy đủ

- **Vị trí:** `frontend/src/services/reportingApi.js:164–178`.
- **Minh chứng:** Fixture `PARTIAL`, observed guests=42, target=NULL xuất thành target=42. Mưa NULL thành 0; holiday NULL thành false.
- **Yêu cầu:** Giữ NULL bằng ô trống; target chỉ có giá trị khi guest `COMPLETE`. Không thay target bằng observed subtotal.

## 6. P2 — API thật chứa departures và YoY hard-code

- **Vị trí:** `backend/app/services/reporting_service.py:246`, `backend/app/schemas/reports.py:27–28`, `backend/app/repositories/operations_repository.py:714`.
- **Minh chứng:** Departures=`max(1, round(arrivals*0.92))`; YoY luôn `+4.2%`, `+1.8%`; top countries luôn nhận `+6.4%`.
- **Yêu cầu:** Tính từ dữ liệu checkout/kỳ so sánh thực tế hoặc bỏ chỉ số chưa hỗ trợ. Đây không phải kết quả truy vấn nguồn.

## 7. P2 — Chú giải biểu đồ không khớp chuỗi dữ liệu

- **Vị trí:** `frontend/src/pages/Reports/Operations/OperationsReportsPage.jsx:625`, `frontend/src/components/charts/TrendChart.jsx:476–477`.
- **Minh chứng:** Trang mô tả arrivals/departures, canvas vẽ observed guests/non-canceled bookings; màu legend cũng khác màu series.
- **Yêu cầu:** Đồng nhất tên, đơn vị và màu giữa dữ liệu, canvas, chú giải. Kết luận từ đọc code; chưa kiểm tra trực tiếp bằng trình duyệt.

## 8. P2 — Tuần không có dữ liệu bị thay bằng kỳ khác
ê ba
- **Vị trí:** `backend/app/repositories/operations_repository.py:793`.
- **Minh chứng:** `/api/reports/operations/weekly-demand?week=2000-W01` trả HTTP 200, kỳ 04–31/08/2017, 2.790 booking.
- **Yêu cầu:** Trả rỗng/not-found cho tuần đã chỉ định. Chỉ chọn kỳ mới nhất khi không truyền kỳ hoặc yêu cầu rõ chế độ đó.

## 9. P2 — Mất kết nối DB trả 500 thay vì lỗi dịch vụ được xử lý

- **Vị trí:** `backend/app/api/metadata.py:52`.
- **Minh chứng:** Mô phỏng PostgreSQL không truy cập được: `/health` báo degraded; metadata, trend, weekly-demand trả 500. Dependency mở kết nối trước `try/except` của endpoint.
- **Yêu cầu:** Bắt lỗi kết nối tại dependency/handler chung, trả 503 với thông báo đã loại thông tin nhạy cảm.

## Căn cứ và bằng chứng

- Công thức eligibility, sum/count, NULL và target: [DW design, mục 9.3](dw_design/dw_design.md); [UI/API specification, mục 1](frontend/ui_specification_and_api_contracts.md). Dùng quy tắc, không lấy số liệu nghiệm thu lịch sử làm expected count hiện tại.
- [Đối chiếu Mart/API](../artifacts/tests/review_main_20261109/probe_results.json): KPI, khoảng báo cáo, response cho tuần không tồn tại.
- [Weather, Capacity, mất kết nối DB](../artifacts/tests/review_main_20261109/edge_probe_results.json).
- [Mô phỏng frontend và CSV](../artifacts/tests/review_main_20261109/frontend_probe_results.json).

Các JSON ghi nhận lần kiểm tra trước khi sửa xuống dòng; thông tin checksum cũ trong đó là lịch sử. Lần tổng hợp này chỉ đối chiếu code, không chạy lại test hoặc sửa ứng dụng. Frontend build và 330 tests đã đạt ở lần rà soát trước sau khi bổ sung đường dẫn import fixture; các ca trên cho thấy bộ test hiện tại chưa bao phủ đủ các lỗi này.
