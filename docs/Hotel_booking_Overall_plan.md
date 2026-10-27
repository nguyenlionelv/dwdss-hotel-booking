# DWDSS Hotel Booking — Master Plan (High-Level → Low-Level → Code-Level)

> **Phạm vi triển khai hiện hành:** Tài liệu này là nguồn ý tưởng kiến trúc rộng, không phải contract nạp dữ liệu. Dự án hiện chỉ có một Operations Mart cho City Hotel và ba nguồn Booking (chỉ City Hotel vào Staging), Holiday PT/Lisboa, Weather lịch sử Lisbon; Event ngoài phạm vi. Không áp dụng các ví dụ bên dưới về điền `children=0`, `country="Unknown"`, holiday thiếu=`False`, lọc City ở Staging→DW, hoặc bốn mart/ba bài toán ML. Quy tắc thực thi hiện hành: [detailed plan](detailed_plan.md), [data contract](data_dictionary/operations_sources.md), [Source → Staging](etl_spec/operations_source_to_target.md), [kế hoạch Member 2](member2_execution_plan.md).

> **Deadline:** 10/11/2026  
> **Mục tiêu:** Xây dựng một hệ thống Data Warehouse & Decision Support System cho domain Hotel Booking theo luồng:
>
> **Business Requirements → Data Sources → Staging → ETL → Data Warehouse → Data Mart → Analytics / Reporting / Mining → DSS**

---

# 0. Cách đọc tài liệu

Mỗi phần được mô tả ở **3 mức**:

1. **High-level** — tại sao phần này tồn tại, mục tiêu business/architecture là gì.
2. **Low-level** — cần làm cụ thể những việc gì, lấy field nào, thiết kế bảng nào, transform gì.
3. **Code-level** — repo/module/file nào cần tạo, input/output là gì, code/query chạy ra artifact nào, phần sau dùng artifact đó ra sao.

Mỗi phase đều trả lời 5 câu hỏi:

- **Input là gì?**
- **Xử lý gì?**
- **Output là gì?**
- **Output đó đóng góp gì cho phase tiếp theo?**
- **Làm sao biết phase này làm tốt?**

---

# 1. North Star — hệ thống cuối cùng phải làm được gì?

## High-level

Hệ thống cần:

- tích hợp dữ liệu Hotel Booking với dữ liệu external;
- làm sạch và tổ chức thành Data Warehouse;
- tạo Data Mart phù hợp với workload;
- phục vụ:
  - **Analytics / OLAP**
  - **Reporting**
  - **Mining / Prediction**
  - **Decision Support System**

## Luồng tổng thể

```text
Booking + Weather + Holiday + Event
                 │
                 ▼
         Data Source Layer
                 │
          ETL / Ingestion #1
                 ▼
            Data Staging
                 │
           ETL / Transform #2
                 ▼
          Data Warehouse
                 │
            ETL / Mart #3
                 ▼
             Data Mart
                 │
      ┌──────────┼──────────┐
      ▼          ▼          ▼
 Analytics    Reporting    Mining
    OLAP         KPI         ML
                               │
                               ▼
                              DSS
```

---

# 2. Business Requirements — tổ chức theo Business Mart Domain × Output Type

## 2.1 Nguyên tắc thiết kế Business Requirements

Business Requirements không được chia đơn thuần theo công nghệ như `Analytics Mart`, `Reporting Mart`, `Mining Mart`.

Thiết kế mục tiêu là **hai chiều**:

```text
Chiều 1: Business domain / subject area
    ↓
Operations
Guest / Customer
Revenue & Cancellation
Booking / Commercial Performance

Chiều 2: Cách khai thác dữ liệu
    ↓
Analytics / OLAP
Reporting
Mining / DSS
```

Do đó:

> **Data Mart được hình thành vì một business domain hợp lý. Analytics, Reporting và Mining/DSS chỉ là các workload/output sử dụng Mart đó.**

Không bắt buộc mỗi Mart phải có đủ cả ba phần. Nếu một Mart chỉ có Analytics + Reporting nhưng không có Mining hợp lý thì **không tạo prediction chỉ để đủ cấu trúc**.

### Ma trận business domain × output

| Mart domain | Analytics / OLAP | Reporting | Mining / DSS |
|---|---:|---:|---:|
| **Operations Mart** | ✅ | ✅ | ✅ Demand Forecast |
| **Guest / Customer Mart** | ✅ | ✅ | ✅ Guest Composition Forecast |
| **Revenue & Cancellation Mart** | ✅ | ✅ | ✅ Cancellation Risk Prediction |
| **Booking / Commercial Performance Mart** | ✅ | ✅ | Không bắt buộc |

---

# 2.2 Domain 1 — Operations Mart

## Business concern

> **Khách sạn sắp có bao nhiêu khách, demand biến động thế nào và cần chuẩn bị nguồn lực vận hành ra sao?**

Mart này tập trung vào demand theo thời gian, seasonal/calendar effects và workload vận hành.

## Grain dự kiến

Baseline:

```text
1 row = 1 hotel × 1 day
```

Có thể tạo thêm aggregate tuần/tháng bằng view hoặc materialized view, không cần đổi grain gốc của Mart.

## Dimension / context fields dự kiến

```text
date_key
full_date
year
quarter
month
week_of_year
day_of_week
hotel_key
hotel_name
is_weekend
is_holiday
holiday_name
event_flag            # optional
event_type            # optional
temperature_mean
precipitation
humidity
wind_speed
weather_code
```

## Measures / aggregate fields dự kiến

```text
total_bookings
total_guests
total_adults
total_children
total_babies
total_stay_nights
avg_party_size
avg_stay_nights
avg_lead_time
avg_adr
total_cancellations
cancellation_rate
```

### Công thức aggregate gợi ý

```text
total_bookings      = COUNT(booking)
total_guests        = SUM(adults + children + babies)
total_stay_nights   = SUM(weekend_nights + weekday_nights)
avg_party_size      = AVG(total_guests_per_booking)
avg_stay_nights     = AVG(total_stay_nights_per_booking)
avg_lead_time       = AVG(lead_time)
avg_adr             = AVG(adr)
cancellation_rate   = SUM(is_canceled) / COUNT(booking)
```

## Analytics / OLAP Requirements

### DO-A01 — Demand Trend Analysis

Phân tích:

- guest count theo ngày/tuần/tháng;
- booking count theo ngày/tuần/tháng;
- City Hotel vs Resort Hotel;
- peak / low-demand periods;
- seasonality.

Output:

```text
Trend chart
Heatmap / calendar view
Year → Quarter → Month → Day drill-down
```

### DO-A02 — Weekend / Seasonality Analysis

So sánh:

```text
Weekday vs Weekend
Month vs Month
Quarter vs Quarter
```

Measures:

- total guests;
- total bookings;
- stay nights;
- ADR.

### DO-A03 — Holiday Impact Analysis

So sánh:

```text
Holiday vs Non-Holiday
```

trên:

- demand;
- average stay;
- ADR;
- cancellation rate.

### DO-A04 — Weather Impact Analysis

Phân tích quan hệ giữa:

```text
Temperature
Rainfall
Humidity
Weather condition
        ↓
Demand / Guest Count
```

> Chỉ dùng nếu có thể mapping weather/location hợp lý với hotel source.

## Reporting Requirements

### DO-R01 — Weekly Demand Report

Các KPI:

```text
Total bookings
Total guests
Average guests/day
Peak demand day
Average stay nights
Weekend demand
Holiday demand
```

### DO-R02 — Operations Capacity Summary

Output phục vụ chuẩn bị nguồn lực:

```text
Expected / historical guest volume
Peak check-in day
Stay-night workload
Average party size
```

## Mining / DSS Requirements

### DO-M01 — Forecast lượng khách 7 ngày tới

Business goal:

> Dự đoán lượng khách trong 7 ngày tiếp theo để chuẩn bị nhân lực, housekeeping, F&B và capacity phù hợp.

Input feature candidates:

```text
historical_guest_count
historical_booking_count
lag_1
lag_7
rolling_mean_7
rolling_mean_14
day_of_week
month
is_weekend
is_holiday
weather variables
event flag (optional)
hotel_key
```

Output:

```text
date
hotel
predicted_guest_count
demand_level = LOW / NORMAL / HIGH
```

DSS contribution:

```text
HIGH demand
→ review room availability
→ prepare staffing capacity
→ prepare housekeeping / F&B workload
```

---

# 2.3 Domain 2 — Guest / Customer Mart

## Business concern

> **Khách sắp tới thuộc nhóm nào và khách sạn nên chuẩn bị cơ cấu phòng như thế nào?**

Domain này tập trung vào party composition, customer profile và room planning.

## Grain dự kiến

Có thể duy trì hai lớp:

```text
Base Mart grain:
1 row = 1 booking / guest party

Aggregate view:
1 row = 1 hotel × 1 day × 1 party_type
```

Base grain cần thiết để phân tích room preference và train model; aggregate layer giúp reporting/forecasting thuận tiện.

