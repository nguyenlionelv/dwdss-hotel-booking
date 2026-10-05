# Đánh giá phạm vi đồ án Hotel Booking DWDSS

**Ngày đánh giá:** 05/10/2026  
**Hạn trong kế hoạch:** 10/11/2026  
**Nguồn:** [Hotel_booking_Overall_plan.md](Hotel_booking_Overall_plan.md)

## Kết luận

Đề tài và kiến trúc **phù hợp với một bài tập lớn** vì thể hiện được toàn bộ chuỗi nguồn dữ liệu → ETL → staging → DW → Data Mart → OLAP/reporting → DSS. Tuy nhiên, toàn bộ scope hiện tại là **quá rộng cho khoảng 5 tuần** nếu nhóm phải tự tìm/chuẩn hóa dữ liệu và làm demo ổn định: 4 mart, 3 bài toán ML, 4 nguồn, React + FastAPI + Docker. Rủi ro chính là có nhiều màn hình/mô hình nhưng thiếu chứng cứ dữ liệu, kiểm tra chất lượng và đối soát KPI.

## MVP nên hoàn thành trước

| Lớp | Tiêu chí đủ mạnh cho đồ án |
|---|---|
| Data source | Booking là nguồn bắt buộc; calendar/holiday là nguồn tích hợp thứ hai. Weather chỉ thêm khi xác nhận được vị trí và thời gian phù hợp. Event để sau. |
| ETL & staging | Raw bất biến, metadata nguồn, khóa kỹ thuật từng dòng, data profiling, quy tắc xử lý null/invalid, đối soát số dòng và khả năng chạy lại. |
| DW | `fact_booking` ở grain một reservation record; `dim_date`, `dim_hotel`, `dim_channel`, `dim_market_segment` là lõi. Các dimension khác chỉ thêm khi câu hỏi kinh doanh cần. |
| Data Mart | Bắt đầu với `operations` theo hotel × arrival date và một mart/view `revenue_cancellation` theo booking hoặc kỳ báo cáo. Hai mart còn lại là mở rộng. |
| OLAP & reporting | 3–4 câu hỏi kinh doanh có SQL kiểm chứng; thể hiện slice, dice, roll-up và drill-down; một báo cáo KPI dùng cùng định nghĩa với dashboard. |
| DSS | Một bài toán **demand forecast 7 ngày**: baseline seasonal naïve, time split, MAE, đầu ra dự báo → mức nhu cầu → gợi ý hành động. Các mô hình guest mix/cancellation là mở rộng. |
| UI & deployment | Một dashboard/luồng demo đơn giản. Làm API và Docker sau khi số liệu ETL/DW/Mart đã đúng. |

Một mart duy nhất cũng có thể đủ nếu giải thích được grain, business question và OLAP; hai mart cho phép chứng minh rõ hơn việc tách workload. Chất lượng thực thi quan trọng hơn số lượng mart.

## Điểm cần chốt sớm trong kế hoạch

1. **Ngày trong fact và target dự báo.** Danh sách field booking nêu `arrival_date_*` nhưng không có ngày tạo booking. Vì vậy có thể đo *lượt đến dự kiến theo ngày đến*, còn “số booking phát sinh theo ngày đặt” chưa có căn cứ. Phải chọn tên KPI và filter cancellation cho nhất quán. Với demand vận hành, đếm booking không bị hủy hoặc khách thực đến cần được định nghĩa trước khi aggregate.
2. **Khóa và duplicate.** Danh sách field không nêu booking ID. Nên cấp `source_row_id`/hash có provenance ở ingestion để trace; không tự động xóa các dòng trùng toàn bộ cột vì chúng có thể là hai reservation hợp lệ.
3. **Weather/holiday join.** `hotel` trong plan mới là City/Resort, chưa đủ chứng minh tọa độ. Chỉ join weather/holiday khi biết được địa điểm, múi giờ và ngày phù hợp. Nếu không, dùng calendar cơ bản và ghi giới hạn; đừng tạo quan hệ giả.
4. **Thông tin biết tại thời điểm dự báo.** Forecast 7 ngày cần backtest tại một ngày chốt trong lịch sử vì dữ liệu quá khứ không thể chứng minh một dự báo cho 2026. Weather quan sát tương lai, `reservation_status`, `reservation_status_date` hay kết quả hủy sau ngày chốt không thể làm feature cho quyết định tại ngày chốt.
5. **Chỉ số tiền.** `adr × stay_nights` là *estimated booking value*, không phải doanh thu kế toán. Tỷ lệ và trung bình khi roll-up phải tính từ tổng tử/mẫu gốc, không lấy trung bình của các tỷ lệ/trung bình theo ngày.
6. **Tính khả dụng của các mart.** Guest/Customer Mart và Booking Performance Mart có thể được phục vụ bằng view từ fact chung ở giai đoạn đầu; không cần 4 bảng vật lý nếu cùng lặp dữ liệu và công thức.

## Gate đề xuất

1. **07/10 — Chốt thiết kế:** nguồn và giấy phép sử dụng, business question, KPI, grain, target, phạm vi MVP.
2. **13/10 — Dữ liệu sẵn sàng:** profiling và source-to-target mapping; chứng minh join ngoài nếu có.
3. **25/10 — DW đúng:** row reconciliation, PK/FK, kiểm thử KPI trên một hotel và khoảng ngày cố định.
4. **29/10 — Mart/OLAP đúng:** SQL drill-down/roll-up và báo cáo khớp với DW.
5. **05/11 — DSS hoạt động:** backtest theo thời gian, baseline, metric, rule và demo sử dụng output.
6. **07/11 — Freeze tích hợp:** chạy lại pipeline từ dữ liệu mẫu; sửa lỗi và hoàn thiện báo cáo đến 10/11.

Nếu thời gian eo hẹp, ưu tiên hoàn thành các gate 1–4 và một DSS đơn giản. Chỉ mở rộng sang guest mix, cancellation ML, weather và nhiều màn hình sau khi end-to-end MVP chạy ổn định.
