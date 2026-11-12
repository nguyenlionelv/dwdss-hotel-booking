# DWDSS Hotel Booking — Frontend UI Specification & API Contracts

> **Mục đích tài liệu:** Thống nhất danh sách màn hình, cấu trúc routing, các khối thông tin hiển thị trên từng màn hình và API Contract tương ứng (request params, response schema, trạng thái dữ liệu). Chưa bàn đến chi tiết thiết kế visual (CSS/màu sắc), chỉ tập trung vào **Information Architecture**, **Data Binding** và **Hợp đồng giao tiếp Frontend ↔ Backend**.
>
> **Căn cứ đối chiếu (100% Aligned):**
> - [detailed_plan.md](../detailed_plan.md) (Mục 5, 6, 7, 8, 9)
> - [dw_design.md](../dw_design/dw_design.md) & [dw_report.md](../dw_report.md) (Quy tắc D01–D08, NULL/0, Country Calendar, Coverage)
> - [operations_mart.sql](../../database/marts/operations_mart.sql) (Schema thực tế của `mart.daily_hotel_operations` và `mart.daily_hotel_operations_by_country`)

---

## 1. Quy tắc Nghiệp vụ & Dữ liệu Bắt buộc trên UI / API

Trước khi đi vào từng màn hình, mọi API và màn hình Frontend phải tuân thủ **6 quy tắc bất biến** đã chốt trong DW & Mart:

1. **Phạm vi cố định:** Chỉ phục vụ **City Hotel** (Lisbon, Portugal — Timezone `Europe/Lisbon`). Không có bộ lọc chọn khách sạn. Khoảng ngày lịch sử thực tế (`actual`): `2015-07-01` → `2017-08-31` (**793 ngày**).
2. **Phân biệt `observed_total_guests` và `target_guests`:**
   - Trong 793 ngày thực tế, có **679 ngày** `guest_data_status = 'COMPLETE'` và **114 ngày** `guest_data_status = 'PARTIAL'` (do 144 booking không hủy có `ZERO_GUESTS`).
   - `observed_total_guests`: Tổng khách từ các booking không hủy hợp lệ (`guest_eligible = true`), dùng để hiển thị kèm nhãn chất lượng (`COMPLETE` / `PARTIAL`).
   - `target_guests`: Chỉ có giá trị khi ngày đó `guest_data_status = 'COMPLETE'`, bằng `null` ở 114 ngày `PARTIAL`.