## Fields dự kiến ở booking-level

```text
booking_key
date_key
hotel_key
country_key
channel_key
market_segment_key
customer_type
is_repeated_guest
adults
children
babies
total_guests
party_type
reserved_room_type
assigned_room_type
room_changed_flag
total_stay_nights
lead_time
adr
is_canceled
```

## Rule phân loại party_type dự kiến

Baseline:

```text
SINGLE:
    adults = 1 AND children = 0 AND babies = 0

COUPLE:
    adults = 2 AND children = 0 AND babies = 0

FAMILY:
    children > 0 OR babies > 0

OTHER_GROUP:
    các trường hợp còn lại
```

> Rule phải được kiểm tra với distribution thực tế trước khi freeze.

## Aggregate fields dự kiến

```text
total_bookings
total_guests
single_bookings
couple_bookings
family_bookings
other_group_bookings
single_ratio
couple_ratio
family_ratio
other_group_ratio
avg_party_size
avg_stay_nights
avg_adr
repeated_guest_count
repeated_guest_rate
room_change_count
room_change_rate
```

Theo room type có thể aggregate thêm:

```text
reserved_room_type_count
assigned_room_type_count
family_bookings_by_room_type
couple_bookings_by_room_type
single_bookings_by_room_type
```

## Analytics / OLAP Requirements

### GC-A01 — Guest Composition Analysis

Phân tích tỷ trọng:

```text
Single
Couple
Family
Other Group
```

theo:

- time;
- hotel;
- market segment;
- channel;
- country;
- customer type.

### GC-A02 — Party Size Analysis

Measures:

```text
avg_party_size
total_adults
total_children
total_babies
```

Phân tích theo thời gian/hotel/segment.

### GC-A03 — Room Preference Analysis

Phân tích:

```text
reserved_room_type
assigned_room_type
reserved vs assigned mismatch
party_type × room_type
```

Business question ví dụ:

> Family thường reserve loại phòng nào và tỷ lệ bị đổi phòng là bao nhiêu?

### GC-A04 — Customer Profile Analysis

Phân tích:

- first-time vs repeated guest;
- customer type;
- origin country nếu phù hợp;
- channel / market segment.

## Reporting Requirements

### GC-R01 — Guest Mix Report

Ví dụ:

```text
Single        27%
Couple        45%
Family        23%
Other          5%
```

Có thể kèm:

```text
Avg party size
Avg stay nights
Repeated guest rate
```

### GC-R02 — Room Demand Mix Report

Các field:

```text
room_type
reserved_count
assigned_count
family_share
couple_share
single_share
room_change_rate
```

## Mining / DSS Requirements

### GC-M01 — Dự đoán cơ cấu khách 1 tuần tới

Business goal:

> Dự đoán số lượng và tỷ lệ khách đơn / đôi / gia đình trong 7 ngày tới để điều chỉnh cơ cấu phòng và chuẩn bị tiện ích phù hợp.

Có hai output cần giữ cùng nhau:

```text
1. predicted total guests/bookings
2. predicted composition ratios
```

Output cuối:

```text
date
hotel
predicted_single_count
predicted_couple_count
predicted_family_count
predicted_other_count
single_ratio
couple_ratio
family_ratio
```

DSS contribution:

```text
Family ratio ↑
→ review family-compatible room availability
→ prepare extra-bed / child-related facilities nếu phù hợp

Couple ratio ↑
→ review double-room inventory
```

> Không được suy diễn room capacity nếu dataset không chứa capacity thực tế; DSS chỉ đưa planning signal.

---

# 2.4 Domain 3 — Revenue & Cancellation Mart

## Business concern

> **Bao nhiêu booking có nguy cơ bị hủy và việc đó ảnh hưởng như thế nào đến booking value / revenue assurance?**

Domain này tập trung vào cancellation behavior, risk và revenue-at-risk estimate.

## Grain dự kiến

Base Mart:

```text
1 row = 1 booking
```

Aggregate reporting layer:

```text
1 row = 1 hotel × 1 day/week/month
```

Booking-level grain là cần thiết cho cancellation classification.

## Fields dự kiến ở booking-level

```text
booking_key
date_key
hotel_key
channel_key
market_segment_key
customer_type
country_key
lead_time
lead_time_bucket
deposit_type
is_repeated_guest
previous_cancellations
previous_bookings_not_canceled
booking_changes
days_in_waiting_list
adr
total_stay_nights
total_guests
special_requests
agent/company indicator
reservation_status
reservation_status_date
is_canceled
estimated_booking_value
```

## Derived field dự kiến

```text
estimated_booking_value = adr × total_stay_nights
```

> Đây là **estimated booking value**, không mặc định gọi là accounting revenue. Nếu dùng làm revenue proxy phải ghi assumption rõ trong báo cáo.

Lead-time buckets ví dụ:

```text
0–7
8–30
31–90
90+
```

## Aggregate fields dự kiến

```text
total_bookings
canceled_bookings
non_canceled_bookings
cancellation_rate
avg_lead_time
avg_adr
gross_estimated_booking_value
canceled_estimated_booking_value
retained_estimated_booking_value
avg_booking_value
```

Historical calculation:

```text
gross_estimated_booking_value
    = SUM(estimated_booking_value)

canceled_estimated_booking_value
    = SUM(estimated_booking_value WHERE is_canceled = 1)

retained_estimated_booking_value
    = SUM(estimated_booking_value WHERE is_canceled = 0)
```

Prediction-derived aggregates:

```text
expected_cancellation_count
predicted_cancellation_rate
estimated_revenue_at_risk
expected_retained_booking_value
```

## Analytics / OLAP Requirements

### RC-A01 — Cancellation Trend Analysis

Phân tích cancellation rate theo:

- day/week/month;
- hotel;
- season.

### RC-A02 — Channel / Segment Cancellation Risk

So sánh:

```text
Direct
Online TA
Offline TA
Corporate
...
```

và market segments.

### RC-A03 — Lead Time Risk Analysis

Phân tích:

```text
lead_time_bucket
        ↓
cancellation_rate
```

### RC-A04 — Deposit / Customer Risk Analysis

So sánh cancellation theo:

```text
deposit_type
customer_type
repeated_guest
previous_cancellations
```

### RC-A05 — Estimated Booking Value at Risk

Phân tích:

```text
estimated_booking_value
canceled_booking_value
retained_booking_value
```

Theo:

- time;
- hotel;
- channel;
- segment.

## Reporting Requirements

### RC-R01 — Cancellation Risk Report

KPI:

```text
Total bookings
Canceled bookings
Cancellation rate
High-risk channel
High-risk lead-time group
```

### RC-R02 — Revenue Assurance Report

KPI:

```text
Gross estimated booking value
Canceled estimated booking value
Retained estimated booking value
Cancellation-adjusted outlook
```

## Mining / DSS Requirements

### RC-M01 — Predict booking cancellation risk

Preferred approach:

```text
Booking-level classification
      ↓
P(cancel | booking features)
      ↓
Aggregate probabilities by future period
```

Possible features:

```text
hotel
lead_time
channel
market_segment
deposit_type
customer_type
is_repeated_guest
previous_cancellations
previous_bookings_not_canceled
booking_changes
days_in_waiting_list
adr
total_stay_nights
total_guests
special_requests
calendar features
```

Output per booking:

```text
booking_key
cancel_probability
risk_level
estimated_booking_value
```

Aggregate output:

```text
expected_cancellation_count
predicted_cancellation_rate
estimated_revenue_at_risk
expected_retained_booking_value
```

Ví dụ:

```text
Expected bookings next week:           1,000
Expected cancellations:                  230
Predicted cancellation rate:             23%
Estimated booking value:             120,000
Estimated value at risk:              24,500
Expected retained booking value:      95,500
```

DSS contribution:

```text
High cancellation risk
→ revenue assurance warning
→ review overbooking / inventory policy carefully
→ monitor risky channels / segments
```

> Hệ thống chỉ đưa decision-support signal; không tự động đề xuất overbooking quantity nếu chưa có optimization/capacity model.

---

# 2.5 Domain 4 — Booking / Commercial Performance Mart

## Business concern

> **Các kênh booking, market segment và nhóm khách đang đóng góp thế nào vào hoạt động kinh doanh?**

Đây là Mart thiên về commercial / sales performance. Không bắt buộc phải có Mining nếu nhóm chưa có business prediction hợp lý.

## Grain dự kiến

Baseline aggregate:

```text
1 row = 1 date × hotel × channel × market_segment
```

Có thể bổ sung country/customer type trong view phân tích nếu cardinality không quá lớn.

## Dimension / context fields dự kiến

```text
date_key
year
quarter
month
hotel_key
channel_key
market_segment_key
country_key          # optional in base aggregate
customer_type        # optional
is_repeated_guest
```

## Measures / aggregate fields dự kiến

```text
total_bookings
total_guests
total_stay_nights
total_cancellations
cancellation_rate
avg_adr
avg_lead_time
avg_party_size
repeated_guest_count
repeated_guest_rate
avg_special_requests
```

