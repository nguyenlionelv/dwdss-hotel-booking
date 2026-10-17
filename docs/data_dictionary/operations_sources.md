# Operations — data contract của ba nguồn

Tài liệu này là contract hiện hành cho Source → Staging của **một Operations Mart, chỉ City Hotel**. Booking, Holiday và Weather đều là nguồn bắt buộc. Event không thuộc phạm vi. Raw của cả ba nguồn bất biến và được định danh bằng checksum; riêng raw Booking giữ nguyên cả City Hotel lẫn Resort Hotel để truy vết. Xem [manifest](source_manifest_20261017.md) để lấy đúng file và tham số thu thập.

## Quy ước chung

- `NULL` trong cột giá trị Staging nghĩa là **không xác định**, không phải 0, `false`, ngày thường hay chuỗi `Unknown`. Không suy diễn/impute trong loader; không bỏ record chỉ vì missing.
- Chỉ nhận diện token missing **theo từng field** trong bảng dưới. Không áp dụng `NA`, `NULL` hoặc chuỗi rỗng toàn cục. Lưu nguyên token nguồn ở cột raw tương ứng hoặc payload raw. Giá trị hiện diện nhưng sai kiểu/miền là **invalid**, không đổi thành missing.
- Mỗi bảng có `_source_id`, `_source_file`, `_source_file_sha256`, `_source_row_id`, `_batch_id`, `_ingested_at timestamptz`. `_source_id` phân biệt Booking/Holiday/Weather; checksum phân biệt phiên bản file. `_source_row_id` là thứ tự record logic trong file gốc **trước mọi phép lọc**, tính từ 2 với header CSV ở vị trí 1; Weather dùng thứ tự phần tử daily từ 1. Đây là định danh nguồn, không phải reservation ID.
- Khóa nạp lại của từng nguồn là `(_source_file_sha256, _source_row_id)`; không dùng hash thuộc tính để xóa reservation trông giống nhau. Dòng lỗi vẫn gắn đủ metadata và raw value.
- Cột typed nullable; parse failure lưu raw token và issue, không âm thầm ép về 0/false/mean/`Unknown`. Record đọc được nhưng sai nghiệp vụ vẫn ở Staging. Record/file không đọc được vào reject hoặc batch failure, không tính là Staging.

## Booking — `staging.stg_booking`

Grain: **một record City Hotel của `hotel_bookings.csv` = một dòng Staging**. So sánh đúng giá trị nguồn `hotel = 'City Hotel'` khi Source → Staging. `Resort Hotel` được đếm `out_of_scope`; giá trị hotel rỗng hoặc không nhận diện được thuộc `unidentified_hotel`; không nạp hai nhóm này. Không cần và không được lọc City Hotel lần nữa ở Staging → DW.

Giữ toàn bộ 32 cột nguồn trong raw payload/các cột raw để không mất thông tin, kể cả field hiện chưa dùng. Bảng dưới quy định các field nghiệp vụ được typed; những cột còn lại giữ string nguồn, nullable nếu token missing của field đó được chốt sau khi profile.

| Field nguồn → Staging | Kiểu Staging | Nghĩa / rule | Token missing được nhận diện |
|---|---|---|---|
| `hotel` | `text` | Bộ lọc phạm vi, giá trị dòng đã nạp phải là `City Hotel` | Không có trong City subset; rỗng/giá trị không nhận diện tính `unidentified_hotel`, không nạp |
| `is_canceled` | `smallint` | 0 chưa hủy, 1 đã hủy; giá trị khác là invalid | Chỉ chuỗi rỗng nếu xuất hiện; không coi `0` là missing |
| `lead_time` | `integer` | Số ngày từ lúc đặt đến ngày đến, phải ≥ 0 | Chỉ chuỗi rỗng nếu xuất hiện |
| `arrival_date_year`, `arrival_date_day_of_month`, `arrival_date_week_number` | `integer` | Thành phần ngày đến và số tuần **theo nguồn**; không dùng source week làm ISO week | Chỉ chuỗi rỗng nếu xuất hiện |
| `arrival_date_month` | `text` | Tên tháng tiếng Anh theo nguồn | Chỉ chuỗi rỗng nếu xuất hiện |
| `arrival_date` | `date` | Parse nghiêm ngặt từ year/month/day; ngày không tồn tại là invalid | `NULL` nếu thiếu bất kỳ thành phần nào; parse failure có issue riêng |
| `stays_in_weekend_nights`, `stays_in_week_nights` | `integer` | Số đêm cuối tuần/ngày thường trong toàn kỳ ở; mỗi số phải ≥ 0; **không** phải flag weekday/weekend của ngày đến | Chỉ chuỗi rỗng nếu xuất hiện |
| `adults`, `children`, `babies` | `numeric` | Số khách từng nhóm, nguyên và ≥ 0; 0 là giá trị có thật | `children`: token `NA` (4 dòng City đo được), hoặc rỗng nếu xuất hiện; `adults`/`babies`: chỉ rỗng nếu xuất hiện |
| `country` | `text` | Mã nước của khách theo nguồn; giữ nguyên nếu hiện diện | Token `NULL` (24 dòng City đo được), hoặc rỗng nếu xuất hiện |
| `agent`, `company` | `text` | Mã nguồn; không suy diễn “không có agent/company” từ missing | Token `NULL` (lần lượt 8.131/75.641 dòng City), hoặc rỗng nếu xuất hiện |
| `adr` | `numeric` | Average Daily Rate của booking, không phải doanh thu kế toán | Chỉ chuỗi rỗng nếu xuất hiện; số âm cần issue/đánh giá theo quy tắc nghiệp vụ, không tự sửa |
| `reservation_status_date` | `date` | Ngày của trạng thái cuối, không phải ngày tạo booking | Chỉ rỗng nếu xuất hiện; ngày sai là invalid |

