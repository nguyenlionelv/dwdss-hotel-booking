# Member 2 — kế hoạch đạt STAGING READY

**Phạm vi:** ba nguồn thực Booking, Holiday, Weather cho **một Operations Mart của City Hotel**. Event, Resort Hotel và các mart khác không thuộc luồng triển khai. Workbook phân công chỉ dùng tham khảo nhân sự; [data dictionary](data_dictionary/operations_sources.md), [Source → Staging contract](etl_spec/operations_source_to_target.md), [source manifest](data_dictionary/source_manifest_20261017.md) là quy tắc hiện hành. Deadline toàn dự án: 10/11/2026.

## Trạng thái đầu vào

| Hạng mục | Tình trạng / bằng chứng |
|---|---|
| Raw Booking | Có `hotel_bookings.csv` gốc, 119.390 record/32 cột, City 79.330, Resort 40.060; checksum trong manifest. Giữ nguyên file toàn bộ, chỉ lọc khi nạp Staging. |
| Raw Holiday | Có 38 dòng PT/Lisboa do `python-holidays` 0.106 sinh cho 2015–2017; cấu hình và checksum trong manifest. |
| Raw Weather | Có 793 ngày ERA5 đại diện Lisbon, 2015-07-01–2017-08-31; request/response và checksum trong manifest. |
| Profiling | `pipeline/quality/profile_sources.py` và artifact tại `artifacts/profiling/run_20261017_full/` đọc token missing theo field, báo City 79.330 và out-of-scope 40.060. Đây là profiling nguồn, chưa là bằng chứng nạp PostgreSQL. |
| Staging/PostgreSQL | `pipeline/source_to_staging/*.py` còn TODO; chưa có DDL `database/staging`, batch/issue/reject table, test PostgreSQL. **STAGING READY chưa đạt.** |

Trong file hiện tại, `children='NA'` xuất hiện ở 4 City record, `country='NULL'` ở 24; `agent='NULL'` 8.131, `company='NULL'` 75.641. Có 167 City record có tổng khách bằng 0; đây là quan sát/quality issue cần xem xét, **không** phải lý do tự động xóa hoặc cách ly. Raw có các reservation trùng toàn bộ thuộc tính; không khẳng định là nạp trùng nếu `_source_row_id` khác. Số 79.330 City là mục tiêu đối soát Staging cho file này.

## Chuỗi việc cần làm

| Thứ tự | Việc Member 2 thực hiện | Đầu ra / điều kiện xong |
|---|---|---|
| 1. Chốt contract | Xác nhận grain, kiểu và raw field của ba bảng, missing token theo field, issue code/severity, schema control/metadata với Member 1. Không đặt rule downstream vào loader. | Contract được review; mapping/DDL đủ cho ba nguồn, không có Event. |
| 2. Hoàn thiện profiling thành test | Thêm test fixture invalid/structural, kiểm tra source-row-ID trước lọc và holiday trùng ngày. | Profiling đo được missing/invalid/out-of-scope riêng và có mẫu truy vết; không thay thế test PostgreSQL. |
| 3. Dựng PostgreSQL schema | Tạo `staging.stg_booking`, `stg_holiday`, `stg_weather`, batch/source registry, `quality_issue`, `reject`. Typed nullable + raw payload/token; unique `(checksum, row_id)` theo bảng; trạng thái batch (`loading`, `failed`, `published`). | Migration chạy từ database trống; constraint và index có test. |
| 4. Viết ba loader | Booking gán row ID toàn CSV trước lọc, chỉ insert `City Hotel`; đếm Resort/hotel khác và unidentified riêng. Holiday/Weather nạp record đọc được từ raw đúng manifest. Tất cả lưu provenance/checksum/batch/time; field-specific missing → SQL `NULL`, invalid → issue và raw value. | Chạy từ file raw thực, không có silent imputation, record đọc được vẫn trong Staging. |
| 5. Kiểm soát lỗi và công bố | Structural parse/file error → reject hoặc batch failed; business-invalid → Staging + issue. Nạp transactional/shadow; chỉ publish khi đối soát cả ba nguồn và kiểm thử thành công; failed batch không thay snapshot cũ. | Log rõ batch status, lý do và số reject/issue. |
| 6. Quality/reconciliation | Booking: raw = City staged + hotel ngoài phạm vi + hotel không định danh + structural reject. Holiday và Weather có phương trình riêng. Báo missing/invalid/out-of-scope riêng, coverage ngày và context uniqueness. | Báo cáo SQL/CSV cho từng nguồn, không dùng “quarantine” như một nhóm bù số dòng. |
| 7. Test PostgreSQL & runbook | First load, same-source rerun, rerun sau failure, hai reservation giống thuộc tính, missing/invalid/parse failure/reject, multiple holidays, weekday/weekend/holiday, `NULL` weather, join many-to-one, record lineage. Ghi lệnh setup/load/test/query và output thực tế. | Bằng chứng test trên PostgreSQL; người khác có thể tái lập từ raw đúng checksum. |

## Gate STAGING READY — chỉ công bố khi đủ

- Ba nguồn Booking/Holiday/Weather nạp thành công vào PostgreSQL với schema/grain/type/missing representation đã chốt; raw không bị sửa.
- Booking chỉ có City Hotel, `_source_row_id` vẫn theo raw trước lọc. Với file hiện tại: `119.390 = 79.330 City staged + 40.060 ngoài phạm vi + 0 hotel không định danh + 0 structural reject`. Holiday `38 = 38 + 0`; Weather `793 = 793 + 0`. Nếu số đo mới khác, giải thích bằng evidence chứ không ép dữ liệu về số cũ.
- Quality report theo nguồn và field tách missing, invalid, ngoài phạm vi, unidentified và structural reject. Missing `children` không cách ly; invalid đọc được vẫn trong Staging cùng issue/raw value.
- Rerun cùng source/checksum không làm tăng số liệu; booking giống thuộc tính nhưng khác source-row ID không bị xóa. Bất kỳ lỗi nào làm batch thất bại không được công bố snapshot dở dang.
- Có batch/provenance, hướng dẫn chạy và kết quả kiểm thử **thực trên PostgreSQL**. Profiling local hoặc Docker Compose chỉ khởi động DB chưa đủ để đạt gate.

## Handoff sau gate (không phải rule nạp Staging)

Member 2 cùng Member 1 chốt **quy tắc riêng từng field** cho Staging → DW, KPI và ML: cách dùng record có ngày/flag/guest invalid; cách tính tổng khi một guest component `NULL`; ADR/country thiếu; coverage Holiday/Weather; và eligibility của fact/target. Quy tắc phải nêu đầu vào, đầu ra, số record ảnh hưởng và test. Không mặc định thiếu là 0/False/`Unknown`, không đổi Staging, không lặp lại rule “thiếu children thì cách ly”. Sau đó mới xây DW, context daily unique, Operations Mart và đối soát KPI; historical ERA5 chỉ là context phân tích, không dùng như forecast thời tiết tại cutoff ML.

**Phụ thuộc:** Member 1 duyệt thiết kế fact/KPI và tích hợp; Member 3 dùng Mart/feature contract đã được chốt. Các file TODO cho mart khác và Event không chặn STAGING READY. Raw bị Git-ignore nên máy khác phải thu thập lại đúng hash hoặc nhận bản chuyển giao được duyệt. Bộ dữ liệu này mô tả booking/dự kiến đến, không xác nhận check-in thực tế hay occupancy.