Nếu nhóm chấp nhận estimated booking value:

```text
gross_estimated_booking_value
retained_estimated_booking_value
```

## Analytics / OLAP Requirements

### BP-A01 — Booking Trend Analysis

Phân tích booking theo:

- time;
- hotel;
- channel;
- segment;
- country.

### BP-A02 — Channel Performance

So sánh từng channel theo:

```text
booking count
cancellation rate
ADR
stay nights
guest count
```

### BP-A03 — Market Segment Performance

So sánh:

```text
booking volume
ADR
average stay
cancellation rate
```

### BP-A04 — Customer / Repeat Behavior

Phân tích:

```text
First-time vs Repeated Guest
```

trên:

- booking volume;
- ADR;
- stay nights;
- cancellation.

### BP-A05 — Geographic Booking Analysis

Nếu country data đủ tốt:

- booking by country;
- ADR by country;
- cancellation by country;
- market/channel mix by country.

## Reporting Requirements

### BP-R01 — Booking Performance Report

KPI:

```text
Total bookings
Total guests
Top channel
Top market segment
Average ADR
Average lead time
Average stay
Cancellation rate
Repeated guest rate
```

### BP-R02 — Channel / Segment Performance Report

Ranking:

```text
Channel / Segment
Bookings
Guests
ADR
Cancellation Rate
Stay Nights
```

## Mining / DSS

Không bắt buộc ở baseline.

Nếu tương lai có business case rõ, có thể bổ sung:

```text
channel demand forecasting
customer segmentation
commercial response prediction
```

nhưng **không đưa vào chỉ để Mart có đủ Mining**.

---

# 2.6 Cross-Mart Business Questions

Một business question có thể sử dụng nhiều Mart hoặc conformed dimensions chung.

Ví dụ:

> Holiday ảnh hưởng cancellation như thế nào?

Có thể kết hợp:

```text
DimDate / Holiday
      +
Revenue & Cancellation Mart
```

Ví dụ khác:

> Tuần tới demand tăng và family ratio cũng tăng thì cần chuẩn bị gì?

DSS có thể kết hợp output:

```text
Operations Mart
    → total demand forecast

Guest / Customer Mart
    → family/couple/single forecast

Combined DSS
    → resource + room planning signal
```

Do đó Mart không phải các hộp kín; chúng nên dùng chung **conformed dimensions** từ Data Warehouse như:

```text
DimDate
DimHotel
DimChannel
DimMarketSegment
DimCountry
```

---

# 2.7 Requirement ID Convention

Để trace từ business requirement tới data/query/model, dùng format:

```text
<DOMAIN>-<OUTPUT>-<NUMBER>
```

Ví dụ:

```text
DO-A01 = Demand/Operations Analytics #01
DO-R01 = Demand/Operations Reporting #01
DO-M01 = Demand/Operations Mining #01

GC-A01 = Guest/Customer Analytics #01
GC-M01 = Guest/Customer Mining #01

RC-A01 = Revenue/Cancellation Analytics #01
RC-M01 = Revenue/Cancellation Mining #01

BP-A01 = Booking Performance Analytics #01
BP-R01 = Booking Performance Reporting #01
```

Requirement ID sẽ được dùng tiếp trong:

```text
Source-to-Target Mapping
SQL query naming
Dashboard page
Report specification
ML experiment
Evaluation table
```

---

# 3. Technology & Application Architecture Decisions

## 3.1 Frontend

**Baseline:** `React + Vite`

Libraries đề xuất:

```text
React
├── Vite
├── React Router
├── Recharts
└── Axios hoặc Fetch API
```

Frontend chịu trách nhiệm hiển thị Analytics/OLAP, Reporting, Mining/DSS, filter, drill-down, chart/table/KPI và gọi REST API. Frontend **không query PostgreSQL trực tiếp**.

```text
React
  ↓ HTTP / REST
FastAPI
  ↓ SQL
PostgreSQL
```

## 3.2 Backend API

**Baseline:** `FastAPI`

Lý do:

- đồng nhất Python với ETL và ML;
- dễ tạo REST API;
- dễ load model `.joblib/.pkl`;
- dễ kết nối PostgreSQL;
- phù hợp Docker.

API groups dự kiến:

```text
/api/analytics/...
/api/reports/...
/api/dss/...
/api/metadata/...
```

Map theo Mart domain:

```text
/api/analytics/operations/...
/api/analytics/guests/...
/api/analytics/cancellations/...
/api/analytics/bookings/...

/api/reports/operations/...
/api/reports/guests/...
/api/reports/revenue/...
/api/reports/bookings/...

/api/dss/demand-forecast
/api/dss/guest-mix-forecast
/api/dss/cancellation-risk
```

## 3.3 Database / DW

**Baseline:** `PostgreSQL 17`

Logical schemas:

```text
staging
dw
mart
```

```text
PostgreSQL
├── staging
│   ├── stg_booking
│   ├── stg_weather
│   └── ...
├── dw
│   ├── fact_booking
│   ├── dim_date
│   └── ...
└── mart
    ├── operations_*
    ├── guest_*
    ├── revenue_*
    └── booking_*
```

## 3.4 ETL / Data Engineering

**Baseline:** Python + pandas + SQLAlchemy/psycopg + requests + logging.

ETL chạy tách khỏi FastAPI request cycle:

```text
Offline / scheduled ETL
        ↓
PostgreSQL DW / Mart
        ↑
FastAPI query
        ↑
React
```

Không chạy full ETL khi user mở dashboard.

## 3.5 Machine Learning

**Baseline:** Python + pandas + scikit-learn + XGBoost/LightGBM (optional) + joblib.

Training offline:

```text
Mart → Feature Engineering → Train/Evaluate → model.joblib
```

Inference online:

```text
React → FastAPI → load model → read Mart/features → prediction → JSON
```

Backend **không train model khi khởi động**.

## 3.6 Containerization

**Baseline:** `Docker + Docker Compose`

```text
Docker Compose
├── frontend   → React build / web server
├── backend    → FastAPI
├── db         → PostgreSQL
└── etl        → Python ETL job
```

Optional: `pgAdmin`.

Development:

```bash
docker compose up --build
```

Run ETL:

```bash
docker compose run --rm etl
```

## 3.7 System Architecture

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

## 3.8 Scope technology

Không thêm Kafka, Redis, Airflow, Kubernetes hay microservices nếu chưa có business/technical need rõ. Ưu tiên hoàn thiện `ETL → DW → Mart → Analytics/Reporting/Mining-DSS`.

---


# 4. Phase A — Data Source Discovery & Acquisition

## 4.1 High-level

Mục tiêu:

> Thu thập nhiều nguồn dữ liệu cần thiết cho các business requirements.

Không xem một Kaggle CSV là toàn bộ hệ thống.

## 4.2 Các nguồn cần có

### Source 1 — Hotel Booking

Các field nên giữ:

```text
hotel
is_canceled
lead_time
arrival_date_year
arrival_date_month
arrival_date_week_number
arrival_date_day_of_month
stays_in_weekend_nights
stays_in_week_nights
adults
children
babies
meal
country
market_segment
distribution_channel
is_repeated_guest
previous_cancellations
previous_bookings_not_canceled
reserved_room_type
assigned_room_type
booking_changes
deposit_type
agent
company
days_in_waiting_list
customer_type
adr
required_car_parking_spaces
total_of_special_requests
reservation_status
reservation_status_date
```

Raw format:

```text
CSV
```

Ví dụ:

```text
data/raw/booking/hotel_bookings.csv
```

### Source 2 — Weather

Field tối thiểu:

```text
date
location
temperature_mean
temperature_min
temperature_max
precipitation
humidity
wind_speed
weather_code
```

Nếu API trả hourly:

```text
timestamp
temperature
rainfall
humidity
wind_speed
```

thì raw giữ hourly.

Raw format:

- API → JSON
- Dataset bảng → CSV

### Source 3 — Holiday / Calendar

Field:

```text
date
holiday_name
country
region
holiday_type
```

Derived sau ETL:

```text
is_holiday
is_weekend
day_of_week
month
quarter
season
```

### Source 4 — Event (Optional)

Chỉ dùng nếu tìm được nguồn đáng tin cậy.

Field:

```text
event_name
event_type
start_date
end_date
location
city
importance
estimated_attendance
```

## 4.3 Code-level

Folder:

```text
data/
└── raw/
    ├── booking/
    ├── weather/
    ├── holiday/
    └── event/
```

Ingestion modules:

```text
src/ingestion/
├── booking/
│   └── ingest_booking.py
├── weather/
│   └── fetch_weather.py
├── holiday/
│   └── ingest_holiday.py
└── event/
    └── ingest_event.py
```

Interface nên thống nhất:

```python
def ingest() -> str:
    # Fetch/copy raw source.
    # Return path to raw file.
    ...
```

## 4.4 Output của phase này

```text
data/raw/booking/*.csv
data/raw/weather/*.json|csv
data/raw/holiday/*.csv
data/raw/event/*.csv
docs/data_dictionary/*.md
```

