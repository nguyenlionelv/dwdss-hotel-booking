# DWDSS Hotel Booking — Detailed Plan: Operations Mart

> **Phạm vi hiện tại:** Operations Mart cho City Hotel (MVP, sau này có thể bổ sung thêm).  
> **Đầu ra:** OLAP Operators, Reporting KPI và Mining dự đoán lượng khách 7 ngày tới.  
> **Deadline:** 10/11/2026.  
> **Tham chiếu:** [Hotel_booking_Overall_plan.md](Hotel_booking_Overall_plan.md). Tài liệu này là kế hoạch triển khai theo phạm vi đã thu gọn, tập trung ở mức low-level.

**Tài liệu triển khai:** [Schema và hợp đồng dữ liệu](schema_and_data_contracts.md) quy định mapping và input/output từng giai đoạn; [hợp đồng API/ML](api_ml_contracts.md) quy định request/response, model artifact và inference sẽ được upload lên.

## 1. Phạm vi và yêu cầu nghiệp vụ

**Câu hỏi chính:** City Hotel có bao nhiêu khách đến theo từng thời điểm, demand biến động thế nào và cần chuẩn bị vận hành cho 7 ngày tiếp theo ra sao?

| ID kế thừa | Yêu cầu trong phiên bản này | Đầu ra |
|---|---|---|
| DO-A01 | Phân tích lượng khách và booking theo ngày/tuần/tháng của City Hotel | Biểu đồ xu hướng, bảng tổng hợp, drill-down |
| DO-A02 | So sánh weekday/weekend và mùa vụ theo tháng/quý | Bảng pivot, biểu đồ so sánh |
| DO-A03 | So sánh holiday/non-holiday khi xác nhận được lịch nghỉ phù hợp | Lượng khách, thời gian ở trung bình, KPI theo nhóm ngày |
| DO-A04 | Phân tích weather và demand khi mapping địa điểm hợp lệ | Biểu đồ so sánh giữa thời tiết đẹp, xấu.. hoặc so sánh theo tiêu chí khác (phần này bổ sung) |
| DO-A05 | Phân tích country và demand | Biểu đồ hoặc danh sách các quốc gia và tổng lượng khách từ quốc gia theo tháng/quý |
| DO-R01 | Báo cáo nhu cầu vận hành hàng tuần | Bộ KPI cố định và bảng theo ngày của City Hotel |
| DO-R02 | Tổng hợp lượng khách và workload để chuẩn bị vận hành | Ngày cao điểm, quy mô nhóm khách, stay nights, forecast |
| DO-M01 | Dự đoán lượng khách đến từng ngày trong 7 ngày tiếp theo | Forecast, mức LOW/NORMAL/HIGH và gợi ý chuẩn bị |

Operations Mart phục vụ cả ba workload trên. Guest / Customer, Revenue & Cancellation, Booking / Commercial Performance và các mô hình tương ứng nằm ngoài phiên bản này. Chỉ số hủy booking được giữ làm thông tin hỗ trợ diễn giải demand, không tạo thêm domain.

Toàn bộ DW, Mart, OLAP, Reporting và Mining trong phiên bản này chỉ xử lý booking của **City Hotel**. Raw và staging giữ dữ liệu nguồn để truy vết; bước Staging → DW lọc phạm vi City Hotel.

## 2. Kiến trúc tổng quát

Giữ các thành phần, công nghệ và cách phân lớp của kế hoạch gốc:

```text
                         USER
                          │
                          ▼
                ┌─────────────────┐
                │ React + Vite    │
                │ Web Dashboard   │
                └────────┬────────┘
                         │ REST / JSON
                         ▼
                ┌─────────────────┐
                │ FastAPI Backend │
                └───────┬─────────┘
                        │
          ┌─────────────┼──────────────┐
          ▼             ▼              ▼
    PostgreSQL      ML Artifacts     Report Logic
   DW / Marts       .joblib/.pkl
          ▲
          │
    Python ETL Jobs
          ▲
          │
 Booking / Weather / Holiday / Event
```