3. **Quy tắc tính trung bình và tỷ lệ khi Roll-up (`BI-01`, `BI-05`):**
   - **Tuyệt đối không lấy `AVG()` của các cột trung bình ngày.** Mọi chỉ số ở mức Tuần/Tháng/Quý/Năm/Kỳ báo cáo phải tính lại từ tổng tử số / tổng mẫu số hợp lệ:
     - `cancellation_rate = SUM(total_cancellations) / NULLIF(SUM(total_bookings), 0)`
     - `avg_party_size = SUM(observed_total_guests) / NULLIF(SUM(guest_valid_booking_count), 0)`
     - `avg_stay_nights = SUM(observed_total_stay_nights) / NULLIF(SUM(stay_valid_booking_count), 0)`
     - `avg_lead_time = SUM(sum_lead_time) / NULLIF(SUM(lead_time_valid_count), 0)`
     - `avg_adr = SUM(sum_adr) / NULLIF(SUM(adr_valid_count), 0)`
   - **Khách trung bình/ngày (`avg_guests_per_day`):** Theo [detailed_plan.md mục 5](../detailed_plan.md#L164):
     - Mẫu số luôn là **số ngày lịch trong kỳ** (`calendar_days_count`); lọc theo `country_code` **không làm giảm mẫu số ngày**.
     - `strict_avg_guests_per_day` chỉ trả số khi **toàn bộ ngày trong kỳ có `guest_data_status = 'COMPLETE'`**, ngược lại trả `null` (đồng thời API trả thêm `observed_avg_guests_per_day = SUM(observed_total_guests) / calendar_days_count` kèm cờ `guest_data_status = 'PARTIAL'` để UI hiển thị rõ).
4. **Không cộng lặp Context / Quality qua Country:**
   - Bảng `mart.daily_hotel_operations_by_country` lặp lại các cột context/quality cấp ngày (`temperature_mean`, `precipitation`, `rejected_booking_count`, `guest_ineligible_booking_count`...). Khi truy vấn không lọc country, phải đọc từ `mart.daily_hotel_operations`; khi lọc theo country, không `SUM()` các cột context/quality cấp ngày.
5. **Đối soát đồng nhất (`BI-05`):**
   - Với cùng khoảng ngày (`start_date`, `end_date`) và cùng điều kiện lọc, khối `summary` của Analytics (`/api/analytics/operations/trend`) và khối `kpis` của Reports (`/api/reports/operations/weekly-demand`) **phải trả về kết quả KPI giống hệt nhau 100%**.
6. **Giới hạn diễn giải nghiệp vụ:**
   - Hệ thống chưa có dữ liệu tổng số phòng (inventory) hay định biên nhân sự, do đó **không hiển thị Occupancy %**, **không tự bịa số lượng phòng hay số nhân viên cụ thể** (ví dụ: không ghi *"tăng 2 nhân viên"* mà dùng đúng gợi ý chuẩn trong [detailed_plan.md mục 8.3](../detailed_plan.md#L230-L234)).

---

## 2. Cấu trúc Routing & Danh mục Màn hình (`FE-01`)

Khớp với cấu trúc thư mục `frontend/src/pages/` và 3 màn hình chính trong [detailed_plan.md mục 9](../detailed_plan.md#L249):

| Route | Component / Thư mục | Vai trò trong Scope hiện hành |
| :--- | :--- | :--- |
| `/` | Redirect → `/analytics/operations` | Mặc định vào màn hình phân tích Operations |
| `/analytics` hoặc `/analytics/operations` | `pages/Analytics/Operations` | **Màn hình 1 (Chính):** Operations Analytics (`DO-A01` → `DO-A05`) |
| `/reports` hoặc `/reports/operations` | `pages/Reports/Operations` | **Màn hình 2 (Chính):** Operations Reports (`DO-R01`, `DO-R02` + Export CSV) |
| `/dss` hoặc `/dss/demand-forecast` | `pages/DSS/DemandForecast` | **Màn hình 3 (Chính):** Demand Forecast 7 ngày & DSS Rules (`DO-M01`) |
| `/analytics/guest-customer`<br>`/analytics/revenue-cancellation`<br>`/analytics/booking-performance`<br>`/reports/*` & `/dss/*` (khác) | Placeholder Component | Hiển thị thông báo **"Out of MVP Scope (Thuộc phạm vi mở rộng)"** kèm nút quay về màn hình Operations tương ứng |

---

## 3. Toàn cục: App Shell (Header, Sidebar & Global Metadata)

### 3.1. Thông tin hiển thị
- **Sidebar (Menu điều hướng):**
  1. **Operations Analytics** (`/analytics/operations`)
  2. **Operations Reports** (`/reports/operations`)
  3. **Demand Forecast (DSS)** (`/dss/demand-forecast`)
- **Header (Thanh trạng thái toàn cục):**
  - **Badge cố định:** `City Hotel — Lisbon, Portugal (Europe/Lisbon)`
  - **Khoảng dữ liệu:** `2015-07-01 → 2017-08-31 (793 ngày)`
  - **Data Version & Thời điểm cập nhật:** `data_version` (rút gọn 8 ký tự đầu) + `published_at`
  - **Trạng thái kết nối:** Badge `Healthy` (Xanh) hoặc `Degraded` (Vàng/Đỏ) lấy từ `/health`.

### 3.2. API Contracts Toàn cục (Đã hoàn thành ở `API-01`)

#### 1) `GET /health`
```json
{
  "status": "healthy",
  "db_connected": true,
  "mart_published": true,
  "matches_active_dw": true,
  "data_version": "9fe497e2-45e0-4a8a-93cb-b09e25c040d3",
  "dw_run_id": "c138f58b-967f-440d-b4f0-459ca2305a41",
  "published_at": "2026-10-27T16:39:15.123456Z",
  "message": null
}
```

#### 2) `GET /api/metadata`
```json
{
  "hotel_name": "City Hotel",
  "location": "Lisbon, Portugal",
  "timezone": "Europe/Lisbon",
  "dw_run_id": "c138f58b-967f-440d-b4f0-459ca2305a41",
  "data_version": "9fe497e2-45e0-4a8a-93cb-b09e25c040d3",
  "published_at": "2026-10-27T16:39:15.123456Z",
  "date_range": {
    "actual_start": "2015-07-01",
    "actual_end": "2017-08-31",
    "total_days": 793
  },
  "context_status_summary": {
    "booking_data_status": { "COMPLETE": 793 },
    "guest_data_status": { "COMPLETE": 679, "PARTIAL": 114 },
    "holiday_data_status": { "COMPLETE": 793 },
    "temperature_status": { "COMPLETE": 793 },
    "precipitation_status": { "COMPLETE": 793 }
  },
  "supported_grains": ["day", "week", "month", "quarter", "year"],
  "supported_measures": [
    "total_bookings",
    "non_canceled_bookings",
    "total_cancellations",
    "cancellation_rate",
    "observed_total_guests",
    "observed_total_stay_nights",
    "avg_party_size",
    "avg_stay_nights",
    "avg_lead_time",
    "avg_adr"
  ],
  "countries": [
    { "country_key": 0, "country_code": "UNK", "country_name": "Unknown" },
    { "country_key": 1, "country_code": "PRT", "country_name": "Portugal" }
  ]
}
```

---

## 4. Màn hình 1: Operations Analytics (`/analytics/operations` — `FE-02`, `BI-01`, `API-02`)

Đáp ứng toàn bộ yêu cầu `DO-A01` → `DO-A05` và 5 thao tác OLAP: **Slice, Dice, Roll-up, Drill-down, Pivot**.

### 4.1. Các khối thông tin hiển thị trên màn hình

#### Khối 1: Bộ lọc chung (OLAP Slice & Dice Filter Bar)
- **Khoảng ngày đến (`start_date`, `end_date`):** Giới hạn trong `2015-07-01` → `2017-08-31`.
- **Mức thời gian (`grain` — Roll-up / Drill-down):** `year` | `quarter` | `month` | `week` (ISO week) | `day`.
- **Quốc gia (`country_code`):** Chọn `All Countries` (đọc `mart.daily_hotel_operations`) hoặc 1 mã quốc gia cụ thể như `PRT`, `FRA`, `UNK` (đọc `mart.daily_hotel_operations_by_country`).
- **Loại ngày (`is_weekend`):** `All` | `Weekday (false)` | `Weekend (true)`.
- **Ngày lễ (`is_holiday`):** `All` | `Holiday (true)` | `Non-Holiday (false)`.
- **Chỉ số chính hiển thị trên biểu đồ (`measure`):** Chọn từ `supported_measures` (mặc định `observed_total_guests`).

#### Khối 2: Bộ thẻ KPI tổng hợp (Summary KPI Cards — Khớp công thức mục 5 `detailed_plan.md`)
Hiển thị các chỉ số tính trên toàn bộ khoảng lọc:
1. **Total Bookings (`total_bookings`)** & **Non-Canceled Bookings (`non_canceled_bookings`)**
2. **Total Cancellations (`total_cancellations`)** & **Cancellation Rate (`cancellation_rate`)**
3. **Observed Total Guests (`observed_total_guests`)** (kèm chi tiết `adults` / `children` / `babies` và badge `guest_data_status`: `COMPLETE` hoặc `PARTIAL (n ngày thiếu điều kiện guest)`)
4. **Average Guests / Day:** Hiển thị `strict_avg_guests_per_day` (nếu 100% ngày COMPLETE) hoặc `observed_avg_guests_per_day` kèm ghi chú `PARTIAL`.
5. **Peak Demand Day (`peak_demand_days`):** Ngày có `observed_total_guests` cao nhất trong kỳ lọc (hiển thị tất cả các ngày đồng hạng nếu có).
6. **Observed Stay Nights (`observed_total_stay_nights`)** & **Avg Stay Nights (`avg_stay_nights`)**
7. **Avg Party Size (`avg_party_size`)**, **Avg Lead Time (`avg_lead_time`)**, **Avg ADR (`avg_adr`)**

#### Khối 3: Biểu đồ xu hướng & Tương tác Drill-down / Roll-up (`DO-A01`)
- **Biểu đồ xu hướng:** Trục X là `period_label` theo `grain`, trục Y là `measure` đang chọn (kết hợp đường/cột so sánh `observed_total_guests` và `non_canceled_bookings`).
- **Thanh đường dẫn Drill-down (Breadcrumb):** Ví dụ `All Years → 2016 → Q3 2016 → 2016-08`.
  - Click vào một cột/điểm trên biểu đồ sẽ tự động thu hẹp `start_date`/`end_date` vào kỳ đó và hạ `grain` xuống 1 cấp (`year` → `quarter` → `month` → `day`).
  - Click nút **Roll-up** trên thanh Breadcrumb sẽ nâng `grain` lên cấp cao hơn.
- **Bảng dữ liệu chi tiết bên dưới biểu đồ:** Hiển thị các dòng của `series` và dòng **Total / Roll-up Summary** ở cuối bảng để chứng minh: *Drill-down rồi Roll-up không làm đổi tổng*.

#### Khối 4: Bảng Pivot 2 chiều (`DO-A02` — Pivot Operator)
- **Điều khiển Pivot:**
  - Chọn chiều Hàng (`row_dim`): `month` | `quarter` | `year` | `day_of_week` | `is_weekend` | `is_holiday`
  - Chọn chiều Cột (`col_dim`): `is_weekend` | `is_holiday` | `quarter` | `year` | `month`
  - Nút **"Đổi trục (Swap Rows ↔ Columns)"**: Đổi trực tiếp `row_dim` và `col_dim` trên cùng tập dữ liệu.
  - Chọn `measure`: `observed_total_guests` | `total_bookings` | `non_canceled_bookings` | `cancellation_rate` | `avg_stay_nights` | `avg_party_size` | `avg_adr`.
- **Bảng kết quả:** Hiển thị ma trận giá trị kèm cột `Row Total`, dòng `Column Total` và ô `Grand Total` (các chỉ số trung bình/tỷ lệ ở cột Total cũng được tính từ tổng tử/tổng mẫu).

#### Khối 5: Phân tích Holiday, Weather & Country (`DO-A03`, `DO-A04`, `DO-A05`)
- **Panel A — Holiday vs Non-Holiday & Scope (`DO-A03`):**
  - Bảng & biểu đồ so sánh `Holiday` vs `Non-Holiday` (và chi tiết `National Holiday`, `Lisboa Municipal Holiday`).
  - **Bắt buộc hiển thị cả 2 chỉ số:** `observed_total_guests` (Tổng khách) **VÀ** `observed_avg_guests_per_day` (Khách trung bình/ngày = Tổng khách / `days_count`) + `avg_stay_nights` để không bị lệch do số ngày lễ ít hơn ngày thường ([detailed_plan.md dòng 169](../detailed_plan.md#L169)).
- **Panel B — Weather & Demand (`DO-A04`):**
  - So sánh lượng khách trung bình/ngày và tỷ lệ hủy theo nhóm thời tiết Lisbon (ERA5):
    - Nhóm lượng mưa (`precipitation`): Ngày khô ráo (`0 mm`), Mưa nhẹ (`(0, 5] mm`), Mưa vừa/to (`> 5 mm`).
    - Nhóm nhiệt độ (`temperature_mean`): Mát/Lạnh (`< 15°C`), Ôn hòa (`15°C – 22°C`), Ấm/Nóng (`> 22°C`).
  - Hiển thị kèm `temperature_status` / `precipitation_status` và ghi chú: *"Phân tích mô tả tương quan lịch sử, không khẳng định quan hệ nhân quả"*.
- **Panel C — Country & Demand (`DO-A05`):**
  - Biểu đồ & bảng xếp hạng các quốc gia có tổng khách đến (`observed_total_guests`) và số booking cao nhất trong khoảng lọc (bao gồm cả nhóm `UNK` — Unknown country theo rule downstream).

---

### 4.2. API Contracts cho Màn hình Analytics (`API-02`)

#### Endpoint 1: `GET /api/analytics/operations/trend`
- **Query Parameters:**
  - `start_date`: `YYYY-MM-DD` (mặc định `2015-07-01`)
  - `end_date`: `YYYY-MM-DD` (mặc định `2017-08-31`)
  - `grain`: `day` | `week` | `month` | `quarter` | `year` (mặc định `month`)
  - `country_code`: `str | None` (mặc định `None` = toàn bộ City Hotel)
  - `is_weekend`: `bool | None` (mặc định `None`)
  - `is_holiday`: `bool | None` (mặc định `None`)
- **Response Schema (`200 OK`):**
```json
{
  "data_version": "9fe497e2-45e0-4a8a-93cb-b09e25c040d3",
  "filters_applied": {
    "start_date": "2016-01-01",
    "end_date": "2016-12-31",
    "grain": "month",
    "country_code": null,
    "is_weekend": null,
    "is_holiday": null
  },
  "coverage": {
    "calendar_days_count": 366,
    "booking_complete_days": 366,
    "guest_complete_days": 312,
    "guest_partial_days": 54,
    "overall_guest_status": "PARTIAL",
    "rejected_booking_count": 0,
    "guest_ineligible_booking_count": 68
  },
  "summary": {
    "total_bookings": 38140,
    "non_canceled_bookings": 23410,
    "total_cancellations": 14730,
    "cancellation_rate": 0.386209,
    "observed_total_adults": 41200,
    "observed_total_children": 3620,
    "observed_total_babies": 300,
    "observed_total_guests": 45120,
    "target_guests": null,
    "strict_avg_guests_per_day": null,
    "observed_avg_guests_per_day": 123.2787,
    "observed_total_stay_nights": 78940,
    "avg_party_size": 1.9328,
    "avg_stay_nights": 3.3721,
    "avg_lead_time": 95.412,
    "avg_adr": 105.23,
    "peak_demand_days": [
      { "full_date": "2016-09-15", "observed_total_guests": 245, "guest_data_status": "COMPLETE" }
    ]
  },
  "series": [
    {
      "period_key": "2016-01",
      "period_label": "2016-01",
      "period_start": "2016-01-01",
      "period_end": "2016-01-31",
      "calendar_days_count": 31,
      "guest_data_status": "PARTIAL",
      "total_bookings": 2240,
      "non_canceled_bookings": 1580,
      "total_cancellations": 660,
      "cancellation_rate": 0.294643,
      "observed_total_guests": 2840,
      "target_guests": null,
      "strict_avg_guests_per_day": null,
      "observed_avg_guests_per_day": 91.6129,
      "observed_total_stay_nights": 5120,
      "avg_party_size": 1.8009,
      "avg_stay_nights": 3.2405,
      "avg_lead_time": 68.21,
      "avg_adr": 72.54
    }
  ]
}
```

#### Endpoint 2: `GET /api/analytics/operations/pivot`
- **Query Parameters:**
  - `start_date`, `end_date`, `country_code`, `is_weekend`, `is_holiday`
  - `row_dim`: `month` | `quarter` | `year` | `day_of_week` | `is_weekend` | `is_holiday` (mặc định `month`)
  - `col_dim`: `is_weekend` | `is_holiday` | `quarter` | `year` | `month` (mặc định `is_weekend`)
  - `measure`: một trong `supported_measures` (mặc định `observed_total_guests`)
- **Response Schema (`200 OK`):**
```json
{
  "data_version": "9fe497e2-45e0-4a8a-93cb-b09e25c040d3",
  "row_dim": "month",
  "col_dim": "is_weekend",
  "measure": "observed_total_guests",
  "columns": [
    { "col_key": "weekday", "col_label": "Weekday (Mon-Fri)" },
    { "col_key": "weekend", "col_label": "Weekend (Sat-Sun)" }
  ],
  "rows": [
    {
      "row_key": "1",
      "row_label": "Month 01",
      "cells": {
        "weekday": 2010,
        "weekend": 830
      },
      "row_total": 2840
    }
  ],
  "column_totals": {
    "weekday": 32100,
    "weekend": 13020
  },
  "grand_total": 45120
}
```

#### Endpoint 3: `GET /api/analytics/operations/impact`
- **Query Parameters:** `start_date`, `end_date`, `country_code`, `top_n` (mặc định `10`)
- **Response Schema (`200 OK`):**
```json
{
  "data_version": "9fe497e2-45e0-4a8a-93cb-b09e25c040d3",
  "holiday_impact": [
    {
      "group_key": "holiday",
      "group_label": "Holiday (National or Lisboa)",
      "days_count": 30,
      "total_bookings": 2950,
      "non_canceled_bookings": 1780,
      "cancellation_rate": 0.3966,
      "observed_total_guests": 3560,
      "observed_avg_guests_per_day": 118.67,
      "avg_stay_nights": 3.12,
      "avg_party_size": 2.00
    },
    {
      "group_key": "non_holiday",
      "group_label": "Non-Holiday",
      "days_count": 763,
      "total_bookings": 76380,
      "non_canceled_bookings": 44448,
      "cancellation_rate": 0.4181,
      "observed_total_guests": 84910,
      "observed_avg_guests_per_day": 111.28,
      "avg_stay_nights": 2.98,
      "avg_party_size": 1.91
    }
  ],
  "weather_impact": {
    "by_temperature": [
      {
        "bucket_key": "cool_lt_15",
        "bucket_label": "< 15°C",
        "days_count": 245,
        "observed_total_guests": 23100,
        "observed_avg_guests_per_day": 94.29,
        "cancellation_rate": 0.3712,
        "avg_stay_nights": 2.89
      },
      {
        "bucket_key": "mild_15_22",
        "bucket_label": "15°C – 22°C",
        "days_count": 380,
        "observed_total_guests": 44200,
        "observed_avg_guests_per_day": 116.32,
        "cancellation_rate": 0.4215,
        "avg_stay_nights": 3.01
      },
      {
        "bucket_key": "warm_gt_22",
        "bucket_label": "> 22°C",
        "days_count": 168,
        "observed_total_guests": 21170,
        "observed_avg_guests_per_day": 126.01,
        "cancellation_rate": 0.4408,
        "avg_stay_nights": 3.08
      }
    ],
    "by_precipitation": [
      {
        "bucket_key": "dry_0mm",
        "bucket_label": "Dry (0 mm)",
        "days_count": 560,
        "observed_total_guests": 64200,
        "observed_avg_guests_per_day": 114.64,
        "cancellation_rate": 0.4231
      },
      {
        "bucket_key": "rain_gt_0mm",
        "bucket_label": "Rainy (> 0 mm)",
        "days_count": 233,
        "observed_total_guests": 24270,
        "observed_avg_guests_per_day": 104.16,
        "cancellation_rate": 0.4012
      }
    ]
  },
  "country_breakdown": [
    {
      "country_key": 1,
      "country_code": "PRT",
      "country_name": "Portugal",
      "total_bookings": 30960,
      "non_canceled_bookings": 10290,
      "cancellation_rate": 0.6676,
      "observed_total_guests": 18450,
      "observed_avg_guests_per_day": 23.27,
      "guest_share": 0.2085
    }
  ]
}
```

---

## 5. Màn hình 2: Operations Reports (`/reports/operations` — `FE-03`, `BI-05`, `API-02`)

Đáp ứng 2 báo cáo cố định trong [detailed_plan.md mục 7](../detailed_plan.md#L187-L199): **DO-R01 — Weekly Demand Report** và **DO-R02 — Operations Capacity Summary**, kèm xuất CSV và đối soát KPI đồng nhất với Analytics.

### 5.1. Các khối thông tin hiển thị trên màn hình

#### Thanh điều khiển kỳ báo cáo (Report Period Selector)
- **Chế độ chọn kỳ:**
  - Mặc định theo **Tuần ISO (Thứ Hai – Chủ Nhật)**: chọn `iso_year` + `iso_week` (hoặc chọn từ danh sách các tuần khả dụng trong dataset).
  - Hỗ trợ chọn theo **Tháng (`year`, `month`)**, **Quý (`year`, `quarter`)** hoặc **Khoảng ngày tùy chỉnh (`start_date`, `end_date`)** để đối soát trực tiếp 1-1 với màn hình Analytics (`BI-05`).
- **Bộ lọc bổ sung:** `country_code` (tùy chọn).
- **Nút Xuất CSV (`Export CSV`):** Xuất file CSV đúng theo bảng và bộ lọc đang xem trên web.
- **Banner Metadata Báo cáo:** Hiển thị rõ:
  - Khoảng ngày thực tế trong kỳ (`actual_start` → `actual_end`, số ngày trong kỳ / 7 ngày). Nếu tuần ở biên dữ liệu chưa đủ 7 ngày (ví dụ tuần đầu `2015-W27` hoặc tuần cuối `2017-W35`), hiển thị cảnh báo: **`INCOMPLETE_WEEK (n/7 days available)`**.
  - Trạng thái coverage (`overall_guest_status`: `COMPLETE` / `PARTIAL`), thời điểm cập nhật (`published_at`), `data_version` và hộp chú giải công thức KPI.

#### Tab 1: DO-R01 — Weekly Demand Report
- **Bộ thẻ KPI cố định (Dùng cùng cấu trúc `summary` với Analytics để đảm bảo `Reporting KPI == Analytics KPI`):**
  1. Tổng booking (`total_bookings`)
  2. Booking không hủy (`non_canceled_bookings`)
  3. Tổng khách (`observed_total_guests` & `target_guests`)
  4. Khách trung bình/ngày (`strict_avg_guests_per_day` & `observed_avg_guests_per_day`)
  5. Ngày cao điểm (`peak_demand_days` — trả đủ các ngày đồng hạng)
  6. Số đêm ở trung bình (`avg_stay_nights`)
  7. Nhu cầu Cuối tuần & Ngày lễ (`weekend_guests`, `weekend_avg_guests_per_day`, `holiday_guests`, `holiday_avg_guests_per_day`)
  8. Tỷ lệ hủy hỗ trợ (`cancellation_rate`)
- **Bảng chi tiết từng ngày trong kỳ (`daily_rows`):**
  - Cột: `full_date`, `day_of_week`, `is_weekend`, `is_holiday`, `holiday_names`, `temperature_mean`, `precipitation`, `total_bookings`, `non_canceled_bookings`, `total_cancellations`, `cancellation_rate`, `observed_total_adults`, `observed_total_children`, `observed_total_babies`, `observed_total_guests`, `target_guests`, `observed_total_stay_nights`, `avg_party_size`, `avg_stay_nights`, `avg_lead_time`, `avg_adr`, `guest_data_status`.

#### Tab 2: DO-R02 — Operations Capacity Summary
- **Mục tiêu:** Tổng hợp lượng khách lịch sử của kỳ đang chọn và dự báo 7 ngày tiếp theo kể từ ngày cuối kỳ (`cutoff = period_end`) để lập kế hoạch vận hành.
- **2 Bảng / Nhóm thẻ tách biệt nhãn rõ ràng (`Historical Actual` vs `7-Day Forecast`):**
  - **Nhóm A — Historical Workload (Thực tế trong kỳ):**
    - Tổng khách thực tế (`observed_total_guests`) & cơ cấu thành phần (`adults`, `children`, `babies`).
    - Quy mô nhóm khách trung bình (`avg_party_size`).
    - Tổng stay-night workload (`observed_total_stay_nights`) phân theo nhóm ngày đến: **Weekday Stay Nights** vs **Weekend Stay Nights** vs **Holiday Stay Nights**.
    - Ngày cao điểm lịch sử trong kỳ (`historical_peak_days`).
  - **Nhóm B — Upcoming 7-Day Forecast Signal (Dự báo 7 ngày kế tiếp từ cuối kỳ):**
    - Tổng khách dự báo 7 ngày tới (`forecast_total_guests_7d`).
    - Ngày dự kiến cao điểm (`forecast_peak_days`).
    - Phân bổ số ngày theo mức nhu cầu (`HIGH` / `NORMAL` / `LOW`) và **gợi ý chuẩn bị vận hành chuẩn** (Housekeeping/F&B/Ca trực).
    - *Ghi chú bắt buộc trên UI:* *"Báo cáo chỉ cung cấp tín hiệu lập kế hoạch từ lượng khách đến và stay-nights; không tính occupancy, số phòng hay số nhân sự cố định do chưa có dữ liệu inventory/capacity."*

---

### 5.2. API Contracts cho Màn hình Reports (`API-02`)

#### Endpoint 1: `GET /api/reports/operations/weekly-demand` (`DO-R01`)
- **Query Parameters:**
  - Cách 1 (Theo tuần ISO): `iso_year: int`, `iso_week: int`
  - Cách 2 (Theo khoảng ngày bất kỳ để đối soát với Analytics): `start_date: YYYY-MM-DD`, `end_date: YYYY-MM-DD`
  - Tùy chọn: `country_code: str | None`
- **Response Schema (`200 OK`):**
```json
{
  "report_id": "DO-R01",
  "report_name": "Weekly Demand Report",
  "hotel_name": "City Hotel",
  "data_version": "9fe497e2-45e0-4a8a-93cb-b09e25c040d3",
  "published_at": "2026-10-27T16:39:15.123456Z",
  "period": {
    "iso_year": 2017,
    "iso_week": 32,
    "start_date": "2017-08-07",
    "end_date": "2017-08-13",
    "calendar_days_count": 7,
    "is_complete_week": true,
    "overall_guest_status": "COMPLETE"
  },
  "summary": {
    "total_bookings": 645,
    "non_canceled_bookings": 412,
    "total_cancellations": 233,
    "cancellation_rate": 0.36124,
    "observed_total_adults": 740,
    "observed_total_children": 72,
    "observed_total_babies": 8,
    "observed_total_guests": 820,
    "target_guests": 820,
    "strict_avg_guests_per_day": 117.1429,
    "observed_avg_guests_per_day": 117.1429,
    "observed_total_stay_nights": 1409,
    "avg_party_size": 1.9903,
    "avg_stay_nights": 3.4199,
    "avg_lead_time": 102.4,
    "avg_adr": 134.5,
    "peak_demand_days": [
      { "full_date": "2017-08-11", "observed_total_guests": 148, "guest_data_status": "COMPLETE" }
    ],
    "weekend_demand": {
      "days_count": 2,
      "observed_total_guests": 265,
      "observed_avg_guests_per_day": 132.5
    },
    "holiday_demand": {
      "days_count": 0,
      "observed_total_guests": 0,
      "observed_avg_guests_per_day": null
    }
  },
  "daily_rows": [
    {
      "date_key": 20170807,
      "full_date": "2017-08-07",
      "day_of_week": 1,
      "is_weekend": false,
      "is_holiday": false,
      "holiday_names": [],
      "temperature_mean": 23.4,
      "precipitation": 0.0,
      "total_bookings": 92,
      "non_canceled_bookings": 61,
      "total_cancellations": 31,
      "cancellation_rate": 0.336957,
      "observed_total_adults": 108,
      "observed_total_children": 10,
      "observed_total_babies": 0,
      "observed_total_guests": 118,
      "target_guests": 118,
      "observed_total_stay_nights": 210,
      "avg_party_size": 1.9344,
      "avg_stay_nights": 3.4426,
      "avg_lead_time": 98.1,
      "avg_adr": 131.2,
      "guest_data_status": "COMPLETE"
    }
  ]
}
```

#### Endpoint 2: `GET /api/reports/operations/capacity-summary` (`DO-R02`)
- **Query Parameters:** `start_date`, `end_date` (hoặc `iso_year`, `iso_week`)
- **Response Schema (`200 OK`):**
```json
{
  "report_id": "DO-R02",
  "report_name": "Operations Capacity Summary",
  "hotel_name": "City Hotel",
  "data_version": "9fe497e2-45e0-4a8a-93cb-b09e25c040d3",
  "historical_period": {
    "start_date": "2017-08-18",
    "end_date": "2017-08-24",
    "calendar_days_count": 7,
    "overall_guest_status": "COMPLETE",
    "observed_total_guests": 845,
    "observed_total_adults": 760,
    "observed_total_children": 78,
    "observed_total_babies": 7,
    "avg_party_size": 2.0119,
    "observed_total_stay_nights": 1520,
    "avg_stay_nights": 3.619,
    "stay_nights_by_arrival_group": {
      "weekday_arrival_stay_nights": 1010,
      "weekend_arrival_stay_nights": 510,
      "holiday_arrival_stay_nights": 0
    },
    "peak_demand_days": [
      { "full_date": "2017-08-19", "observed_total_guests": 154, "guest_data_status": "COMPLETE" }
    ]
  },
  "forecast_7d_summary": {
    "as_of_date": "2017-08-24",
    "horizon_start": "2017-08-25",
    "horizon_end": "2017-08-31",
    "model_version": "seasonal-naive-v1",
    "predicted_total_guests_7d": 862.0,
    "peak_forecast_days": [
      { "forecast_date": "2017-08-26", "predicted_guest_count": 154.0, "demand_level": "HIGH" }
    ],
    "demand_level_counts": { "HIGH": 2, "NORMAL": 4, "LOW": 1 },
    "forecasts": [
      {
        "as_of_date": "2017-08-24",
        "forecast_date": "2017-08-25",
        "predicted_guest_count": 128.0,
        "demand_level": "NORMAL",
        "recommended_action": "Duy trì kế hoạch vận hành, theo dõi thay đổi",
        "model_version": "seasonal-naive-v1",
        "generated_at": "2026-10-28T08:00:00Z"
      }
    ]
  },
  "capacity_disclaimer": "Chỉ cung cấp tín hiệu lập kế hoạch dựa trên lượng khách đến và stay-nights; chưa tính occupancy, số phòng cần dùng hay số nhân sự cần bố trí vì chưa có dữ liệu inventory/capacity."
}
```

#### Endpoint 3: `GET /api/reports/operations/export.csv`
- **Query Parameters:** `report_type` (`weekly-demand` | `capacity-summary`), `start_date`, `end_date`, `iso_year`, `iso_week`, `country_code`
- **Response:** `text/csv; charset=utf-8` với `Content-Disposition: attachment; filename="city_hotel_DO-R01_2017-08-07_2017-08-13.csv"`.

---

## 6. Màn hình 3: Demand Forecast & DSS (`/dss/demand-forecast` — `API-03`, `DO-M01`)

Tuân thủ nghiêm ngặt quy định tại [detailed_plan.md mục 8](../detailed_plan.md#L200-L237).

### 6.1. Các khối thông tin hiển thị trên màn hình

#### Khối 1: Bộ chọn Ngày chốt dữ liệu (`as_of_date` — Cutoff $T$) & Chọn Model
- **Date Picker `as_of_date` ($T$):** Default `2017-08-31`; forecasts `2017-09-01` through `2017-09-07`. Earlier cutoffs remain available for backtesting.
- **Model Selector:** Chọn mô hình đã train (mặc định mô hình tốt nhất trên tập validation hoặc `seasonal_naive`).
- **Nhãn minh bạch Cutoff:** Hiển thị rõ *"Dự báo tại ngày chốt T = YYYY-MM-DD cho 7 ngày tiếp theo (T+1 đến T+7) của City Hotel. Chỉ dùng lịch sử đến ngày T, không đọc actual sau T."*

#### Khối 2: Ngưỡng DSS 8 tuần & Thẻ Tổng hợp 7 ngày tới
- **Ngưỡng phân mức DSS (Tính trên 8 tuần lịch sử đầy đủ gần nhất = 56 ngày đến $T$):**
  - Hiển thị `mean_8w` ($\mu$), `std_8w` ($\sigma$), ngưỡng `HIGH` ($\mu + \sigma$), ngưỡng `LOW` ($\max(0, \mu - \sigma)$).
  - Nếu trước $T$ chưa đủ 56 ngày `COMPLETE`, hiển thị trạng thái `INSUFFICIENT_HISTORY` (*"Chưa đủ dữ liệu lịch sử để phân mức"*).
- **Tổng khách dự kiến trong 7 ngày (`total_predicted_guests_7d`)** & **Ngày cao điểm dự báo (`peak_forecast_days`)**.

#### Khối 3: Biểu đồ Actual vs Forecast (`detailed_plan.md` dòng 226)
- Vẽ chuỗi lịch sử gần nhất (ví dụ 14–28 ngày trước $T$) + 7 ngày dự báo ($T+1 \dots T+7$):
  - Đường nét liền: `actual_target_guests` (Lịch sử trước $T$, và cả actual của $T+1 \dots T+7$ nếu $T$ nằm trong quá khứ để người xem đối chiếu độ chính xác trong backtest).
  - Đường nét đứt (hoặc màu nổi bật): `predicted_guest_count` cho $T+1 \dots T+7$.
  - 2 đường ngang tham chiếu: ngưỡng `HIGH` ($\mu + \sigma$) và ngưỡng `LOW` ($\max(0, \mu - \sigma)$).

#### Khối 4: Bảng 7 dòng dự báo chuẩn & Gợi ý vận hành (`detailed_plan.md` dòng 226–234)
Hiển thị đúng 7 dòng cho City Hotel với các cột bắt buộc:
- `as_of_date`, `forecast_date`, `predicted_guest_count` (làm tròn khi hiển thị số khách, giữ số thực trong JSON), `demand_level` (`LOW` | `NORMAL` | `HIGH` | `INSUFFICIENT_HISTORY`), `recommended_action`, `model_version`, `generated_at`.
- **Bảng quy tắc gợi ý vận hành cố định ([detailed_plan.md dòng 230–234](../detailed_plan.md#L230-L234)):**
  - `HIGH`: *"Rà soát khả năng tiếp nhận, chuẩn bị nhân lực và workload housekeeping/F&B"*
  - `NORMAL`: *"Duy trì kế hoạch vận hành, theo dõi thay đổi"*
  - `LOW`: *"Rà soát phân bổ ca và lượng chuẩn bị theo nhu cầu thấp"*

#### Khối 5: Bảng đánh giá & So sánh Models với Baseline (`detailed_plan.md` dòng 214–224)
- Bảng so sánh kết quả Backtest giữa **Seasonal Naive (Baseline)**, **Linear Regression / Ridge**, **Random Forest**, **XGBoost**:
  - Cột: `model_name`, `overall_mae` (chính), `overall_rmse` (bổ sung), và sai số theo từng bước dự báo `h = 1..7`.

---

### 6.2. API Contract cho Màn hình DSS (`API-03`)

#### Endpoint: `GET /api/dss/demand-forecast`
- **Query Parameters:**
  - `as_of_date`: `YYYY-MM-DD` (mặc định `2017-08-24`)
  - `model_name`: `str | None` (mặc định model được chọn hoặc `seasonal_naive`)
- **Response Schema (`200 OK`):**
```json
{
  "hotel_name": "City Hotel",
  "as_of_date": "2017-08-24",
  "horizon": 7,
  "model_version": "seasonal-naive-v1",
  "generated_at": "2026-10-28T08:00:00Z",
  "dss_threshold_rule": {
    "lookback_days_required": 56,
    "complete_days_available": 56,
    "sufficient_history": true,
    "mean_guests_8w": 124.5,
    "std_guests_8w": 18.2,
    "high_threshold": 142.7,
    "low_threshold": 106.3
  },
  "summary": {
    "total_predicted_guests_7d": 910.0,
    "total_predicted_guests_7d_rounded": 910,
    "peak_forecast_days": [
      { "forecast_date": "2017-08-26", "predicted_guest_count": 152.0, "demand_level": "HIGH" }
    ]
  },
  "forecasts": [
    {
      "as_of_date": "2017-08-24",
      "forecast_date": "2017-08-25",
      "day_of_week": 5,
      "is_weekend": false,
      "is_holiday": false,
      "predicted_guest_count": 138.0,
      "predicted_guest_count_display": 138,
      "actual_guest_count": 135,
      "demand_level": "NORMAL",
      "recommended_action": "Duy trì kế hoạch vận hành, theo dõi thay đổi",
      "model_version": "seasonal-naive-v1",
      "generated_at": "2026-10-28T08:00:00Z"
    }
  ],
  "recent_history": [
    {
      "full_date": "2017-08-24",
      "observed_total_guests": 130,
      "target_guests": 130,
      "guest_data_status": "COMPLETE"
    }
  ],
  "model_comparison": [
    {
      "model_name": "seasonal_naive",
      "is_baseline": true,
      "is_selected": true,
      "overall_mae": 18.42,
      "overall_rmse": 24.15,
      "horizon_mae": { "1": 15.2, "2": 16.8, "3": 17.5, "4": 18.9, "5": 19.4, "6": 20.1, "7": 21.0 }
    }
  ]
}
```

---

## 7. Ma trận Đối chiếu Nghiệm thu (Traceability Matrix)

| Mã Yêu cầu / Task | Nội dung trong `detailed_plan.md` & Checklist | Màn hình & API đáp ứng trong tài liệu này |
| :--- | :--- | :--- |
| **DO-A01 / BI-01** | Xu hướng khách & booking theo ngày/tuần/tháng/quý/năm; Slice/Dice/Roll-up/Drill-down | `/analytics/operations` (Khối 1, 2, 3) + `GET /api/analytics/operations/trend` |
| **DO-A02 / BI-01** | So sánh weekday/weekend và mùa vụ; bảng Pivot đổi trục | `/analytics/operations` (Khối 4) + `GET /api/analytics/operations/pivot` |
| **DO-A03 / BI-01** | So sánh holiday/non-holiday (cả tổng khách và khách TB/ngày) | `/analytics/operations` (Khối 5 - Panel A) + `GET /api/analytics/operations/impact` |
| **DO-A04 / BI-01** | Phân tích thời tiết (nhiệt độ, lượng mưa) và demand | `/analytics/operations` (Khối 5 - Panel B) + `GET /api/analytics/operations/impact` |
| **DO-A05 / BI-01** | Phân tích quốc gia (`country`) và demand từ bảng `by_country` | `/analytics/operations` (Khối 5 - Panel C) + `GET /api/analytics/operations/impact` |
| **DO-R01 / BI-05** | Báo cáo nhu cầu hàng tuần + Xuất CSV + Khớp KPI 100% với Analytics | `/reports/operations` (Tab 1) + `GET /api/reports/operations/weekly-demand` + `export.csv` |
| **DO-R02 / BI-05** | Báo cáo tải vận hành (stay-nights, party size, lịch sử + forecast 7 ngày) | `/reports/operations` (Tab 2) + `GET /api/reports/operations/capacity-summary` |
| **DO-M01 / API-03** | Dự báo 7 ngày từ cutoff $T$, ngưỡng 8 tuần $\mu \pm \sigma$, bảng 7 dòng, so sánh baseline | `/dss/demand-forecast` + `GET /api/dss/demand-forecast` |
| **FE-01 / FE-02 / FE-03** | Router, API client, Loading/Error/Empty states, Coverage badges | Mục 1, 2, 3, 4, 5, 6 |