## 4.5 Đóng góp cho phase sau

Output raw là **source of truth** cho:

```text
Raw Data
   ↓
Source-to-Staging ETL
```

Staging không được lấy dữ liệu từ file đã sửa tay.

## 4.6 Validation

Ví dụ:

```python
assert file_exists
assert row_count > 0
assert required_columns_exist
```

Lưu metadata:

```text
source_name
file_name
ingestion_time
row_count
```

## 4.7 Definition of Done

Phase này làm tốt khi:

- source có provenance rõ;
- field selection gắn business requirement;
- raw data không bị overwrite;
- có data dictionary;
- có thể chạy ingestion lại.

---

# 5. Phase B — Data Profiling & Staging

## 5.1 High-level

Staging là vùng:

> giữ dữ liệu gần source để ETL sau có thể clean/integrate có kiểm soát.

## 5.2 Schema đề xuất

PostgreSQL:

```sql
CREATE SCHEMA staging;
CREATE SCHEMA dw;
CREATE SCHEMA mart;
```

Tables:

```text
staging.stg_booking
staging.stg_weather
staging.stg_holiday
staging.stg_event
```

## 5.3 Metadata columns

Mỗi staging table có thể thêm:

```text
_source_system
_source_file
_ingested_at
_batch_id
```

## 5.4 Code-level

Folder:

```text
sql/staging/
├── 001_create_stg_booking.sql
├── 002_create_stg_weather.sql
├── 003_create_stg_holiday.sql
└── 004_create_stg_event.sql
```

ETL:

```text
src/etl/source_to_staging/
├── booking.py
├── weather.py
├── holiday.py
└── event.py
```

Ví dụ loader:

```python
def load_booking_to_staging(df, engine, batch_id):
    df["_batch_id"] = batch_id
    df["_source_system"] = "kaggle_hotel_booking"

    df.to_sql(
        "stg_booking",
        engine,
        schema="staging",
        if_exists="append",
        index=False
    )
```

## 5.5 Profiling

Notebook:

```text
notebooks/profiling/
├── booking_profile.ipynb
├── weather_profile.ipynb
└── source_integration_profile.ipynb
```

Các metric:

```text
row_count
null_count
null_percentage
distinct_count
duplicate_count
min
max
mean
invalid_date_count
```

## 5.6 Output

Sau phase:

```text
staging.stg_booking
staging.stg_weather
staging.stg_holiday
staging.stg_event
```

và:

```text
profiling report
data quality issues
```

## 5.7 Đóng góp cho phase sau

```text
Staging
   ↓
Transform / Integrate
   ↓
Data Warehouse
```

Profiling quyết định:

- field nào cần clean;
- missing xử lý ra sao;
- key nào dùng integration;
- field nào không đáng tin cậy.

## 5.8 Definition of Done

- raw → staging row count reconcile được;
- staging giữ traceability;
- có profiling;
- không clean nặng ở source-to-staging;
- biết rõ các data quality issues.

---

# 6. Phase C — ETL Staging → Data Warehouse

## 6.1 High-level

Đây là ETL quan trọng nhất.

Mục tiêu:

```text
Raw-like Staging
      ↓
Clean
Standardize
Deduplicate
Integrate
Apply Business Rules
Generate Keys
      ↓
Data Warehouse
```

## 6.2 Pipeline logical stages

```text
staging
   ↓
validate
   ↓
clean
   ↓
standardize
   ↓
integrate
   ↓
dimension processing
   ↓
fact processing
   ↓
load DW
```

## 6.3 Code-level structure

```text
src/etl/staging_to_dw/
├── dimensions/
│   ├── dim_date.py
│   ├── dim_hotel.py
│   ├── dim_channel.py
│   ├── dim_market_segment.py
│   └── dim_customer.py
│
├── facts/
│   └── fact_booking.py
│
├── transformations/
│   ├── dates.py
│   ├── categorical.py
│   ├── missing.py
│   ├── outliers.py
│   └── integration.py
│
└── run.py
```

## 6.4 Transform examples

### Date

Input:

```text
arrival_date_year = 2017
arrival_date_month = July
arrival_date_day_of_month = 12
```

Output:

```text
arrival_date = 2017-07-12
date_key = 20170712
```

Code:

```python
df["arrival_date"] = pd.to_datetime(
    df["arrival_date_year"].astype(str)
    + "-"
    + df["arrival_date_month"]
    + "-"
    + df["arrival_date_day_of_month"].astype(str)
)
```

### Stay nights

```python
df["total_stay_nights"] = (
    df["stays_in_weekend_nights"]
    + df["stays_in_week_nights"]
)
```

### Guests

```python
df["total_guests"] = (
    df["adults"]
    + df["children"].fillna(0)
    + df["babies"]
)
```

### Booking count

Fact measure:

```text
booking_count = 1
```

### Cancellation

```text
is_canceled = 0 / 1
```

Sau aggregate:

```sql
AVG(is_canceled::numeric)
```

→ cancellation rate.

## 6.5 Weather integration

Nếu weather daily:

```text
booking.arrival_date
        +
hotel/location mapping
        ↓
weather.date
```

Pseudo:

```python
booking = booking.merge(
    weather,
    left_on=["arrival_date", "location"],
    right_on=["date", "location"],
    how="left"
)
```

> Nếu source booking không có location đủ chi tiết thì cần ghi assumption rõ; không được giả vờ mapping chính xác.

## 6.6 Holiday integration

```python
booking = booking.merge(
    holidays[["date", "is_holiday"]],
    left_on="arrival_date",
    right_on="date",
    how="left"
)

booking["is_holiday"] = booking["is_holiday"].fillna(False)
```

## 6.7 Missing value rules

Không dùng:

```python
df.dropna()
```

cho toàn bộ dataset.

Thay vào đó:

```text
country missing → "Unknown"
children missing → 0 nếu hợp lý
agent/company missing → có thể "No Agent / No Company"
weather missing → xử lý riêng / flag
```

Document:

```text
docs/etl_spec/missing_value_rules.md
```

## 6.8 Output sau ETL

Ví dụ:

```text
dw.dim_date
dw.dim_hotel
dw.dim_channel
dw.dim_market_segment
dw.dim_customer
dw.fact_booking
```

## 6.9 Đóng góp cho phần sau

Data Warehouse là nguồn chuẩn cho:

```text
DW
├── Data Mart
├── OLAP
├── Reporting
└── DSS Feature Engineering
```

Từ thời điểm này:

> downstream không nên quay lại raw CSV để lấy số liệu chính thức.

## 6.10 Validation

### Referential integrity

```sql
SELECT COUNT(*)
FROM dw.fact_booking f
LEFT JOIN dw.dim_date d
  ON f.date_key = d.date_key
WHERE d.date_key IS NULL;
```

Expected:

```text
0
```

### Row reconciliation

```text
valid staging rows
≈
fact rows
+ rejected rows
```

### Duplicate fact

Tùy business key:

```sql
SELECT booking_business_key, COUNT(*)
FROM dw.fact_booking
GROUP BY booking_business_key
HAVING COUNT(*) > 1;
```

## 6.11 Definition of Done

- fact grain rõ;
- không double-count;
- join dimension đúng;
- business rules documented;
- pipeline modular;
- rerun không tạo duplicate ngoài ý muốn;
- output đủ cho Mart.

---

# 7. Phase D — Data Warehouse Design

## 7.1 High-level

DW phải:

- tích hợp dữ liệu;
- lưu lịch sử;
- phục vụ analytical query;
- dễ mở rộng.

## 7.2 Grain

Ví dụ:

> **Một row của FactBooking đại diện cho một booking/reservation record.**

Grain phải được ghi trước khi viết DDL.

## 7.3 Baseline Star Schema

```text
                DimDate
                   │
                   │
DimHotel ─── FactBooking ─── DimChannel
                   │
                   │
           DimMarketSegment
                   │
              DimCustomer
```

Optional context:

```text
DimWeather
DimCountry
DimRoom
```

## 7.4 FactBooking

Possible columns:

```text
booking_key
date_key
hotel_key
channel_key
segment_key
customer_key

booking_count
is_canceled
lead_time
total_stay_nights
total_guests
adr
special_requests
```

## 7.5 Code-level SQL

```sql
CREATE TABLE dw.fact_booking (
    booking_key BIGSERIAL PRIMARY KEY,

    date_key INT NOT NULL,
    hotel_key INT NOT NULL,
    channel_key INT,
    segment_key INT,
    customer_key INT,

    booking_count SMALLINT DEFAULT 1,
    is_canceled SMALLINT,
    lead_time INT,
    total_stay_nights INT,
    total_guests INT,
    adr NUMERIC(10,2),

    FOREIGN KEY (date_key)
        REFERENCES dw.dim_date(date_key)
);
```

## 7.6 Indexing

```sql
CREATE INDEX idx_fact_booking_date
ON dw.fact_booking(date_key);

CREATE INDEX idx_fact_booking_hotel
ON dw.fact_booking(hotel_key);
```

