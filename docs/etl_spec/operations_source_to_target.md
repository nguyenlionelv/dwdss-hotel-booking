# Operations — Source → Staging contract và nghiệm thu STAGING READY

Áp dụng cho đúng ba nguồn Booking, Holiday, Weather và một Operations Mart của City Hotel. [Data dictionary](../data_dictionary/operations_sources.md) là định nghĩa field/token/kiểu; [source manifest](../data_dictionary/source_manifest_20261017.md) là định danh các file thực. Event không nạp. Các ví dụ/quy tắc khác trong master plan hoặc workbook không thay thế contract này.

## Grain, khóa và mapping

| Nguồn raw | Bảng Staging và grain | Quy tắc Source → Staging | Handoff cho DW/context |
|---|---|---|---|
| Booking CSV nguyên bản | `staging.stg_booking`: một record `City Hotel` đúng theo vị trí trong CSV | Gán `_source_row_id` trên **toàn file trước lọc**; chỉ nạp `hotel = 'City Hotel'`. Đếm `Resort Hotel` là `out_of_scope`, hotel rỗng/không nhận diện là `unidentified_hotel`. Giữ raw payload/token và typed nullable. | City Hotel đã được lọc; Member 2 quyết định eligibility/field-specific transforms trước DW, không xóa record Staging. |
| Holiday CSV | `staging.stg_holiday`: một ngày × scope × tên lễ theo dòng sinh | Nạp mọi record đọc được, kể cả thiếu hoặc invalid, kèm issue. Giữ provenance cấu hình sinh lịch. | Gộp **nhiều lễ cùng ngày** thành một holiday context cho khóa `(City Hotel, local_date)`; có thể giữ danh sách tên/scope. |
| Weather JSON daily | `staging.stg_weather`: một phần tử daily × request/grid/model | Nạp daily entry đọc được, typed nullable và raw value. Giữ request/response provenance. | Tạo tối đa một weather context cho khóa `(City Hotel, local_date)` sau kiểm tra duplicate date/location/model; không chọn bản ghi tùy tiện. |

Context key trước join là `(hotel_key = City Hotel, local_date Europe/Lisbon)`. Booking join bằng **ngày đến**; mỗi context tối đa một dòng/khóa, dùng left join và assert số booking trước/sau bằng nhau. `is_weekend` từ ngày đến (Mon–Fri `false`, Sat–Sun `true`); `is_holiday` là thuộc tính độc lập. Holiday `false` chỉ khi coverage của PT/Lisboa cho ngày đã được xác nhận; nếu chưa, `NULL`. Weather `NULL` không phải 0 mm.

Metadata bắt buộc trên mỗi dòng: `_source_id`, `_source_file`, `_source_file_sha256`, `_source_row_id`, `_batch_id`, `_ingested_at timestamptz`. Batch/source registry lưu path/URL, checksum, thời điểm acquisition, parser/schema version, row counts, status; Holiday lưu `python-holidays` version, years 2015–2017, PT/Lisboa, category, observed setting; Weather lưu endpoint, request parameters, requested/returned coordinates, timezone, ERA5 model, daily variables và units. Raw bất biến, không ghi đè.

## Missing, invalid, reject

| Loại | Xử lý ở Source → Staging | Đối soát/báo cáo |
|---|---|---|
| Missing đã nhận diện theo **field** | Typed value `NULL`, giữ token raw và record. Không impute và không loại record. `children='NA'` là missing đã đo; không coi mọi `NA` ở mọi cột là missing. | Count riêng theo source/field/token. `NULL` là không xác định, không phải 0/false/`Unknown`. |
| Invalid có giá trị hiện diện | Giữ record đọc được trong Staging, typed value có thể `NULL` khi parse bất khả thi nhưng raw token và issue bắt buộc còn. Không gọi parse failure là missing. | `quality_issue` gồm `_batch_id`, source/record ID, `rule_code`, `field`, `raw_value`, `reason`, `severity`, `issue_type=invalid`, thời điểm. Ví dụ: ngày không tồn tại, số âm, flag ngoài 0/1, chuỗi không parse được. |
| Lỗi cấu trúc record/file không đọc được | Không tạo Staging row giả. Ghi `reject` với file, vị trí/offset nếu biết, raw fragment, lý do; lỗi toàn file làm batch `failed`. | Count reject riêng; không cộng vào missing/invalid field hoặc out-of-scope. |
| Ngoài phạm vi Booking | Không nạp hotel khác `City Hotel`; hotel không xác định ghi nhóm riêng. | Count `out_of_scope_hotel` và `unidentified_hotel`, không gọi là invalid business record của City. |

`quality_issue` là bảng/record phụ, **không** phải chỗ chuyển booking thiếu `children` hoặc sai nghiệp vụ ra khỏi Staging. Với `children='NA'`, giữ City record và `children=NULL`; với 0 tổng khách, giữ City record và có thể phát issue `ZERO_GUESTS` theo rule được chốt. Member 2 định nghĩa riêng eligibility/biến đổi từng field cho Staging → DW/KPI, ghi rule và kiểm thử trước khi áp dụng; không đưa rule đó vào loader Staging.