Các cột còn lại cũng thuộc record Staging, nullable và giữ raw token:

| Kiểu Staging | Các field và ý nghĩa | Token missing |
|---|---|---|
| `text` | `meal` (gói ăn), `market_segment` (phân khúc), `distribution_channel` (kênh), `reserved_room_type`/`assigned_room_type` (mã phòng), `deposit_type` (loại cọc), `customer_type` (loại khách), `reservation_status` (trạng thái cuối) | Chỉ rỗng nếu xuất hiện; không coi chuỗi `NA`/`NULL` là missing khi chưa có bằng chứng theo field |
| `smallint` | `is_repeated_guest` (flag khách lặp, miền 0/1) | Chỉ rỗng nếu xuất hiện; sai miền là invalid |
| `integer` | `previous_cancellations`, `previous_bookings_not_canceled`, `booking_changes`, `days_in_waiting_list`, `required_car_parking_spaces`, `total_of_special_requests` (các số đếm không âm) | Chỉ rỗng nếu xuất hiện; sai kiểu/âm là invalid |

Không dùng bộ token mặc định toàn cục của pandas (`keep_default_na=False` hoặc parser tương đương).

Các giá trị dẫn xuất chỉ tính khi đủ đầu vào hợp lệ: `total_guests = adults + children + babies`, `total_stay_nights = stays_in_weekend_nights + stays_in_week_nights`. Thiếu `children` cho `total_guests = NULL`, **không cách ly**. `is_weekend` tính từ `arrival_date`: thứ Hai–thứ Sáu là weekday, thứ Bảy–Chủ nhật là weekend. Holiday là thuộc tính độc lập, một ngày có thể vừa weekend vừa holiday.

## Holiday — `staging.stg_holiday`

Grain: **một dòng holiday được sinh cho một date × scope × holiday name**; có thể có nhiều lễ cùng ngày, không xóa trong Staging. Phạm vi Portugal (`PT`), national và Lisboa (`11`); năm 2015–2017, public holidays, `observed=false`, thư viện `python-holidays` 0.106 theo manifest. Lưu `_generator`, `_generator_version`, `_years`, `_country`, `_subdivision_setting`, `_observed_setting` ở batch/source metadata.

| Field | Kiểu Staging | Nghĩa / rule | Token missing được nhận diện |
|---|---|---|---|
| `date` | `date` | Ngày lễ lịch sử; ngày sai là invalid | Chuỗi rỗng nếu xuất hiện |
| `holiday_name` | `text` | Tên lễ theo thư viện, không tự điền tên | Chuỗi rỗng nếu xuất hiện |
| `country` | `text` | Phải là `PT` theo nguồn đã chốt; khác là issue | Chuỗi rỗng nếu xuất hiện |
| `subdivision` | `text` | `11` cho Lisboa; raw rỗng ở dòng national | Rỗng → SQL `NULL`; scope `national` riêng cho biết đây là lễ toàn quốc, không suy từ NULL |
| `scope` | `text` | `national` hoặc `Lisboa`; sai miền là invalid | Chuỗi rỗng nếu xuất hiện |
| `category` | `text` | `public` theo cấu hình sinh | Chuỗi rỗng nếu xuất hiện |
| `observed` | `boolean` | Cấu hình observed của record, hiện là `false` | Chuỗi rỗng nếu xuất hiện; `false` là giá trị có thật |

Không có dòng holiday trong một ngày **không tự động** nghĩa là non-holiday. Chỉ downstream được gán `false` khi xác nhận coverage lịch PT/Lisboa đầy đủ cho ngày đó; chưa xác nhận thì `is_holiday = NULL`.

## Weather — `staging.stg_weather`

Grain: **một phần tử daily của response cho ngày địa phương × địa điểm đại diện × model/request**. Nguồn Open-Meteo Historical Weather API, ERA5, Lisbon đại diện (request 38.72509, -9.1498; grid trả về 38.75, -9.25), timezone `Europe/Lisbon`, ngày 2015-07-01–2017-08-31. Đây không phải tọa độ chính xác của khách sạn. Lưu provider, endpoint, request parameters đầy đủ, requested/returned coordinates, model, timezone, daily variables và units trong batch/source metadata; xem manifest/raw JSON.

| Field | Kiểu Staging | Nghĩa / rule | Token missing được nhận diện |
|---|---|---|---|
| `time` → `date` | `date` | Ngày daily theo `Europe/Lisbon`; parse nghiêm ngặt | JSON `null` hoặc chuỗi rỗng nếu API gửi; parse failure là invalid |
| `temperature_2m_mean` | `numeric` | °C, nhiệt độ trung bình ngày ở 2 m | JSON `null` nếu xuất hiện; 0°C là giá trị có thật |
| `precipitation_sum` | `numeric` | mm, lượng mưa tổng ngày, phải ≥ 0 | JSON `null` nếu xuất hiện; 0 mm là giá trị có thật |

Weather thiếu ngày/giá trị hoặc request thất bại phải được báo riêng; không chuyển thiếu mưa thành 0. Historical ERA5 dùng phân tích mô tả, không phải dự báo thời tiết biết trước tại cutoff ML.