## 7.7 Scalability / Extensibility

Ví dụ sau này có Review:

```text
FactBooking
FactReview
     │
     ├── DimDate
     └── DimHotel
```

Không cần phá FactBooking.

## 7.8 Output

```text
sql/warehouse/*.sql
DW schema
DW diagram
fact/dimension data
```

## 7.9 Downstream contribution

```text
Data Warehouse
      ↓
Data Mart
      ↓
Analytics / Reporting / Mining
```

DW cung cấp:

- conformed dimensions;
- standardized KPI inputs;
- trusted historical data.

## 7.10 Definition of Done

- grain không mơ hồ;
- schema giải thích được;
- PK/FK đúng;
- query không double-count;
- extension scenario hợp lý.

---

# 8. Phase E — Data Mart Design & DW → Mart ETL

## 8.1 High-level

Data Mart được thiết kế theo **business subject/domain**, không theo công nghệ output.

Baseline architecture:

```text
                         DATA WAREHOUSE
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
   Operations Mart       Guest/Customer Mart   Revenue & Cancellation Mart
          │                     │                     │
      A / R / M               A / R / M             A / R / M
                                \
                                 \
                         Booking / Commercial
                           Performance Mart
                                │
                              A / R
```

Trong đó:

```text
A = Analytics / OLAP
R = Reporting
M = Mining / DSS
```

Không bắt buộc tất cả Mart có đủ A/R/M.

## 8.2 Nguyên tắc grain

Không nên tạo một bảng khổng lồ chứa mọi thứ cho mọi use case.

Baseline:

```text
Operations Mart
    grain = hotel × day

Guest / Customer Mart
    base grain = booking / party
    aggregate = hotel × day × party_type

Revenue & Cancellation Mart
    base grain = booking
    aggregate = hotel × period

Booking Performance Mart
    grain = date × hotel × channel × market segment
```

## 8.3 Mart 1 — Operations Mart

### Table / materialized view gợi ý

```text
mart.daily_hotel_operations
```

Fields:

```text
date_key
hotel_key

# Calendar/context
is_weekend
is_holiday
holiday_name
event_flag
temperature_mean
precipitation
humidity
wind_speed
weather_code

# Measures
total_bookings
total_guests
total_adults
total_children
total_babies
total_stay_nights
avg_party_size
avg_stay_nights
avg_lead_time
avg_adr
total_cancellations
cancellation_rate
```

### SQL aggregate sketch

```sql
CREATE MATERIALIZED VIEW mart.daily_hotel_operations AS
SELECT
    f.date_key,
    f.hotel_key,
    COUNT(*) AS total_bookings,
    SUM(f.total_guests) AS total_guests,
    SUM(f.total_stay_nights) AS total_stay_nights,
    AVG(f.total_guests::numeric) AS avg_party_size,
    AVG(f.total_stay_nights::numeric) AS avg_stay_nights,
    AVG(f.lead_time::numeric) AS avg_lead_time,
    AVG(f.adr) AS avg_adr,
    SUM(f.is_canceled) AS total_cancellations,
    AVG(f.is_canceled::numeric) AS cancellation_rate
FROM dw.fact_booking f
GROUP BY f.date_key, f.hotel_key;
```

> Calendar/weather fields có thể join từ conformed dimensions/context tables trong view cuối.

### Downstream

```text
DO-A* → OLAP demand / holiday / weather analysis
DO-R* → weekly operations reports
DO-M01 → 7-day guest demand forecast
```

---

## 8.4 Mart 2 — Guest / Customer Mart

### Base table/view

```text
mart.guest_booking_profile
```

Fields:

```text
booking_key
date_key
hotel_key
country_key
channel_key
market_segment_key
customer_type
is_repeated_guest
adults
children
babies
total_guests
party_type
reserved_room_type
assigned_room_type
room_changed_flag
total_stay_nights
lead_time
adr
is_canceled
```

### Aggregate table/view

```text
mart.daily_guest_mix
```

Fields:

```text
date_key
hotel_key
party_type
booking_count
guest_count
avg_party_size
avg_stay_nights
avg_adr
room_change_rate
```

Hoặc wide aggregate cho forecasting/reporting:

```text
date_key
hotel_key
single_bookings
couple_bookings
family_bookings
other_group_bookings
single_ratio
couple_ratio
family_ratio
other_group_ratio
```

### Party type transformation

Pseudo SQL:

```sql
CASE
    WHEN adults = 1
         AND COALESCE(children, 0) = 0
         AND babies = 0
        THEN 'SINGLE'

    WHEN adults = 2
         AND COALESCE(children, 0) = 0
         AND babies = 0
        THEN 'COUPLE'

    WHEN COALESCE(children, 0) > 0
         OR babies > 0
        THEN 'FAMILY'

    ELSE 'OTHER_GROUP'
END AS party_type
```

### Downstream

```text
GC-A* → guest/room composition analytics
GC-R* → guest mix / room demand reports
GC-M01 → single/couple/family forecast
```

---

## 8.5 Mart 3 — Revenue & Cancellation Mart

### Base booking-risk view

```text
mart.booking_cancellation_risk_base
```

Fields:

```text
booking_key
date_key
hotel_key
channel_key
market_segment_key
customer_type
country_key
lead_time
lead_time_bucket
deposit_type
is_repeated_guest
previous_cancellations
previous_bookings_not_canceled
booking_changes
days_in_waiting_list
adr
total_stay_nights
total_guests
special_requests
is_canceled
estimated_booking_value
```

### Derived booking value

```sql
adr * total_stay_nights AS estimated_booking_value
```

### Aggregate reporting view

```text
mart.daily_revenue_cancellation
```

Fields:

```text
date_key
hotel_key
total_bookings
canceled_bookings
non_canceled_bookings
cancellation_rate
avg_lead_time
avg_adr
gross_estimated_booking_value
canceled_estimated_booking_value
retained_estimated_booking_value
```

### Prediction output table

Có thể tách model output ra khỏi Mart core:

```text
mart.booking_cancellation_predictions
```

Fields:

```text
booking_key
scored_at
cancel_probability
risk_level
estimated_booking_value
estimated_value_at_risk
```

Aggregate DSS:

```text
expected_cancellation_count
predicted_cancellation_rate
estimated_revenue_at_risk
expected_retained_booking_value
```

### Downstream

```text
RC-A* → cancellation/revenue-risk analytics
RC-R* → cancellation + revenue assurance reports
RC-M01 → booking cancellation classification + aggregate outlook
```

---

## 8.6 Mart 4 — Booking / Commercial Performance Mart

### Aggregate view

```text
mart.booking_commercial_performance
```

Grain:

```text
1 row = date × hotel × channel × market_segment
```

Fields:

```text
date_key
hotel_key
channel_key
market_segment_key

total_bookings
total_guests
total_stay_nights
total_cancellations
cancellation_rate
avg_adr
avg_lead_time
avg_party_size
repeated_guest_count
repeated_guest_rate
avg_special_requests
```

Optional:

```text
gross_estimated_booking_value
retained_estimated_booking_value
```

### SQL aggregate sketch

```sql
CREATE MATERIALIZED VIEW mart.booking_commercial_performance AS
SELECT
    f.date_key,
    f.hotel_key,
    f.channel_key,
    f.segment_key AS market_segment_key,

    COUNT(*) AS total_bookings,
    SUM(f.total_guests) AS total_guests,
    SUM(f.total_stay_nights) AS total_stay_nights,
    SUM(f.is_canceled) AS total_cancellations,
    AVG(f.is_canceled::numeric) AS cancellation_rate,
    AVG(f.adr) AS avg_adr,
    AVG(f.lead_time::numeric) AS avg_lead_time,
    AVG(f.total_guests::numeric) AS avg_party_size

FROM dw.fact_booking f
GROUP BY
    f.date_key,
    f.hotel_key,
    f.channel_key,
    f.segment_key;
```

### Downstream

```text
BP-A* → channel / segment / booking performance analytics
BP-R* → booking commercial reports
Mining → không bắt buộc ở baseline
```

---

## 8.7 ETL DW → Mart organization

Về logic, mỗi Mart có pipeline riêng vì dependency khác nhau:

```text
src/etl/dw_to_mart/
├── operations/
│   └── build_operations_mart.py
├── guest_customer/
│   └── build_guest_customer_mart.py
├── revenue_cancellation/
│   └── build_revenue_cancellation_mart.py
├── booking_performance/
│   └── build_booking_performance_mart.py
└── refresh_marts.py
```

Không có nghĩa 4 codebase độc lập; shared transformation có thể tái sử dụng.

## 8.8 Dependency principle

Ví dụ DW thêm:

```text
weather.humidity
```

Ảnh hưởng có thể là:

```text
Operations Mart             → UPDATE nếu dùng humidity
Guest/Customer Mart         → NO CHANGE
Revenue/Cancellation Mart   → NO CHANGE nếu không dùng
Booking Performance Mart    → NO CHANGE
```

Ví dụ thêm customer loyalty attribute:

