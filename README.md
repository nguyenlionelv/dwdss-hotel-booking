# Hotel Booking DWDSS

Đồ án Data Warehouse và Decision Support System cho dữ liệu đặt phòng khách sạn. Repo được tổ chức theo luồng:

`data/raw → pipeline → PostgreSQL (staging → dw → mart) → OLAP/reporting → DSS`

Đây là **repo skeleton** cho giai đoạn thiết kế. Các thư mục và tệp module đã được đặt theo [kế hoạch tổng thể](docs/Hotel_booking_Overall_plan.md); logic ETL, DDL, truy vấn OLAP, mô hình và giao diện sẽ được triển khai theo từng phase. Các tệp scaffold có chú thích `TODO`, chưa được xem là chức năng hoàn tất.

## Phạm vi ưu tiên

1. Xác định nguồn dữ liệu, grain và source-to-target mapping.
2. Nạp raw → staging có kiểm tra số dòng và chất lượng dữ liệu.
3. Xây star schema với `fact_booking` và các conformed dimensions thiết yếu.
4. Tạo 1–2 mart phục vụ các câu hỏi vận hành và hủy phòng; có SQL OLAP drill-down, roll-up, slice/dice và báo cáo KPI nhất quán.
5. Xây một luồng DSS hoàn chỉnh: dự báo demand 7 ngày, đánh giá theo thời gian, rồi ánh xạ dự báo thành cảnh báo/hành động.

Đánh giá chi tiết phạm vi và các rủi ro dữ liệu nằm trong [docs/scope_assessment.md](docs/scope_assessment.md).

## Cấu trúc

| Thư mục | Vai trò |
|---|---|
| `frontend/` | React dashboard cho Analytics, Reporting, DSS |
| `backend/` | FastAPI đọc dữ liệu DW/Mart và phục vụ API |
| `pipeline/` | Ingestion, staging, ETL sang DW và mart, data quality |
| `ml/` | Feature engineering, huấn luyện, đánh giá và suy luận |
| `database/` | DDL, mart SQL, OLAP SQL, validation SQL |
| `data/` | Nguồn raw và dữ liệu mẫu có thể chia sẻ |
| `notebooks/` | Profiling, EDA, thí nghiệm |
| `docs/` | Yêu cầu, kiến trúc, mapping, schema, hướng dẫn demo |
| `reports/` | Mẫu và kết quả báo cáo |
| `artifacts/` | Forecast, metrics, log, ảnh demo sinh ra |
| `scripts/` | Điểm vào của pipeline và tác vụ phụ trợ |
| `tests/` | Kiểm thử dữ liệu và các thành phần |
| `infra/` | Cấu hình triển khai |

Các thư mục rỗng dùng `.gitkeep` để Git theo dõi. Dữ liệu raw, secrets, model binaries và artifacts sinh ra không được commit. Xem [data/README.md](data/README.md) trước khi thêm dữ liệu.

## Gate đầu tiên

Trước khi viết DDL/ETL, nhóm cần chốt: nguồn booking cụ thể, ý nghĩa ngày trong fact, định nghĩa demand, grain `1 row = 1 reservation record`, quy tắc xử lý bản ghi hủy và tập KPI. Đây là các quyết định quyết định độ đúng của toàn bộ pipeline.