```text
┌──────────────────────────────────────────────┐
│                Docker Compose                │
│  frontend | backend | postgres | etl-job     │
└──────────────────────────────────────────────┘
```

| Thành phần | Công nghệ và trách nhiệm |
|---|---|
| Frontend | React + Vite, React Router, Recharts, Axios/Fetch; hiển thị filter, chart, bảng và KPI |
| Backend | FastAPI; nhận yêu cầu, kiểm tra tham số, truy vấn dữ liệu và trả REST/JSON |
| Database | PostgreSQL 17; ba schema `staging`, `dw`, `mart` |
| ETL | Python, pandas, SQLAlchemy/psycopg, requests, logging; chạy độc lập với request của dashboard |
| Mining | Python, pandas, scikit-learn (Linear Regression), joblib, XGBoost/LightGBM (nên làm nhiều mô hình để so sánh, tham khảo https://chatgpt.com/share/6ac45d98-ac90-83ec-9626-2fba75dbac84)|
| Triển khai | Docker Compose với frontend, backend, db và etl; PostgreSQL có persistent volume |

**Luồng dữ liệu:** Sources → Ingestion → Staging → ETL → Data Warehouse → Operations Mart → OLAP / Reporting / Mining → DSS.

**Luồng ML:** Mart → Feature Engineering → Train/Evaluate offline → model artifact; React → FastAPI → đọc Mart/features và model → inference → kết quả JSON.

Frontend gọi FastAPI; backend sử dụng dữ liệu DW/Mart chính thức. ETL và training chạy riêng, không chạy khi mở dashboard hay khi backend khởi động. Weather/Event vẫn thuộc khả năng tích hợp của kiến trúc; phạm vi baseline của nguồn được quy định bên dưới.

## 3. Quy ước dữ liệu và thiết kế DW

### 3.1. Ngày, grain và định nghĩa lượng khách

- **FactBooking:** một dòng tương ứng một reservation record của City Hotel trong nguồn.
- **Ngày phân tích:** `arrival_date`, dựng từ năm/tháng/ngày đến; không diễn giải thành ngày tạo booking.
- **Operations Mart:** một dòng = một `hotel_key × date_key`, với `hotel_key` cố định là City Hotel và `date_key` là ngày đến; tương đương một dòng mỗi ngày của City Hotel.
- **Lượng khách / target:** tổng `adults + children + babies` của booking City Hotel có `is_canceled = 0`, nhóm theo ngày đến.
- Đây là **proxy lượng khách đến từ booking không hủy**. Chỉ gọi là khách thực đến khi dữ liệu xác nhận được; không diễn giải thành số khách đang lưu trú, occupancy hay công suất phòng.
- `total_stay_nights` là tổng số đêm của các booking thuộc ngày đến đó; không phải số phòng/khách đang lưu trú trong chính ngày đó.

### 3.2. Nguồn và field cần dùng

| Nguồn | Field chính | Quy tắc sử dụng |
|---|---|---|
| Booking — bắt buộc | `hotel`, `arrival_date_*`, `is_canceled`, `adults`, `children`, `babies`, `stays_in_weekend_nights`, `stays_in_week_nights`, `lead_time`, `adr`, `country` | Giữ raw bất biến; ghi nguồn, thời gian bao phủ và định nghĩa field; chỉ nạp bản ghi có `hotel = 'City Hotel'` vào DW |
| Calendar/Holiday | Ngày, thứ, tuần, tháng, quý, năm; ngày lễ, quốc gia/vùng, tên lễ | Calendar tạo từ lịch; holiday phải có nguồn và mapping với Portugal, hoặc thành phố (vùng) của City Hotel |
| Weather — có điều kiện | Ngày, địa điểm, nhiệt độ trung bình, lượng mưa, độ ẩm, gió, mã thời tiết | Chỉ tích hợp khi chứng minh được mapping City Hotel–location và thời gian |
| Event — để mở rộng | Tên, loại, ngày bắt đầu/kết thúc, địa điểm | Chưa triển khai trong baseline |

Nguồn booking cụ thể, phạm vi ngày và mapping địa điểm phải được xác nhận ở bước profiling. Nếu holiday chưa mapping được, đánh dấu chưa xác định; chỉ so sánh weekday/weekend, không gán mọi ngày thành non-holiday.

### 3.3. Bảng tối thiểu

| Bảng/lớp | Grain và nội dung |
|---|---|
| `staging.stg_booking` | Một dòng nguồn; dữ liệu gần raw và metadata `_source_file`, `_source_row_id`, `_batch_id`, `_ingested_at` |
| `staging.stg_holiday` | Một ngày lễ × phạm vi địa lý; giữ provenance |
| `staging.stg_weather` — có điều kiện | Ngày/giờ × location theo nguồn; chuẩn hóa về daily trước khi tích hợp |
| `dw.dim_date` | Một ngày; date key, full date, year, quarter, month, ISO week/year, day of week, is_weekend |
| `dw.dim_hotel` | Một bản ghi City Hotel; key, tên và mapping địa lý đã được xác nhận |
| `dw.dim_country` | Một mã country; key, code, tên; có Unknown để giữ booking thiếu country |
| `dw.fact_booking` | Booking key, source row reference, date/hotel/country foreign keys, booking_count = 1, cancellation flag, số khách từng nhóm, tổng khách, stay nights, lead time, ADR |
| Context holiday/weather | Chuẩn hóa còn tối đa một bản ghi cho mỗi ngày × địa điểm cần join; nhiều tên lễ tổng hợp trong cùng context |

Giữ `dim_date`, `dim_hotel` và `dim_country` để phục vụ Operations và mở rộng sau; hiện tại mọi `hotel_key` trong fact và Mart đều tham chiếu City Hotel. Dimension channel/segment/customer không cần đưa vào luồng phục vụ Operations hiện tại.

## 4. ETL và hợp đồng giữa các lớp

| Bước | Xử lý cụ thể | Output / điều kiện hoàn thành |
|---|---|---|
| Sources → Staging | Nạp raw, thêm metadata, định danh dòng ổn định bằng nguồn/file và vị trí dòng hoặc ID thật; profile null, giá trị bất thường, phạm vi ngày | Staging truy ngược được raw; đối soát số dòng mỗi batch |
| Staging → DW | Chuẩn hóa hotel và chỉ giữ `hotel = 'City Hotel'`; parse arrival date/kiểu dữ liệu; tính khách và stay nights; áp dụng quy tắc missing/invalid; nạp dimension trước fact | PK/FK hợp lệ; đối soát riêng dòng ngoài phạm vi, dòng City Hotel được nhận và dòng bị cách ly; không nhân bản fact khi join |
| DW → Mart | Aggregate booking City Hotel theo ngày đến; join calendar và context; tạo chuỗi ngày liên tục trong khoảng nguồn City Hotel bao phủ | Duy nhất một dòng City Hotel × ngày; tổng KPI khớp DW |
| Mart → Features | Tạo target, lag và rolling trên chuỗi ngày của City Hotel; gắn ngày chốt dữ liệu | Feature dataset theo thời gian, truy vết được Mart và chỉ dùng thông tin đã biết |

**Quy tắc xử lý:**

- Ngày không hợp lệ, số khách/số đêm âm, tổng khách bằng 0 hoặc cancellation flag ngoài 0/1 phải được cách ly và ghi lý do theo hợp đồng dữ liệu.
- Baseline cách ly booking thiếu `children`, không tự điền 0; thay đổi quy tắc sau profiling phải cập nhật contract. Không xóa toàn bộ dòng chỉ vì thiếu field phụ như ADR/weather.
- Giữ các reservation có cùng thuộc tính nếu không có bằng chứng là nạp trùng. Chạy lại cùng batch không tạo thêm booking.
- Các dòng thuộc hotel khác được ghi nhận là ngoài phạm vi, không tính là dữ liệu lỗi; đối soát đủ dòng staging và kiểm tra DW/Mart chỉ chứa City Hotel.
- Holiday/weather được tổng hợp đúng grain trước khi join; dùng left join để không làm mất booking vì thiếu context.
- Ngày không có booking trong khoảng dữ liệu được xác nhận đầy đủ có count = 0; ngày thiếu dữ liệu nguồn giữ trạng thái thiếu, không tự điền 0.
- Full refresh trong baseline phải có thể chạy lại và chỉ công bố Mart sau khi kiểm tra thành công; log batch, số dòng và thời điểm cập nhật.

**Artifact cần có:** data dictionary, source-to-target mapping, quy tắc chất lượng dữ liệu, báo cáo reconciliation và log pipeline.

## 5. Operations Mart và công thức KPI

**Bảng phục vụ chính:** `mart.daily_hotel_operations`, khóa duy nhất `(hotel_key, date_key)`, với `hotel_key` cố định là City Hotel. View tuần/tháng đọc từ bảng này, không hình thành Mart mới.

**View phục vụ DO-A05:** `mart.daily_hotel_operations_by_country`, grain `(hotel_key, date_key, country_key)`, tổng hợp từ fact và dùng cùng công thức KPI. Country là thuộc tính của booking; bao gồm nhóm Unknown. Forecast vẫn dùng view tổng theo ngày; không join hai aggregate rồi cộng measure.

Quy ước: **A** là các booking hợp lệ của City Hotel có ngày đến thuộc nhóm đang xét; **B** là tập con của A có `is_canceled = 0`.

| Field/KPI | Công thức và ý nghĩa |
|---|---|
| `total_bookings` | Số booking trong A, bao gồm booking hủy |
| `non_canceled_bookings` | Số booking trong B |
| `total_cancellations` | Số booking trong A có `is_canceled = 1` |
| `cancellation_rate` | `total_cancellations / total_bookings` |
| `total_adults / total_children / total_babies` | Tổng từng nhóm khách trong B |
| `total_guests` | Tổng adults + children + babies trong B; dùng làm target forecast |
| `total_stay_nights` | Tổng weekend nights + weekday nights trong B |
| `avg_party_size` | `total_guests / non_canceled_bookings` |
| `avg_stay_nights` | `total_stay_nights / non_canceled_bookings` |
| `avg_lead_time / avg_adr` | Trung bình giá trị hợp lệ trong B; giữ tổng và số bản ghi hợp lệ của từng field để roll-up |
| Average guests/day | Tổng khách của City Hotel chia số ngày lịch đầy đủ trong kỳ |
| Peak demand day | Ngày có tổng khách cao nhất sau khi áp dụng filter; trả các ngày đồng hạng |

Calendar/context gồm full date, year/quarter/month, ISO week/year, day of week, is_weekend, is_holiday/holiday_name khi xác định được; weather là bổ sung.

**Quy tắc tổng hợp:** cộng các measure dạng count/sum; tính lại tỷ lệ và trung bình từ tổng tử số/mẫu số, không lấy trung bình các tỷ lệ/trung bình theo ngày. Mẫu số bằng 0 trả null. Kỳ thiếu dữ liệu phải có nhãn coverage. So sánh holiday/weekend nên có cả tổng khách và khách trung bình/ngày để xét khác biệt số ngày.

## 6. Analytics — OLAP Operators

Các bộ lọc chung: khoảng ngày đến, country, weekday/weekend và holiday nếu khả dụng. Phạm vi hotel cố định là City Hotel. Measure chọn từ danh mục KPI thống nhất ở mục 5.

| Operator | Thao tác cần hỗ trợ | Ví dụ trong Operations |
|---|---|---|
| Slice | Cố định một dimension/giá trị | Chọn một năm và xem demand theo tháng của City Hotel |
| Dice | Lọc đồng thời nhiều dimension/điều kiện | Một quý cụ thể, chỉ cuối tuần |
| Roll-up | Tổng hợp từ mức chi tiết lên mức cao hơn | Ngày → tháng → quý → năm; ngày → tuần theo ISO week/year |
| Drill-down | Đi xuống mức chi tiết, giữ bộ lọc hiện tại | Năm → quý → tháng → ngày |
| Pivot | Đổi trục trình bày trên cùng dữ liệu tổng hợp | Hàng = tháng, cột = weekday/weekend; đổi sang hàng = weekday/weekend, cột = tháng |

Đầu ra tối thiểu: biểu đồ xu hướng khách/booking, bảng pivot. Holiday/weather là phân tích bổ sung theo điều kiện dữ liệu; kết quả thể hiện quan hệ quan sát được, không khẳng định quan hệ nhân quả. Nghiên cứu bổ sung thêm, hoặc điều chỉnh lại các business needs.

**Nghiệm thu:** mỗi operator có ví dụ thao tác và truy vấn đối soát; chart và bảng thống nhất số liệu, drill-down rồi roll-up không làm đổi tổng.

## 7. Reporting KPI

| Báo cáo | Nội dung cố định |
|---|---|
| **DO-R01 — Weekly Demand Report** | Tổng booking, booking không hủy, tổng khách, khách trung bình/ngày, ngày cao điểm, avg stay nights, weekend/holiday demand; cancellation rate là KPI hỗ trợ |
| **DO-R02 — Operations Capacity Summary** | Lượng khách lịch sử và forecast 7 ngày, ngày dự kiến cao điểm, avg party size, stay-night workload theo nhóm ngày đến, mức nhu cầu và gợi ý chuẩn bị |

Mặc định báo cáo của City Hotel theo tuần Thứ Hai–Chủ Nhật, có chọn kỳ/quý/tuần xem. Hiển thị khoảng ngày thực tế, coverage, thời điểm cập nhật và định nghĩa KPI; tuần chưa đủ ngày phải được ghi rõ. Xuất CSV theo cùng filter với bảng trên web.

Historical actual và forecast có cột/nhãn riêng. Báo cáo capacity chỉ cung cấp tín hiệu lập kế hoạch; chưa tính occupancy, số phòng cần dùng hay số nhân sự cần bố trí vì chưa có dữ liệu inventory/capacity.

**Nghiệm thu:** với City Hotel và cùng khoảng ngày thì Reporting KPI = Analytics KPI = kết quả đối soát từ DW.

## 8. Mining — Dự đoán lượng khách 7 ngày tới

### 8.1. Input và feature

- Nguồn chính thức: `mart.daily_hotel_operations`; feature dataset: `mart.demand_features`.
- Target: `total_guests` mỗi ngày của City Hotel, theo đúng định nghĩa tại mục 3.
- Feature baseline: guest lag 1/7, rolling mean 7/14; day of week, month, is_weekend, holiday đã biết. Tính trên chuỗi ngày của City Hotel, rolling chỉ dùng các ngày trước ngày dự báo; `hotel_key` chỉ dùng định danh, không làm feature vì là hằng số.
- Dòng thiếu lịch sử cho lag/rolling không được lấp bằng dữ liệu tương lai; loại khỏi tập train và ghi số dòng.
- Baseline chỉ dùng lịch và lịch sử demand. Weather chỉ thêm nếu có dự báo thời tiết được phát hành trước thời điểm chốt; không dùng thời tiết quan sát của các ngày cần dự đoán.
- Không dùng trạng thái hủy/kết quả lưu trú chưa biết tại thời điểm dự báo làm feature. Với nguồn chỉ có trạng thái cuối cùng, ghi rõ giới hạn của backtest lịch sử, không tuyên bố đã mô phỏng đầy đủ dữ liệu vận hành thời gian thực.

### 8.2. Huấn luyện và dự báo

1. Chia chuỗi dữ liệu City Hotel thành train → validation → test theo thời gian; xác định mốc cụ thể sau profiling. Chỉ fit model, preprocessing và tham số trên train.
2. Tạo baseline bắt buộc **seasonal naive** (dự báo bằng lượng khách cùng thứ tuần trước).
3. So sánh **Linear Regression**, **Random Forest regression** và **XGBoost** với baseline; Ridge là biến thể tuyến tính có thể thử. Dùng cùng split/origin theo hợp đồng ML để tạo bảng so sánh trong report.
4. Forecast tại ngày chốt **T** cho **T+1 đến T+7**. Với mô hình regression, dự báo lần lượt từng ngày và dùng giá trị vừa dự báo để cập nhật lag/rolling cho các bước tiếp theo; không đọc actual sau T.
5. Backtest các cửa sổ 7 ngày theo thời gian, dùng cùng cutoff và dữ liệu khả dụng cho baseline và mô hình. Chọn mô hình theo validation rồi đánh giá trên test chưa dùng để chọn.
6. Lưu model, feature schema, thời gian train, cutoff, version và metrics; dự báo không âm. Giữ giá trị số thực để đánh giá, chỉ làm tròn khi hiển thị số khách.

Nếu dataset chỉ có dữ liệu lịch sử, “7 ngày tới” được tính từ cutoff trong dataset. Demo hiển thị ngày chốt này, không gán forecast lịch sử thành dự báo cho ngày hiện tại năm 2026.

### 8.3. Đánh giá và output

**Metrics:** MAE là chính, RMSE bổ sung; báo cáo cho City Hotel trên toàn bộ test và từng bước dự báo h = 1…7. So sánh với baseline trên cùng các cửa sổ. Nếu mô hình phức tạp chưa tốt hơn baseline, dùng baseline và ghi rõ kết quả.

Mỗi lần dự báo trả **7 dòng cho City Hotel**, gồm: `as_of_date`, `forecast_date`, `hotel_key` (City Hotel), `predicted_guest_count`, `demand_level`, `model_version`, `generated_at`. Có thêm chart actual/forecast và tổng khách dự kiến trong 7 ngày.

**Rule DSS baseline:** tính mean và standard deviation của lượng khách City Hotel trên 8 tuần lịch sử đầy đủ gần nhất đến T; HIGH nếu dự báo > mean + std, LOW nếu < max(0, mean − std), còn lại NORMAL. Nếu thiếu lịch sử, hiển thị chưa đủ dữ liệu phân mức. Backtest tính lại ngưỡng tại từng cutoff.

| Mức | Gợi ý vận hành |
|---|---|
| HIGH | Rà soát khả năng tiếp nhận, chuẩn bị nhân lực và workload housekeeping/F&B |
| NORMAL | Duy trì kế hoạch vận hành, theo dõi thay đổi |
| LOW | Rà soát phân bổ ca và lượng chuẩn bị theo nhu cầu thấp |

**Nghiệm thu:** tái tạo được training/backtest, chứng minh không dùng future actual trong forecast, có bảng metric so với baseline và đầu ra đủ 7 ngày cho City Hotel.

## 9. API, giao diện và tích hợp

| Nhóm | Hợp đồng tối thiểu |
|---|---|
| Metadata | Thông tin City Hotel, khoảng ngày khả dụng, dimension/measure hỗ trợ, trạng thái holiday/weather và thời điểm cập nhật |
| Analytics Operations | Nhận filter, grain thời gian, measure và trục pivot; trả dimension, measure, bảng/chart và coverage |
| Reports Operations | Nhận kỳ báo cáo; trả KPI cố định của City Hotel, bảng theo ngày và dữ liệu xuất CSV |
| Demand Forecast | Nhận cutoff; hotel cố định là City Hotel, horizon cố định 7; trả forecast, demand level, gợi ý, model version và cutoff |

Giữ các nhóm route của kiến trúc gốc: `/api/metadata/...`, `/api/analytics/operations/...`, `/api/reports/operations/...`, `/api/dss/demand-forecast`. Backend cố định phạm vi City Hotel và kiểm tra filter/measure hợp lệ; dữ liệu forecast/actual thiếu phải trả trạng thái rõ ràng.

Frontend gồm ba màn hình **Operations Analytics**, **Operations Reports**, **Demand Forecast**; hiển thị City Hotel cố định, dùng chung date filters khi phù hợp, có loading/error/empty state và nhãn cutoff cho dự báo. Không cần bộ chọn hotel trong phiên bản này.

Triển khai tập trung ở các module Operations hiện có trong `pipeline/`, `database/`, `backend/`, `frontend/` và `ml/demand_forecast/`. `scripts/` điều phối pipeline/training; `artifacts/` lưu model, metric, forecast và log. Notebook phục vụ profiling/experiment; luồng chạy chính phải tái lập độc lập.

**Gate tích hợp:** Docker Compose dựng được frontend/backend/database; ETL chạy riêng; cấu hình môi trường được mô tả; có thể chạy từ raw/sample đến Mart, xem OLAP, xuất report và gọi forecast mà không chỉnh dữ liệu bằng tay.

## 10. Tiến độ và tiêu chí hoàn thành

Giữ deadline của kế hoạch gốc, thu gọn đầu việc về Operations:

| Thời gian năm 2026 | Công việc / artifact bắt buộc | Gate |
|---|---|---|
| 06/10–07/10 | Chốt Operations Mart cho City Hotel, target, grain, bộ KPI và danh sách nguồn | Business baseline |
| 08/10–13/10 | Thu Booking/Calendar/Holiday, profiling, data dictionary, mapping nguồn và địa điểm | Data sources ready |
| 14/10–19/10 | Staging, ingestion metadata, quy tắc cleaning, đối soát batch | Staging ready |
| 20/10–25/10 | Dimension/fact ETL, PK/FK, kiểm tra grain và KPI | DW ready |
| 26/10–29/10 | Operations Mart, OLAP operators, backend/frontend skeleton và dashboard đầu tiên | Mart + OLAP ready |
| 30/10–02/11 | Weekly report, feature dataset, seasonal naive và mô hình đầu tiên | Reporting + model baseline |
| 03/11–05/11 | Backtest, forecast 7 ngày, DSS rules và hoàn thiện ba màn hình | Demo feature complete |
| 06/11–07/11 | End-to-end, Docker, đối soát KPI, thử dựng trên máy thành viên khác | Integration freeze |
| 08/11–10/11 | Chốt báo cáo, chạy thử demo, lưu backup và nộp phiên bản ổn định | Final submission |

**Checklist nghiệm thu cuối:**

- Truy vết được City Hotel tại một ngày qua Raw → Staging → DW → Operations Mart → OLAP/Report/Forecast; xác nhận các đầu ra chỉ chứa City Hotel.
- Grain, quy tắc booking hủy, số khách và coverage nhất quán; pipeline chạy lại không tăng số liệu.
- Chứng minh slice, dice, roll-up, drill-down và pivot; tỷ lệ/trung bình tổng hợp đúng.
- Reporting khớp Analytics/DW; forecast có cutoff, đủ 7 ngày, metrics và so sánh baseline.
- Có demo ổn định, tài liệu chạy dự án và ghi rõ giới hạn dữ liệu/giả định.

## 11. Mở rộng và quản lý phiên bản

Khi thêm domain, cập nhật yêu cầu nghiệp vụ, grain, bảng/ETL, API/UI và tiêu chí nghiệm thu của domain đó; tái sử dụng DW cùng các dimension phù hợp. Mọi thay đổi ảnh hưởng target hoặc công thức KPI phải tăng version và cập nhật các đầu ra liên quan.

**Version:** 1.0.1  
**Ngày chốt:** 06/10/2026 (Asia/Ho_Chi_Minh)  
**Phạm vi chốt:** Operations Mart cho City Hotel — OLAP Operators, Reporting KPI, Mining dự đoán lượng khách 7 ngày tới và rule DSS cơ bản.

| Version | Ngày chốt | Nội dung |
|---|---|---|
| 1.0.0 | 06/10/2026 | Thu gọn từ master plan về một Operations Mart; giữ kiến trúc tổng quát; xác định grain, KPI, ETL, OLAP, reporting, forecast và các gate triển khai |
| 1.0.1 | 06/10/2026 | Giới hạn phạm vi City Hotel; cập nhật lọc ETL, KPI, ví dụ OLAP, forecast và API/UI; giữ hotel key để hỗ trợ mở rộng |