```text
Operations Mart             → có thể không đổi
Guest/Customer Mart         → UPDATE
Revenue/Cancellation Mart   → UPDATE nếu model cancellation cần
Booking Performance Mart    → UPDATE nếu report commercial cần
```

Tức là:

> **DW thay đổi → chỉ update downstream Mart/pipeline thực sự phụ thuộc vào field/business mới.**

## 8.9 Data Mart outputs

Sau phase này hệ thống có thể có:

```text
mart.daily_hotel_operations
mart.guest_booking_profile
mart.daily_guest_mix
mart.booking_cancellation_risk_base
mart.daily_revenue_cancellation
mart.booking_commercial_performance
```

Model output có thể bổ sung sau:

```text
mart.booking_cancellation_predictions
artifacts/forecast_guest_demand.csv
artifacts/forecast_guest_mix.csv
```

## 8.10 Đóng góp cho các phần sau

```text
Operations Mart
├── Analytics
├── Reporting
└── Demand Forecast DSS

Guest/Customer Mart
├── Analytics
├── Reporting
└── Guest Composition DSS

Revenue & Cancellation Mart
├── Analytics
├── Reporting
└── Cancellation / Revenue Assurance DSS

Booking Performance Mart
├── Analytics
└── Reporting
```

## 8.11 Definition of Done

Data Mart phase được xem là làm tốt khi:

- mỗi Mart đại diện cho một business domain rõ ràng;
- grain của từng Mart/view được viết thành câu cụ thể;
- aggregate fields có công thức rõ;
- không tạo Mart chỉ vì muốn đủ Analytics/Reporting/Mining;
- shared dimensions lấy từ DW nhất quán;
- KPI trùng nhau giữa các Mart phải dùng cùng definition;
- Mart có dependency mapping rõ;
- Analytics/Reporting/Mining downstream không phải quay lại raw data;
- nếu bỏ ML đi, các Mart chính vẫn có business value độc lập.

---

# 9. Phase F — Analytics / OLAP

## 9.1 High-level

Analytics = người dùng chủ động khám phá dữ liệu.

## 9.2 Business questions

Ví dụ:

1. Booking trend theo tháng?
2. Cancellation cao ở channel nào?
3. City vs Resort Hotel khác nhau thế nào?
4. Holiday vs non-holiday demand khác nhau không?

## 9.3 OLAP operations

### Slice

```sql
WHERE year = 2017
```

### Dice

```sql
WHERE
    year = 2017
    AND hotel = 'City Hotel'
    AND channel = 'Online TA'
```

### Roll-up

```sql
GROUP BY year
```

thay vì:

```sql
GROUP BY year, month
```

### Drill-down

```text
Year
 ↓
Quarter
 ↓
Month
 ↓
Day
```

## 9.4 Code-level folder

```text
sql/olap/
├── booking_trend.sql
├── cancellation_by_channel.sql
├── hotel_comparison.sql
├── holiday_analysis.sql
└── drilldown_queries.sql
```

## 9.5 Dashboard layer

Ví dụ Streamlit:

```text
dashboard/
├── app.py
├── pages/
│   ├── 1_analytics.py
│   ├── 2_reports.py
│   └── 3_dss.py
└── services/
    └── database.py
```

## 9.6 Output

```text
Interactive charts
Filters
Tables
OLAP drill-down
```

## 9.7 Đóng góp

Analytics dùng để:

- hiểu lịch sử;
- kiểm tra assumptions;
- phát hiện pattern;
- hỗ trợ giải thích DSS.

## 9.8 Definition of Done

- chart gắn business question;
- query reproducible;
- filter hoạt động;
- có OLAP operation thật;
- dashboard value khớp SQL kiểm chứng.

---

# 10. Phase G — Reporting

## 10.1 High-level

Reporting = output định kỳ, format cố định.

## 10.2 Report đề xuất

```text
Monthly Hotel Performance Report
```

KPI:

```text
Total Bookings
Cancellation Rate
Average ADR
Average Lead Time
Stay Nights
Total Guests
```

## 10.3 SQL view

```sql
CREATE VIEW mart.monthly_hotel_report AS
SELECT
    year,
    month,
    hotel_key,

    SUM(total_bookings) AS total_bookings,
    SUM(total_cancellations) AS total_cancellations,
    AVG(avg_adr) AS avg_adr,
    AVG(avg_lead_time) AS avg_lead_time

FROM mart.daily_hotel_metrics
GROUP BY
    year,
    month,
    hotel_key;
```

## 10.4 Output

Ví dụ:

```text
September 2017
--------------------------
Bookings           12,482
Cancellation Rate    21.4%
ADR                 126.4
Avg Lead Time        89.2
```

## 10.5 Contribution

Reporting cung cấp:

- operational summary;
- management KPI;
- baseline để so với forecast.

## 10.6 Definition of Done

- KPI formula document;
- report reproducible;
- same filter → same KPI as analytics;
- period rõ;
- data refresh timestamp rõ.

---

# 11. Phase H — Mining / Demand Forecasting

## 11.1 High-level

Mục tiêu:

```text
Historical Mart Data
       ↓
Feature Engineering
       ↓
Forecasting Model
       ↓
7-day Prediction
```

## 11.2 Target cần chốt

Ví dụ:

```text
daily_booking_demand
```

định nghĩa:

> số booking/arrival records của mỗi hotel trong mỗi ngày.

Không đổi target giữa chừng.

## 11.3 Feature table

```text
mart.demand_features
```

Possible columns:

```text
date
hotel_key

target_demand

day_of_week
month
quarter
is_weekend
is_holiday

temperature_mean
precipitation
humidity

lag_1
lag_7
rolling_mean_7
rolling_mean_14
```

## 11.4 Code-level feature engineering

```python
df["lag_1"] = (
    df.groupby("hotel_key")["target_demand"]
      .shift(1)
)

df["lag_7"] = (
    df.groupby("hotel_key")["target_demand"]
      .shift(7)
)

df["rolling_mean_7"] = (
    df.groupby("hotel_key")["target_demand"]
      .shift(1)
      .rolling(7)
      .mean()
)
```

## 11.5 Important — Leakage

Không được dùng:

```text
future target
future reservation outcome
field chỉ biết sau thời điểm prediction
```

Time split:

```text
Train → Validation → Test
theo thời gian
```

Không random split cho forecasting chính.

## 11.6 Baseline

Phải có baseline:

```text
Naive:
prediction(t) = actual(t-1)
```

hoặc:

```text
Seasonal naive:
prediction(t) = actual(t-7)
```

## 11.7 Models

Sau baseline:

```text
Linear Regression
Random Forest
XGBoost / LightGBM
```

Nếu muốn time-series:

```text
ARIMA / Prophet
```

nhưng không cần quá nhiều model.

## 11.8 Evaluation

Primary:

```text
MAE
```

Secondary:

```text
RMSE
MAPE (nếu target không nhiều zero)
```

## 11.9 Code-level folder

```text
src/dss/
├── features/
│   ├── build_features.py
│   └── leakage_checks.py
│
├── training/
│   ├── baseline.py
│   ├── train_model.py
│   └── evaluate.py
│
├── inference/
│   └── predict_next_7_days.py
│
└── rules/
    └── demand_rules.py
```

## 11.10 Output

```text
models/demand_model.pkl
artifacts/model_metrics.json
artifacts/forecast.csv
```

Example:

```text
date,hotel,predicted_demand
2017-09-01,City Hotel,87
2017-09-02,City Hotel,92
...
```

## 11.11 Downstream contribution

Prediction không phải end-point.

```text
Forecast
   ↓
DSS Rules
   ↓
Decision Support UI
```

## 11.12 Definition of Done

- baseline có;
- model compare baseline;
- no leakage;
- time split đúng;
- forecast reproducible;
- output được DSS sử dụng.

---

# 12. Phase I — DSS

## 12.1 High-level

DSS = Prediction + Context + Decision Rule.

## 12.2 Rule layer

Ví dụ:

```python
def demand_level(pred, historical_mean, historical_std):
    if pred > historical_mean + historical_std:
        return "HIGH"
    elif pred < historical_mean - historical_std:
        return "LOW"
    return "NORMAL"
```

## 12.3 Suggested actions

```python
ACTION_MAP = {
    "HIGH": [
        "Review room availability",
        "Prepare staffing capacity",
        "Review pricing strategy"
    ],
    "NORMAL": [
        "Maintain current operating plan"
    ],
    "LOW": [
        "Review promotion opportunities",
        "Monitor booking channels"
    ]
}
```

## 12.4 UI

```text
Forecast next 7 days

Date       Predicted    Status
01/11      83           HIGH
02/11      85           HIGH
03/11      62           NORMAL
...

Decision Support
- High demand expected on 01/11–02/11
- Review capacity
- Prepare staff
```

## 12.5 Output

```text
Forecast chart
Demand status
Alert
Suggested actions
```

## 12.6 Definition of Done

DSS phải trả lời:

> “Kết quả prediction này có ý nghĩa gì cho người quản lý?”