Rule code tối thiểu cho Staging: `DATE_PARSE_FAILED` (ngày hiện diện sai/không tồn tại), `NUMERIC_PARSE_FAILED` (chuỗi số không parse được), `NEGATIVE_GUEST_OR_NIGHT` (giá trị âm), `CANCEL_FLAG_DOMAIN` (khác 0/1), `HOLIDAY_SCOPE_DOMAIN`, `WEATHER_NEGATIVE_PRECIPITATION` — severity `error` nhưng **không xóa record đọc được**. `ZERO_GUESTS` là `warning` cần quyết định downstream. `CSV_ROW_MALFORMED`/`WEATHER_RESPONSE_MALFORMED` là lỗi cấu trúc vào reject hoặc batch `failed`. Mỗi issue lưu raw value, lý do cụ thể, field, source record và batch; missing được đếm theo field/token, không đánh đồng với các code invalid.

## Đối soát và idempotency

Khóa duy nhất của các dòng Staging từ cùng nguồn: `(_source_file_sha256, _source_row_id)` theo từng bảng. `_source_row_id` của Booking là thứ tự record logic trong **raw gốc trước lọc** (header=1, record đầu=2), không đánh lại 1…79.330. Reservation giống hệt 32 thuộc tính vẫn là hai record nếu vị trí khác và chưa có bằng chứng nạp trùng.

Đối soát Booking cho batch hiện tại:

```text
raw_records = staged_city + out_of_scope_hotel + unidentified_hotel + structural_rejects
119,390     = 79,330      + 40,060             + 0                  + 0
```

Các số trên là số đã profile từ file cụ thể, không hard-code làm quy tắc tổng quát. Missing/invalid của City là **nhãn chất lượng có thể chồng lấp**, không trừ khỏi `staged_city`. Đối soát Holiday riêng: `raw_holiday_rows = staged_holiday + structural_rejects` (batch hiện tại 38 = 38 + 0). Đối soát Weather riêng: `daily_entries = staged_weather + structural_rejects` (batch hiện tại 793 = 793 + 0), đồng thời đối chiếu ngày từ 2015-07-01 đến 2017-08-31 và báo ngày/giá trị thiếu. Quality report từng nguồn tách `missing`, `invalid`, `out_of_scope`/`unidentified`, `structural_reject`, coverage và duplicate key.

Baseline triển khai: bảng nguồn giữ row bất biến theo `(file checksum, row ID)`, `staging.load_batch`/`load_batch_source` ghi lần nạp và ba nguồn, `staging.active_snapshot` trỏ một batch `published`. `v_booking_current`, `v_holiday_current`, `v_weather_current` chỉ expose checksum của batch active; `_batch_id` trên row vật lý là batch nạp row lần đầu. Một transaction nạp row mới, issue/counts, đối soát và chuyển active pointer; fatal error rollback transaction đó, ghi batch `failed`/reject riêng, không đổi snapshot đang công bố. Session lock tuần tự hóa các lần nạp và lần chạy kế tiếp đánh dấu attempt `loading` bị ngắt thành `failed`. Cùng source set fingerprint đã published trả `no-op`; version contract/source mới có batch mới nhưng không nhân đôi row cùng checksum. Không xóa dữ liệu nguồn để “sửa” số liệu.

`staging.v_daily_context_current` là projection bàn giao, một dòng cho mỗi `(City Hotel, local_date)` trong khoảng arrival date; nhiều lễ cùng ngày được gộp tên. Ngày không có lễ trả `is_holiday=NULL` ở Staging, chỉ downstream được xác nhận coverage rồi mới suy non-holiday. Weather nhiều record cùng ngày giữ tất cả trong Staging, projection trả Weather `NULL` và `weather_ambiguous=true`; không chọn bản ghi tùy tiện.

## Bằng chứng nghiệm thu trên PostgreSQL

1. DDL thực thi được cho ba bảng Staging, batch/source registry, `quality_issue`, `reject`; các cột typed nullable cùng raw value/payload và unique key đúng grain.
2. Loader thực thi được cho cả ba nguồn; raw checksum khớp manifest; log/provenance đủ để truy ngược một record mẫu tới file và vị trí ban đầu.
3. Query đối soát **riêng từng nguồn** khớp phương trình trên. Query City Hotel chứng minh không có Resort trong `stg_booking`; row ID vẫn là vị trí trước lọc.
4. Test missing (`children='NA'`, `country='NULL'`, Holiday/Weather JSON `null`), invalid (date/number/flag/parse), structural reject và hotel không xác định; chứng minh raw token được giữ, record đọc được vẫn có mặt, issue đủ trường.
5. Test rerun cùng source và batch mới cùng checksum giữ số dòng/KPI; hai reservation giống thuộc tính nhưng khác `_source_row_id` đều được giữ.
6. Test weekday/weekend, holiday độc lập, nhiều lễ một ngày, weather/holiday chưa rõ vẫn `NULL`, và context join không nhân bản hay làm mất booking.
7. Có lệnh chạy từ raw → PostgreSQL, migration/setup, query/report quality, log batch thành công/thất bại và kết quả test có thể tái lập. Chỉ sau đó mới gọi gate **STAGING READY**.

STAGING READY không đòi đã xây DW/Mart; quyết định transform và eligibility downstream của Member 2 là handoff riêng sau gate này.

**Hiện thực và hướng dẫn chạy:** `database/staging/001_staging.sql`, `pipeline/source_to_staging/{common,booking,holiday,weather,run}.py`, `scripts/{setup_db,run_pipeline}.py`, `pipeline/quality/staging_checks.py`, `database/validation/staging_checks.sql` và [runbook](../staging_runbook.md). Source set/checksum cố định cho lần bàn giao tại [operations_source_set.json](../data_dictionary/operations_source_set.json); expected count không áp dụng cho file checksum khác.
