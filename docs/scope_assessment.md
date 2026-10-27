# Phạm vi triển khai DWDSS Hotel Booking

Phạm vi hiện hành là **một Operations Mart cho City Hotel**. Ba nguồn bắt buộc: Booking (chỉ nạp City Hotel vào Staging), Holiday PT/Lisboa và Weather ERA5 lịch sử đại diện Lisbon cùng khoảng ngày. Raw Booking gốc giữ nguyên cả hai hotel. Event, Resort Hotel downstream, ba mart khác và các bài toán ML khác ngoài phạm vi.

**Quyết định 24/10/2026:** xây DW **1 FactBooking + 6 Dim + 1 DailyContext** theo [thiết kế hợp nhất](dw_design/dw_design.md). Đây là mở rộng cấu trúc DW, không mở thêm Mart đầu ra: Operations hiện chỉ dùng Date/Country/DailyContext nhưng ETL phải nạp và kiểm tra đủ sáu chiều.

| Lớp | Grain / cam kết |
|---|---|
| Source → Staging | Một record City Hotel theo vị trí raw gốc; một holiday record; một weather daily entry. Missing theo field → SQL `NULL`; invalid đọc được → Staging + issue; structural error → reject/batch failure. Đối soát ba nguồn, rerun idempotent, chỉ publish batch thành công. |
| DW | Một FactBooking theo source reservation record, sáu Dim Date/Country/Channel/MarketSegment/CustomerProfile/RoomType; RoomType hai vai trò. Date key theo arrival date; không có DimHotel/hotel_key. Xử lý eligibility/missing/invalid downstream theo rule từng field được Member 2 chốt và Member 1 duyệt; cấu trúc đã chốt không tự phê duyệt rules còn đề xuất. Không xóa reservation giống thuộc tính khi chưa chứng minh nạp trùng. |
| Context/Mart | Một context/ngày sau khi gộp nhiều lễ cùng ngày; left join bằng date_key không nhân bản booking. Operations Mart một dòng/ngày đến; breakdown country có khóa (date_key,country_key). Tên City Hotel, địa điểm Lisbon và timezone Europe/Lisbon lưu ở cấu hình/metadata. Weekday Mon–Fri, weekend Sat–Sun; holiday độc lập; weather/holiday thiếu không suy thành 0/false. |
| OLAP/Reporting/ML | Cùng định nghĩa KPI và coverage; dự báo proxy lượng khách không hủy 7 ngày theo cutoff lịch sử. Weather ERA5 chỉ dùng phân tích lịch sử, không là weather forecast biết trước tại cutoff. |

Gate gần nhất là **STAGING READY**: ba bảng Staging, provenance/batch/issue/reject, quality report, đối soát và bằng chứng chạy/test trên PostgreSQL. Xem [contract](etl_spec/operations_source_to_target.md) và [kế hoạch Member 2](member2_execution_plan.md). `Hotel_booking_Overall_plan.md` là tài liệu ý tưởng rộng; những phần về bốn mart, Event, imputation và lọc City ở DW không phải hướng dẫn triển khai hiện hành.