Nếu chỉ show:

```text
RMSE = 12.4
```

thì chưa phải DSS hoàn chỉnh.

---

# 13. Phase J — Integration & End-to-End Demo

## 13.1 End-to-End Flow

```text
Raw Files
   ↓
Ingestion
   ↓
Staging
   ↓
ETL
   ↓
Data Warehouse
   ↓
Data Mart
   ↓
Analytics / Reporting / Mining
   ↓
DSS
```

## 13.2 Pipeline runner

Ví dụ:

```text
scripts/run_pipeline.py
```

Pseudo:

```python
def main():
    ingest_sources()
    load_source_to_staging()
    validate_staging()
    load_dimensions()
    load_fact_booking()
    validate_dw()
    refresh_marts()
    build_dss_features()
```

## 13.3 CLI

```bash
python scripts/run_pipeline.py
```

Optional:

```bash
python scripts/run_pipeline.py --from staging --to mart
```

## 13.4 Demo story

1. Show raw source.
2. Run ETL.
3. Show staging.
4. Show DW star schema.
5. Show Mart.
6. Show OLAP.
7. Show monthly report.
8. Show forecasting.
9. Show DSS recommendation.

## 13.5 Definition of Done

- pipeline chạy end-to-end;
- không cần sửa data bằng tay;
- dashboard/report/model đều dùng official Mart/DW;
- KPI nhất quán;
- có fallback screenshots/data.

---

# 14. Data Contracts giữa các phase

Đây là phần rất quan trọng để cả nhóm không làm lệch nhau.

## Contract 1 — Raw → Staging

Expected:

```text
same business information
+ ingestion metadata
```

## Contract 2 — Staging → DW

Expected:

```text
clean
standardized
integrated
surrogate keys
business rules applied
```

## Contract 3 — DW → Mart

Expected:

```text
business-oriented
query-friendly
possibly aggregated
```

## Contract 4 — Mart → Analytics

Expected:

```text
dimensions + measures
```

## Contract 5 — Mart → DSS

Expected:

```text
time-indexed feature dataset
no leakage
target clearly defined
```

---

# 15. Repo Structure đề xuất — Full-stack DWDSS

```text
hotel-dwdss/
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── app/router.jsx
│       ├── components/
│       │   ├── charts/
│       │   ├── tables/
│       │   ├── filters/
│       │   ├── kpi/
│       │   └── layout/
│       ├── pages/
│       │   ├── Overview/
│       │   ├── Analytics/
│       │   │   ├── Operations/
│       │   │   ├── GuestCustomer/
│       │   │   ├── RevenueCancellation/
│       │   │   └── BookingPerformance/
│       │   ├── Reports/
│       │   │   ├── Operations/
│       │   │   ├── GuestCustomer/
│       │   │   ├── RevenueCancellation/
│       │   │   └── BookingPerformance/
│       │   └── DSS/
│       │       ├── DemandForecast/
│       │       ├── GuestMixForecast/
│       │       └── CancellationRisk/
│       ├── services/
│       │   ├── apiClient.js
│       │   ├── analyticsApi.js
│       │   ├── reportingApi.js
│       │   └── dssApi.js
│       ├── hooks/
│       ├── utils/
│       └── main.jsx
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── api/
│       │   ├── analytics.py
│       │   ├── reports.py
│       │   ├── dss.py
│       │   └── metadata.py
│       ├── services/
│       │   ├── analytics_service.py
│       │   ├── reporting_service.py
│       │   └── dss_service.py
│       ├── repositories/
│       │   ├── operations_repository.py
│       │   ├── guest_repository.py
│       │   ├── revenue_repository.py
│       │   └── booking_repository.py
│       ├── schemas/
│       ├── db/
│       │   ├── connection.py
│       │   └── queries.py
│       └── core/config.py
│
├── pipeline/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── ingestion/
│   │   ├── booking/
│   │   ├── weather/
│   │   ├── holiday/
│   │   └── event/
│   ├── source_to_staging/
│   │   ├── booking.py
│   │   ├── weather.py
│   │   ├── holiday.py
│   │   └── event.py
│   ├── staging_to_dw/
│   │   ├── dimensions/
│   │   ├── facts/
│   │   ├── transformations/
│   │   └── run.py
│   ├── dw_to_mart/
│   │   ├── operations.py
│   │   ├── guest_customer.py
│   │   ├── revenue_cancellation.py
│   │   ├── booking_performance.py
│   │   └── run.py
│   ├── quality/
│   └── common/
│
├── ml/
│   ├── requirements.txt
│   ├── demand_forecast/
│   │   ├── features.py
│   │   ├── baseline.py
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   └── predict.py
│   ├── guest_mix/
│   │   ├── features.py
│   │   ├── baseline.py
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   └── predict.py
│   ├── cancellation/
│   │   ├── features.py
│   │   ├── baseline.py
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   └── predict.py
│   ├── common/
│   └── artifacts/
│       ├── demand_model.joblib
│       ├── guest_mix_model.joblib
│       └── cancellation_model.joblib
│
├── database/
│   ├── staging/
│   ├── warehouse/
│   ├── marts/
│   │   ├── operations_mart.sql
│   │   ├── guest_customer_mart.sql
│   │   ├── revenue_cancellation_mart.sql
│   │   └── booking_performance_mart.sql
│   ├── olap/
│   │   ├── operations/
│   │   ├── guest_customer/
│   │   ├── revenue_cancellation/
│   │   └── booking_performance/
│   └── validation/
│
├── data/
│   ├── raw/
│   │   ├── booking/
│   │   ├── weather/
│   │   ├── holiday/
│   │   └── event/
│   ├── sample/
│   └── README.md
│
├── notebooks/
│   ├── profiling/
│   ├── exploration/
│   └── experiments/
│
├── docs/
│   ├── architecture/
│   ├── business_requirements/
│   ├── data_dictionary/
│   ├── etl_spec/
│   ├── schema/
│   ├── api/
│   └── demo/
│
├── reports/
├── artifacts/
│   ├── forecasts/
│   ├── metrics/
│   ├── logs/
│   └── screenshots/
│
├── scripts/
│   ├── setup_db.py
│   ├── run_pipeline.py
│   ├── refresh_marts.py
│   ├── train_models.py
│   └── seed_demo_data.py
│
├── tests/
│   ├── pipeline/
│   ├── data_quality/
│   ├── warehouse/
│   ├── marts/
│   ├── backend/
│   └── ml/
│
└── infra/
    ├── frontend/nginx.conf
    └── docker/README.md
```

## 15.1 Trách nhiệm từng top-level folder

| Folder | Vai trò |
|---|---|
| `frontend/` | React dashboard, Analytics, Reporting, DSS UI |
| `backend/` | FastAPI, REST endpoints, service/business logic |
| `pipeline/` | Ingestion + 3 tầng ETL |
| `ml/` | Training/evaluation/inference cho 3 prediction |
| `database/` | DDL, Mart SQL, OLAP SQL, validation SQL |
| `data/` | Raw/sample data |
| `notebooks/` | Profiling, EDA, experiment; không chứa production pipeline chính |
| `docs/` | Architecture, BR, data dictionary, ETL spec, schema, API |
| `reports/` | Report templates/output |
| `artifacts/` | Forecast, metrics, logs, screenshots |
| `scripts/` | Entry-point cho workflow |
| `tests/` | Test pipeline/data/API/ML |
| `infra/` | Docker/nginx/infrastructure config |

## 15.2 Dependency giữa các module

```text
data/raw
   ↓
pipeline
   ↓
PostgreSQL: staging → dw → mart
   ↓                    ↓
backend              ml training
   ↓                    ↓
React              model artifacts
   ↑                    ↓
   └──────── FastAPI DSS API
```

## 15.3 Quy tắc codebase

- `frontend/` không chứa SQL.
- `backend/` không chạy full ETL.
- `pipeline/` không chứa UI logic.
- `ml/` không đọc raw trực tiếp nếu official Mart/feature table đã tồn tại.
- `database/` lưu DDL và analytical SQL có version control.
- notebook chỉ dùng exploration/experiment; logic ổn định chuyển sang `.py`.
- secrets chỉ qua `.env`; không commit credential.

---


# 16. Output của từng phase và downstream dependency

| Phase | Output chính | Ai dùng tiếp? |
|---|---|---|
| Data Sources | raw CSV/JSON | Staging ETL |
| Staging | stg_* tables | DW ETL |
| ETL | cleaned/integrated data | DW |
| DW | Fact + Dimensions | Mart |
| Mart | aggregated/business-ready data | Analytics, Reporting, Mining |
| Analytics | insights / OLAP result | Manager / report / interpretation |
| Reporting | fixed KPI/report | Manager |
| Mining | forecast | DSS |
| DSS | alert + suggested action | Decision maker |

---

# 16.5 Application Integration & Docker Deployment

## Analytics request flow

```text
React Analytics Page
      ↓
GET /api/analytics/operations/demand-trend
      ↓
FastAPI
      ↓
Operations Repository
      ↓
Operations Mart
      ↓
JSON
      ↓
Recharts
```

## Reporting request flow

```text
React Reports Page
      ↓
GET /api/reports/revenue/monthly
      ↓
FastAPI
      ↓
Reporting Service
      ↓
Revenue & Cancellation Mart
      ↓
Fixed KPI response
```

## DSS request flow

```text
React DSS Page
      ↓
GET /api/dss/demand-forecast?horizon=7
      ↓
FastAPI DSS Service
      ├── read latest Mart/features
      ├── load model artifact
      ├── run inference
      └── apply DSS rule
      ↓
Forecast + Status + Suggested Action
      ↓
React
```

## Docker Compose baseline

```yaml
services:
  db:
    image: postgres:17
    env_file: [.env]
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build: ./backend
    env_file: [.env]
    depends_on: [db]

  frontend:
    build: ./frontend
    depends_on: [backend]

  etl:
    build: ./pipeline
    env_file: [.env]
    depends_on: [db]

volumes:
  postgres_data:
```

Development:

```bash
docker compose up --build
```

Run ETL:

```bash
docker compose run --rm etl
```

## Output application layer

```text
Frontend → web dashboard
Backend  → REST API
Database → persistent staging/DW/Mart
ETL      → reproducible data pipeline
ML       → model artifacts + prediction output
```

## Definition of Done

- một lệnh dựng được frontend/backend/database;
- React không query DB trực tiếp;
- FastAPI chỉ đọc official DW/Mart/model artifacts;
- ETL chạy độc lập;
- PostgreSQL dùng persistent volume;
- model training không chạy khi backend startup;
- API response có schema ổn định;
- frontend có loading/error state cơ bản;
- `.env.example` đủ để thành viên khác dựng project.

---

# 17. Evaluation Framework

## 17.1 Data Source

Good:

- provenance rõ;
- field có lý do;
- raw immutable;
- reproducible ingestion.

## 17.2 Staging

Good:

- row reconciliation;
- metadata;
- traceability;
- profiling.

## 17.3 ETL

Good:

- modular;
- business rules documented;
- no duplicate;
- validation;
- rerun safe;
- extensible.

## 17.4 DW

Good:

- grain rõ;
- PK/FK đúng;
- Fact/Dim hợp lý;
- KPI không double-count;
- schema extensible.

## 17.5 Data Mart

Good:

- business-oriented;
- grain đúng workload;
- không duplicate vô ích;
- dependency rõ.

## 17.6 OLAP

Good:

- có slice/dice;
- drill-down/roll-up;
- SQL kiểm chứng;
- chart trả lời business question.

## 17.7 Reporting

Good:

- KPI formula rõ;
- period rõ;
- reproducible;
- nhất quán với Analytics.

## 17.8 Mining

Good:

- baseline;
- time split;
- no leakage;
- MAE/RMSE;
- reproducible model.

## 17.9 DSS

Good:

- forecast → decision logic;
- context rõ;
- suggested actions hợp lý;
- không overclaim optimization.

---

# 18. Timeline đến 10/11/2026

## 04/10 – 07/10 — Architecture & Business Design

### High-level

Chốt thiết kế.

### Low-level

- BR list;
- business questions;
- DBMS;
- architecture;
- target demand;
- grain sơ bộ;
- source list;
- repo skeleton.

### Output

```text
docs/business_requirements/
docs/architecture/
README.md
repo skeleton
```

### Gate

```text
DESIGN BASELINE
```

---

## 08/10 – 13/10 — Sources + Profiling

- thu booking/weather/holiday;
- event nếu khả thi;
- data dictionary;
- profiling;
- field mapping.

Output:

```text
data/raw/
notebooks/profiling/
docs/data_dictionary/
```

Gate:

```text
DATA SOURCES READY
```

---

## 14/10 – 19/10 — Staging + ETL Foundation

- staging DDL;
- source loaders;
- metadata;
- validation;
- transformation spec.

Gate:

```text
STAGING READY
```

---

## 20/10 – 25/10 — Data Warehouse

- grain freeze;
- Fact/Dimension;
- DDL;
- dimension ETL;
- fact ETL;
- integration;
- validation.

Gate:

```text
DW READY
SCHEMA FREEZE
```

---

## 26/10 – 29/10 — Data Mart + OLAP + Web Skeleton

- Mart;
- Mart ETL;
- OLAP queries;
- KPI definitions;
- React + Vite skeleton;
- FastAPI skeleton;
- kết nối FastAPI → PostgreSQL;
- first Analytics dashboard.

Gate:

```text
MART + OLAP READY
```

---

## 30/10 – 02/11 — Reporting + DSS Baseline

- monthly report;
- feature table;
- baseline forecasting;
- first model.

Gate:

```text
MODEL BASELINE
```

---

## 03/11 – 05/11 — DSS + Full-stack UI

- model comparison;
- forecast;
- alerts;
- DSS rules;
- FastAPI DSS endpoints;
- React DSS pages;
- Reporting pages;
- Dockerfiles cho frontend/backend/pipeline.

Gate:

```text
DEMO FEATURE COMPLETE
```

---

## 06/11 – 07/11 — Integration, Docker & Evaluation

- Docker Compose integration;
- end-to-end run;
- fix inconsistencies;
- reconciliation;
- evaluate ETL/DW/OLAP/ML;
- kiểm tra setup trên máy thành viên khác.

Gate:

```text
INTEGRATION FREEZE
```

---

## 08/11 — Report Freeze

- architecture diagram;
- screenshots;
- evaluation tables;
- limitations;
- repo instructions.

---

## 09/11 — Dry Run

- full demo;
- backup screenshots;
- backup DB/sample;
- fix blockers only.

---

## 10/11 — Final

```text
NO NEW FEATURES
SUBMIT STABLE VERSION
```

---

# 19. Checkpoint bắt buộc

## Checkpoint 1 — Business Freeze

Phải chốt:

```text
What problem?
Who uses it?
What decision?
What output?
```

## Checkpoint 2 — Grain Freeze

Phải trả lời:

> Một row của FactBooking là gì?

## Checkpoint 3 — Source-to-Target Mapping

Ví dụ:

```text
booking.adr
   ↓
staging.stg_booking.adr
   ↓
dw.fact_booking.adr
   ↓
mart.daily_hotel_metrics.avg_adr
   ↓
Analytics / Report
```

## Checkpoint 4 — No Leakage

Feature DSS phải được review trước training.

## Checkpoint 5 — KPI Reconciliation

Cùng filter:

```text
Analytics KPI
=
Reporting KPI
=
SQL validation
```

## Checkpoint 6 — End-to-End Traceability

Có thể chọn:

```text
Hotel = City Hotel
Date = X
```

và trace:

```text
Raw
↓
Staging
↓
DW
↓
Mart
↓
Dashboard / Model
```

---

# 20. Những điều không nên làm

- Không bắt đầu bằng chọn model.
- Không tạo dashboard trước business questions.
- Không coi Kaggle CSV là toàn bộ ETL.
- Không drop toàn bộ missing values.
- Không sửa raw bằng tay.
- Không dùng notebook như production pipeline duy nhất.
- Không tạo nhiều Mart không cần thiết.
- Không tính KPI không đủ dữ liệu.
- Không random split forecasting.
- Không để model dùng feature leakage.
- Không để Analytics và Reporting dùng công thức KPI khác nhau.
- Không thêm feature mới sau Integration Freeze trừ blocker.

---

# 21. Demo Story cuối cùng

## Step 1 — Business Need

```text
Manager wants:
- understand booking/cancellation
- monitor KPI
- forecast demand
```

## Step 2 — Sources

Show:

```text
Booking
Weather
Holiday
Event
```

## Step 3 — ETL

Show:

```text
Raw → Staging → Clean → Integrate → DW
```

## Step 4 — DW

Show:

```text
FactBooking
Dimensions
```

## Step 5 — Mart

Show:

```text
daily_hotel_metrics
```

## Step 6 — Analytics

Show:

- booking trend;
- cancellation;
- drill-down;
- slice/dice.

## Step 7 — Reporting

Show:

```text
Monthly Hotel Performance Report
```

## Step 8 — Mining

Show:

```text
Actual vs Forecast
MAE
7-day forecast
```

## Step 9 — DSS

Show:

```text
HIGH DEMAND
→ prepare capacity
→ monitor staffing
→ review pricing
```

## Step 10 — Evaluation

Show:

```text
ETL quality
DW correctness
OLAP coverage
Forecast performance
System limitations
```

---

# 22. Nguyên tắc quan trọng nhất

Toàn project phải giữ được chuỗi reasoning:

```text
Business Requirement
        ↓
Required Data
        ↓
Source
        ↓
ETL
        ↓
DW
        ↓
Mart
        ↓
Analytics / Reporting / Mining
        ↓
Business Insight / Decision
```

Nếu một field, table, Mart, chart hoặc model không giải thích được nó nằm ở đâu trong chuỗi trên và phục vụ business requirement nào, thì nên xem lại có cần nó không.
