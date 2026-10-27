# Báo cáo triển khai Data Warehouse

## 1. Phạm vi

Data Warehouse phục vụ phân tích vận hành City Hotel theo ngày đến. Mô hình gồm một FactBooking ở grain một reservation record nguồn, sáu dimension và một DailyContext ở grain một ngày. Các bảng kỹ thuật lưu phiên bản nạp, source coverage, chất lượng và lỗi truy vết.

DW đã được nạp và kiểm chứng trên PostgreSQL local. Operations Mart chưa được triển khai. Phạm vi tiếp theo gồm tổng hợp theo ngày và ngày × country trong cùng domain Operations; API, feature dataset và mô hình ML được tích hợp ở giai đoạn sau.

| Tài liệu DW | Chức năng |
|---|---|
| [dw_design.md](dw_design/dw_design.md) | Mô hình, thuộc tính, baseline D01–D08 và tiêu chí nghiệm thu |
| [dw_runbook.md](dw_runbook.md) | Điều kiện môi trường, thứ tự chạy script, kiểm tra và xử lý lỗi |
| Báo cáo này | Quá trình triển khai, quy tắc, danh mục file, kết quả và evidence |

Các tài liệu nguồn, Staging và hợp đồng tích hợp thuộc giai đoạn trước tiếp tục được giữ tại vị trí hiện có.

Trong phạm vi DW, `dw_design.md` quy định mô hình và baseline hiện hành; báo cáo xác định kết quả đã có bằng chứng; runbook mô tả thao tác vận hành. Phần Mart và feature/ML trong thiết kế là yêu cầu cho các giai đoạn sau, không biểu diễn chức năng đã triển khai hoặc điều kiện bổ sung để công nhận DW READY.

## 2. Quá trình triển khai

| Giai đoạn | Công việc và kết quả |
|---|---|
| Tiếp nhận Staging | Xác định published batch, current views, registry, issues và manifest. Phân biệt batch nạp dòng đầu tiên với active batch |
| Chuẩn bị đầu vào | Xây năm mapping có version/hash; xác định calendar, actual range, coverage theo nguồn/scope, NULL/0 và country calendar. Preflight chỉ đọc dữ liệu |
| Booking coverage | Ban đầu giữ UNKNOWN vì count/min/max không chứng minh nguồn đầy đủ. Khi giả định completeness của dataset được chấp nhận, chuyển config sang `dw-inputs-v2`, coverage `selected-coverage-v2`; ngoài phạm vi chấp nhận vẫn UNKNOWN |
| Migration | Tạo ba migration theo thứ tự control → dimensions → fact/context/quality; kiểm chứng ledger/checksum, constraints, transaction và chạy lại |
| Transformer | Xây hàm thuần kiểm tra raw/typed/issues, core acceptance/rejection, numeric, eligibility, mapping, profile, party và room comparison |
| Snapshot và loader | Đọc nhất quán published Staging; dựng/nạp đủ dimension, fact, context, coverage và daily quality; kiểm tra trước atomic publish |
| Nghiệm thu | Nạp source thật, đối soát độc lập, chạy PostgreSQL tests, kiểm tra no-op, rollback, recovery và concurrency; lưu evidence từng giai đoạn |
| Điều phối bằng một lệnh | `scripts/run_dw.py` gọi các CLI theo thứ tự, dừng khi lỗi, lưu report chung và xác nhận load/quality/rerun cùng phiên bản; tùy chọn chạy bộ test |

Chuẩn bị đầu vào có evidence 36 test cases. Migration được kiểm chứng riêng bằng 50 PostgreSQL cases. Transformer có 107 unit cases. Bộ nghiệm thu loader DW gốc có 223 tests. Khi bổ sung runner, có thêm 13 cases điều phối và một case PostgreSQL, tổng bộ hiện hành là 237 tests; không cộng số test các lần chạy vì có cases được chạy nhiều lần.

## 3. Đầu vào và source lineage

DW loader đọc `staging.v_booking_current`, `staging.v_holiday_current`, `staging.v_weather_current` cùng registry/issues của một published snapshot. Source selection theo [operations_source_set.json](data_dictionary/operations_source_set.json); field và missing/invalid semantics theo [dictionary nguồn](data_dictionary/operations_sources.md) và [contract Staging](etl_spec/operations_source_to_target.md).

| Nguồn | File raw trong manifest | Published Staging |
|---|---|---|
| Booking | [hotel_bookings.csv](../data/raw/booking/mathsian_hotel-bookings_20261017/hotel_bookings.csv) | 79.330 reservation City Hotel |
| Holiday | [Lịch PT/Lisboa](../data/raw/holiday/pt_lisboa_holidays_2015_2017_20261017.csv) | 38 records |
| Weather | [ERA5 Lisbon](../data/raw/weather/open_meteo_lisbon_era5_2015-07-01_2017-08-31_20261027.json) | 793 records ngày |

Raw và acquisition metadata được giữ bất biến; manifest chứa checksum và đường dẫn metadata. Raw thường bị Git-ignore nên phải chuyển giao riêng đúng checksum. DW không trừ lại Resort vì Staging đã xử lý phạm vi City Hotel.

Booking source key là checksum file + source row ID. Row ID là ordinal trong CSV gốc trước lọc, header=1 và data đầu=2. Hai reservation giống thuộc tính nhưng khác source key vẫn là hai record. `source_first_batch_id` theo batch nạp dòng vật lý đầu tiên; `staging_batch_id` của DW run theo published snapshot đang dùng.

### 3.1. Mapping

Mapping chuyển token nguồn sang mã chuẩn và nhãn dimension. Đây là quy tắc chuẩn hóa có version, không phải bước gộp hoặc loại reservation.

| Trường hợp | Quy tắc |
|---|---|
| Country `CN` / `TMP` | Chuẩn hóa thành `CHN` / `TLS`, giữ country raw trên fact |
| Country missing | Dùng `UNK` và unknown key; giữ guest hợp lệ |
| Channel/segment `Undefined` | Dùng `UNKNOWN`, không tự gán `Other` |
| Code mới chưa có mapping | Preflight báo unmapped để kiểm tra; transformer giữ unknown và issue theo contract |
| Customer type/repeat biết một phần | Giữ tổ hợp biết một phần; chỉ cả hai unknown mới dùng full-unknown profile |
| Room reserved/assigned | Dùng chung namespace mã ẩn danh; dimension lấy hợp hai vai trò, gồm mã chỉ có ở assigned |
| Tên/hạng phòng | Không suy từ mã; nhãn không có căn cứ giữ NULL |

Country labels dùng [bản tham chiếu có checksum](../artifacts/dw/operations/input_preparation_20261027/references/references.json). ETL không tự tải dictionary mới khi chạy. Căn cứ room namespace và alias country được ghi trong [coverage assessment](../artifacts/dw/operations/input_preparation_20261027/coverage_assessment.json).

<a id="coverage-calendar"></a>

## 4. Coverage và calendar

| Nguồn/scope | Khoảng khai báo | Căn cứ và giới hạn |
|---|---|---|
| Booking | 01/07/2015–31/08/2017 | COMPLETE theo giả định dataset đầy đủ đã được chấp nhận; chỉ City Hotel và đúng checksum |
| Holiday national | 01/01/2015–31/12/2017 | COMPLETE cho lịch public của generator đã chọn, `observed=false`; replay khớp CSV |
| Holiday Lisboa | 01/01/2015–31/12/2017 | Cùng căn cứ generator, giữ scope riêng với national |
| Weather | 01/07/2015–31/08/2017 | COMPLETE cho series ERA5 được chọn; vẫn kiểm tra từng ngày/measure |
| Ngoài khoảng khai báo | Theo calendar | UNKNOWN |

Giả định Booking được ghi tại [decision.json](../artifacts/dw/operations/booking_coverage_accepted_20261027/decision.json), gắn checksum `7c2ae42a7353905ea136e5c2287f17c92c5435826598bfbb8491c6f0c7b1fc06`. Đây là giả định sử dụng dataset, không phải bằng chứng độc lập về capture PMS. Checksum mới phải được đánh giá lại. Coverage nguồn không miễn validation hoặc làm measure lỗi trở thành hợp lệ.

Calendar có 800 ngày liên tục từ 01/07/2015 đến 07/09/2017. Khoảng actual có 793 ngày đến 31/08/2017; bảy ngày sau dành cho horizon, không được coi là actual. Booking/Weather ở bảy ngày này giữ UNKNOWN; Holiday vẫn trong coverage của lịch đã sinh.

Evidence v1 giữ Booking UNKNOWN để thể hiện trạng thái trước khi áp dụng giả định. Config/coverage v2 và quyết định chấp nhận là căn cứ hiện hành; report lịch sử không biểu diễn trạng thái đang phục vụ.

## 5. Migration và cấu trúc database

Ba SQL migration tạo 15 bảng trong schema `dw`:

| Nhóm | Bảng và mục đích |
|---|---|
| Dimensions | `dim_date`, `dim_country`, `dim_channel`, `dim_market_segment`, `dim_customer_profile`, `dim_room_type` |
| Fact | `fact_booking`: một reservation nguồn; bảy FK do room có hai vai trò reserved/assigned |
| Context | `daily_hotel_context`: Holiday/Weather theo ngày |
| Daily quality | `daily_data_quality`: technical counts, completeness và reason codes |
| Điều khiển | `schema_migration`, `load_run`, `active_dataset` |
| Truy vết | `source_coverage`, `row_issue`, `booking_rejection` |

Dimension có natural uniqueness, unknown member và constraints phù hợp. CustomerProfile biểu diễn tổ hợp thuộc tính, không phải định danh cá nhân. ADR dùng NUMERIC; biến đổi cần precision dùng Decimal. PK/FK/CHECK/index và trigger bảo vệ lineage/publication được kiểm chứng bằng PostgreSQL thật.

Migration runner dùng checksum ledger, writer lock và transaction atomic. SQL đã áp dụng phải giữ nguyên; chạy lại đúng version/hash là no-op. Migration tạo cấu trúc; loader nạp dữ liệu fact/context.

## 6. Transformer Booking

Interface: `transform_booking(row, config, mappings, staging_issues=()) -> BookingTransformResult`.

Hàm nhận một row Staging cùng raw record, lineage và issues của đúng source key; không kết nối DB, ghi file hoặc sửa input. Kết quả gồm `fact`, `rejection`, `issues`, `block_publish`; mỗi row có đúng một trong `fact` hoặc `rejection`. Candidate chưa có surrogate booking key/run metadata; loader tra FK và bổ sung metadata khi nạp.

| Điều kiện | Xử lý |
|---|---|
| Ngày đến không xác định | Rejection và block publish |
| Ngày hợp lệ ngoài calendar | Lỗi config; không đổi thành rejection để bỏ dòng |
| Cancellation invalid | Core rejection; lỗi có ngày xác định ảnh hưởng daily quality |
| Guest missing/invalid/âm/phân số/overflow | Giữ booking core hợp lệ; vô hiệu measure tương ứng và ghi issue |
| Guest tổng bằng 0 | Giữ 0 và warning ZERO_GUESTS; guest-ineligible |
| Nights bằng 0 | Stay-eligible, giữ warning ZERO_STAY_NIGHTS |
| Nights/lead time/ADR lỗi | Vô hiệu measure tương ứng, không loại booking chỉ vì measure lỗi |
| ADR bằng 0 | Hợp lệ, giữ precision |
| Party type | FAMILY khi có children/babies; SINGLE/COUPLE theo adults; OTHER_GROUP cho nhóm còn lại; UNKNOWN khi guest-ineligible |
| Room comparison | So sánh khi cả hai mã đủ điều kiện; thiếu một bên giữ NULL, không suy upgrade hoặc chuyển phòng |

Raw/typed values và issues được đối chiếu trước khi sử dụng. Không phục hồi typed NULL từ raw hoặc dùng `int()` để cắt phần thập phân invalid. Missing tokens xử lý theo field, không dùng quy tắc NA/NULL toàn cục.

### 6.1. Ảnh hưởng D01/D02

- Có 4 booking thiếu children, đều đã hủy. Giữ booking/issue; riêng lỗi này không làm thiếu demand khách không hủy.
- Có 167 ZERO_GUESTS, gồm 144 booking không hủy thuộc 114 ngày. Giữ booking; không impute hoặc gán nguyên nhân nhập liệu khi chưa có căn cứ.
- Actual có 679 ngày guest COMPLETE và 114 PARTIAL. Booking coverage COMPLETE không làm 114 ngày này trở thành COMPLETE.

Các con số thuộc source version hiện hành, phải tính lại khi đổi source/rule. Booking hủy vẫn phục vụ count/cancellation nhưng không góp guest demand không hủy.

## 7. Snapshot, loader và publish

1. Validate config, mapping và coverage hashes.
2. Lấy shared session advisory lock cùng Staging writer trước khi pin input; không giữ snapshot transaction cũ khi chờ lock.
3. Kiểm tra migration ledger, phục hồi attempt loading bị ngắt, pin published Staging header và tính build fingerprint.
4. Active DW cùng fingerprint trả no-op. Nếu cần nạp mới, ghi loading run/data version ở transaction ngắn.
5. Mở REPEATABLE READ, đọc current views/registry/issues nhất quán; dựng candidates, dimensions, context và quality.
6. Đối soát source key, fact/rejection và điều kiện chặn trước khi thay dữ liệu phục vụ.
7. DELETE bảng con trước cha, INSERT dimensions trước fact/context/quality trong cùng transaction; ghi audit.
8. Chạy SQL/Python checks; chỉ khi đạt mới mark run published, đổi active pointer và commit.

Lỗi trước commit rollback dữ liệu; failed run/audit được ghi bằng transaction riêng. MVCC readers thấy snapshot cũ đến commit. Lịch sử run/issues/rejections/coverage được giữ; fact/dim/context phục vụ một active snapshot.

Fingerprint gồm pinned Staging batch, source-set fingerprint, config/manifest và hashes runtime code, SQL checks, DDL. Mapping/coverage hashes được pin qua config. Run ID, thời điểm chạy, output folder và credential không tham gia fingerprint. Full refresh có thể cấp surrogate keys mới; dùng source keys/natural codes để đối chiếu qua các lần chạy.

### 7.1. DailyContext và quality

Holiday được tổng hợp theo ngày/scope trước join, giữ national, Lisboa và cờ OR ba giá trị. Không có record chỉ trở thành false khi scope có coverage COMPLETE và không bị issue che khuất. Invalid date không định vị được có thể làm scope chưa xác định trên calendar.

Weather trùng ngày được đánh dấu AMBIGUOUS, hai measure giữ NULL. Ngày có một record được kiểm tra từng field; thiếu mưa không thành 0, nhiệt độ âm có thể hợp lệ, NaN/Infinity và mưa âm không hợp lệ.

Daily quality có đủ calendar, gồm ngày không booking. Technical counts bằng 0 không chứng nhận demand bằng 0 khi coverage chưa đủ. Defect ở booking không hủy làm measure tương ứng PARTIAL; unknown categorical dimension không tự làm mất guest hợp lệ.

<a id="null-zero"></a>

## 8. Quy tắc tổng hợp cho Operations Mart

Đây là hợp đồng cho bước Mart; SQL/refresh Mart chưa được triển khai.

A là accepted facts trong nhóm ngày/country; B là A không hủy; G/S/L/R lần lượt là B đủ điều kiện guest/stay/lead time/ADR. Mỗi sum/valid count dùng đúng tập tương ứng. Roll-up cộng sum/count rồi tính lại average/rate, không lấy trung bình các average.

| Tình huống | Quy tắc |
|---|---|
| Có accepted rows | Giữ observed counts/sums từ tập hợp lệ, kèm quality |
| Còn booking không hủy nhưng measure không có giá trị hợp lệ | Sum NULL, valid count kỹ thuật bằng 0, average NULL |
| Không có booking không hủy; source COMPLETE, không core rejection | Các sum phù hợp bằng 0; average NULL |
| Không có fact; source COMPLETE, không core rejection | Booking/cancellation counts bằng 0; cancellation rate NULL do mẫu số 0 |
| Không có fact; coverage chưa đủ hoặc có core rejection | Serving counts/sums NULL; observed technical counts có thể bằng 0 |
| Có guest hợp lệ và guest-ineligible | Giữ subtotal quan sát; guest PARTIAL, target NULL |
| Mẫu số bằng 0 | Average/rate NULL |

`avg_party_size=sum_guest/count(G)`; stay/lead/ADR dùng S/L/R. Guest component sums cùng dùng G để cộng khớp total. Target chỉ có giá trị khi guest COMPLETE. Không âm thầm bỏ ngày thiếu khỏi mẫu số ngày.

<a id="country-calendar"></a>

### 8.1. Country calendar

Mart country dùng actual dates × countries của accepted candidates + UNK, sau đó LEFT JOIN aggregate fact. Không thêm toàn bộ danh mục thế giới hoặc code chỉ có ở core-rejected rows.

Country filter giữ nguyên số ngày lịch. Ngày source COMPLETE và không core rejection cho phép ô country rỗng có count/sum phù hợp bằng 0; ngày có core rejection giữ NULL ở ô rỗng. Quality/counters cấp ngày tiếp tục đi cùng mỗi country; không SUM lại counters/context bị lặp. Guest PARTIAL cấp ngày không đổi thành target COMPLETE chỉ bằng country filter.

## 9. Danh mục file hiện thực

### 9.1. Python và CLI

| File | Trách nhiệm |
|---|---|
| [config.py](../pipeline/staging_to_dw/config.py) | Validate config, mapping, hashes và coverage |
| [preflight.py](../pipeline/staging_to_dw/preflight.py) | Profile và kiểm tra đầu vào chỉ đọc |
| [migrations.py](../pipeline/staging_to_dw/migrations.py) | Migration ledger/checksum/transaction |
| [snapshot.py](../pipeline/staging_to_dw/snapshot.py) | Pin/read published Staging, registry và issues |
| [transform.py](../pipeline/staging_to_dw/transform.py) | Acceptance/rejection, eligibility và canonical codes |
| [dimensions.py](../pipeline/staging_to_dw/dimensions.py) | Dựng/nạp sáu dimension, trả lookup |
| [facts.py](../pipeline/staging_to_dw/facts.py) | Map bảy FK, insert fact và audit |
| [context.py](../pipeline/staging_to_dw/context.py) | Daily Holiday/Weather context |
| [quality.py](../pipeline/staging_to_dw/quality.py) | Source coverage và daily quality |
| [checks.py](../pipeline/staging_to_dw/checks.py) | Đối soát candidate và dữ liệu đã nạp |
| [run.py](../pipeline/staging_to_dw/run.py) | Lock, lifecycle, fingerprint, refresh và publish |
| [dw_checks.py](../pipeline/quality/dw_checks.py) | Quality CLI chỉ đọc |
| [check_dw_inputs.py](../scripts/check_dw_inputs.py) | Preflight CLI và report |
| [setup_db.py](../scripts/setup_db.py) | Migration CLI `--schema dw`, dùng chung với Staging |
| [run_pipeline.py](../scripts/run_pipeline.py) | Pipeline CLI `--to dw`, dùng chung với Staging |
| [run_dw.py](../scripts/run_dw.py) | Chạy preflight/migration/load/quality/rerun bằng một lệnh; tùy chọn tests |

Tái sử dụng [common.py](../pipeline/source_to_staging/common.py) cho kết nối/config/source helpers và [booking.py](../pipeline/source_to_staging/booking.py) cho fields/tháng. Không thêm pandas, ORM hoặc dependency điều phối.

### 9.2. SQL, config và mapping

| File | Trách nhiệm |
|---|---|
| [001_control.sql](../database/dw/001_control.sql) | Schema và sáu bảng kỹ thuật |
| [002_dimensions.sql](../database/dw/002_dimensions.sql) | Sáu dimension, constraints và unknown members |
| [003_fact_context_quality.sql](../database/dw/003_fact_context_quality.sql) | Fact, context, quality và lineage |
| [dw_checks.sql](../database/validation/dw_checks.sql) | SQL đối soát, được quality CLI bind tham số |
| [dw_operations.json](../pipeline/config/dw_operations.json) | Config `dw-inputs-v2`, calendar/actual, asset versions/hashes |
| [coverage_selected_source_set.json](../pipeline/config/coverage_selected_source_set.json) | Coverage `selected-coverage-v2`, source checksums và evidence |
| [country_codes.csv](../pipeline/mappings/country_codes.csv) | Country aliases/labels/unknown |
| [channel_codes.csv](../pipeline/mappings/channel_codes.csv) | Channel mapping |
| [market_segment_codes.csv](../pipeline/mappings/market_segment_codes.csv) | Segment mapping |
| [customer_type_codes.csv](../pipeline/mappings/customer_type_codes.csv) | Customer type mapping |
| [room_type_codes.csv](../pipeline/mappings/room_type_codes.csv) | Shared room namespace mapping |

### 9.3. Tests và fixture

| File | Nội dung | Cases trong bộ cuối |
|---|---|---:|
| [test_dw_inputs.py](../tests/pipeline/test_dw_inputs.py) | Config/mapping/coverage, expectations và CLI errors | 31 |
| [test_dw_inputs_postgres.py](../tests/pipeline/test_dw_inputs_postgres.py) | Snapshot/first-batch và preflight PostgreSQL | 1 |
| [test_dw_migrations_postgres.py](../tests/pipeline/test_dw_migrations_postgres.py) | Migration, constraints, ledger/transaction | 50 |
| [test_dw_transform.py](../tests/pipeline/test_dw_transform.py) | Transformer expected values | 107 |
| [test_dw_context.py](../tests/pipeline/test_dw_context.py) | Holiday, Weather, ISO calendar và quality | 13 |
| [test_dw_postgres.py](../tests/pipeline/test_dw_postgres.py) | Load, no-op, rollback, recovery, MVCC, competing writers và runner PostgreSQL | 17 |
| [test_dw_cli.py](../tests/pipeline/test_dw_cli.py) | Runner: thứ tự, dừng khi lỗi, version mismatch, output tồn tại, tùy chọn tests và interruption | 13 |
| [operations_expected.json](../tests/fixtures/dw/operations_expected.json) | Fixture tính tay; có expected country cho bước Mart | — |

Có thêm 5 Staging regression tests trong bộ pipeline, tổng cộng 237. Integration dùng database test riêng; SQLite không thay thế kiểm chứng PostgreSQL. File `pytest_final.xml` của bộ nghiệm thu loader gốc giữ nguyên 223 cases; kết quả bộ hiện hành nằm trong evidence runner.

<a id="results"></a>

## 10. Kết quả nghiệm thu DW

| Nội dung | Kết quả |
|---|---|
| Trạng thái | DW READY trên local |
| Staging batch | `735da72d-5c48-4690-984c-13b5c44b9325` |
| DW run | `4481d8b1-a6c7-451d-87a6-057d8273e7b2` |
| Data version | `b49e51b6-ac15-4227-8b82-77d465e4cc93` |
| Source-set fingerprint | `5d2b572acc4a467e19028ab43902686d826538f819d072e5b1971345e577a339` |
| FactBooking | 79.330 unique source keys; 0 rejection |
| DimDate | 800 |
| Country / Channel / Segment / Profile / Room | 166 / 5 / 8 / 9 / 10, gồm unknown |
| DailyContext / daily quality | 800 / 800 |
| Booking không hủy / hủy | 46.228 / 33.102 |
| DW issues | 532 issue rows; không cộng thêm vào fact/rejection reconciliation |
| Actual guest quality | 679 COMPLETE + 114 PARTIAL |
| Observed eligible guests không hủy | 89.456; subtotal quan sát đi cùng daily quality |
| Observed eligible nights không hủy | 135.153 |
| Tổng ADR hợp lệ không hủy | 4.888.423,70; giá trị đối soát, không phải doanh thu |
| Kiểm tra độc lập | 36 checks đạt, violation counts bằng 0 |
| Bộ test pipeline hiện hành | 237 passed; 0 failed/error/skipped; bộ nghiệm thu loader gốc giữ 223 cases |
| Chạy lại cùng input | No-op, cùng run/data version |
| Staging trước/sau | Snapshot, registry, issues, counts và quality không đổi |

Các kiểm tra bao gồm source keys hai chiều, fact/rejection disjoint, exact dimension/calendar sets, labels/FK assignments, raw source measures, context, coverage và quality. PostgreSQL tests có fault injection ở bảy phase, interrupted recovery, first-batch khác active, historical fingerprint, MVCC reader, competing writers và lỗi ghi report sau commit.

Số liệu gắn source/run đã ghi nhận, không phải hằng số thuật toán. DW READY xác nhận pipeline đúng contract; không chứng nhận mọi measure/day COMPLETE hoặc Operations Mart đã có dữ liệu.

<a id="evidence"></a>

## 11. Evidence và khả năng tái lập

### 11.1. Nghiệm thu loader DW gốc

| File | Mục đích |
|---|---|
| [first_load.json](../artifacts/dw/operations/loader_20261027/first_load.json) | Publication, input versions và số liệu nạp |
| [quality_report.json](../artifacts/dw/operations/loader_20261027/quality_report.json) | 36 checks, totals và statuses |
| [rerun.json](../artifacts/dw/operations/loader_20261027/rerun.json) | No-op cùng active version |
| [inspection_before.json](../artifacts/dw/operations/loader_20261027/inspection_before.json) / [inspection_after.json](../artifacts/dw/operations/loader_20261027/inspection_after.json) | Đối chiếu trạng thái Staging/DW trước-sau |
| [pytest_final.xml](../artifacts/dw/operations/loader_20261027/pytest_final.xml) | 223 tests passed |
| [verification.json](../artifacts/dw/operations/loader_20261027/verification.json) | Gate, evidence hashes và runtime hashes |

### 11.2. Đầu vào coverage và ví dụ cần giữ

| Nhóm | Evidence được giữ |
|---|---|
| Căn cứ coverage và mapping | [assessment](../artifacts/dw/operations/input_preparation_20261027/coverage_assessment.json), [reference metadata](../artifacts/dw/operations/input_preparation_20261027/references/references.json), [country dictionary](../artifacts/dw/operations/input_preparation_20261027/references/iso3166-1.json) |
| Booking completeness và cấu hình trước thay đổi | [decision](../artifacts/dw/operations/booking_coverage_accepted_20261027/decision.json), [config_before.json](../artifacts/dw/operations/booking_coverage_accepted_20261027/config_before.json), [coverage_before.json](../artifacts/dw/operations/booking_coverage_accepted_20261027/coverage_before.json) |
| Ví dụ transformer | [examples.json](../artifacts/dw/operations/transform_booking_20261027/examples.json): input/output synthetic để đối chiếu cách xử lý từng row |

Evidence có checksum hoặc được verification cuối tham chiếu giữ nguyên nội dung/vị trí. Coverage v2 tham chiếu decision và assessment v1 bằng hash; xóa hoặc di chuyển các file này làm config không hợp lệ.

Bộ artifact nghiệm thu loader DW được giữ gồm 14 file: bảy evidence ở mục 11.1 và bảy file trong bảng trên. Các report preflight cũ, XML/verification của từng bước và bản sao config/coverage sau thay đổi đã được loại bỏ. Bộ 223 tests gốc được giữ bất biến; evidence kiểm chứng runner được lưu ở thư mục run riêng. Quá trình triển khai tại mục 2, cấu hình hiện hành tại `pipeline/config`.

`config_before.json` và `coverage_before.json` là cặp bản chụp cấu hình trước khi áp dụng Booking completeness. Đường dẫn coverage trong config lịch sử vẫn trỏ vị trí cấu hình dùng chung; checksum lịch sử được đối chiếu với `coverage_before.json`, không với coverage v2 đang hoạt động. Các bản chụp phục vụ truy vết, không dùng trực tiếp làm config vận hành hiện tại.

### 11.3. Kiểm chứng điều phối bằng một lệnh

Lệnh `scripts/run_dw.py --with-tests` đã hoàn thành trên PostgreSQL local. Preflight/migration/load/quality/rerun/tests đều có mã thoát `0`; load và rerun là no-op, giữ nguyên DW run/data version ở mục 10. Bộ pipeline đạt 237 tests; quality có 36 checks đạt.

| File | Nội dung |
|---|---|
| [summary.json](../artifacts/dw/operations/runner_faaf32a5/summary.json) | Sáu bước hoàn tất, version nhất quán và tests đã chạy |
| [preflight.json](../artifacts/dw/operations/runner_faaf32a5/inputs/preflight.json) | Published Staging và đầu vào hợp lệ |
| [migration.json](../artifacts/dw/operations/runner_faaf32a5/migration.json) | Migration no-op |
| [first_load.json](../artifacts/dw/operations/runner_faaf32a5/first_load.json) | Load no-op với dữ liệu đang phục vụ |
| [quality_report.json](../artifacts/dw/operations/runner_faaf32a5/quality_report.json) | Quality độc lập của cùng DW version |
| [rerun.json](../artifacts/dw/operations/runner_faaf32a5/rerun.json) | No-op, counts và version giữ nguyên |
| [pytest.xml](../artifacts/dw/operations/runner_faaf32a5/pytest.xml) | 237 passed, không failed/error/skipped |

## 12. Vận hành và thay đổi dữ liệu

Thực hiện theo [dw_runbook.md](dw_runbook.md). Lệnh `scripts/run_dw.py` tự chạy preflight → migration → load → quality độc lập → rerun; `--with-tests` bổ sung bộ kiểm thử sau khi đối soát đạt. Các CLI riêng vẫn dùng để xử lý từng bước. Runner điều phối tiến trình bằng Python đang sử dụng, không thay đổi ETL hoặc transaction của các bước bên trong.

Runner lưu `summary.json`, từ chối thư mục output đã tồn tại và dừng ở lỗi đầu tiên. Nếu một writer khác thay active dataset giữa load/quality/rerun, đối chiếu version hoặc counts không đạt và runner trả lỗi. Dừng luồng không rollback các publication đã commit; trạng thái luồng và trạng thái active DW được phân biệt.

Khi đổi source, kiểm tra dữ liệu/metadata thật, cập nhật source selection theo contract Staging, đánh giá lại mapping/coverage/expected counts. Không chuyển giả định Booking đầy đủ sang checksum mới. Sau published Staging mới, chạy preflight rồi chuỗi lệnh DW; lưu evidence ở thư mục mới.

Khi đổi rule/mapping/config/runtime, ghi version/hash phù hợp và chạy test liên quan trước khi nạp. Không sửa SQL migration đã áp dụng hoặc thay checksum để vượt kiểm tra. Quality CLI dùng đúng cấu hình của run đang đối soát.

### 12.1. Tổ chức tài liệu và file phụ trợ

Nội dung đầu vào, migration, transformer và nghiệm thu được tổng hợp trong báo cáo này. Các ghi chú riêng `input_readiness.md`, `migration.md`, `booking_transform.md`, `progress_checklist.md`, hướng dẫn DW cũ và review trung gian được loại khỏi bộ tài liệu DW.

XML thử nghiệm, report từng bước đã được bộ nghiệm thu cuối bao phủ, preflight bị thay thế và helper tạo asset v1/ghi evidence dùng một lần được loại bỏ. Giữ runtime, fixtures, mapping/config, bộ nghiệm thu DW cuối, ví dụ transformer và dependency coverage. Tài liệu giai đoạn trước chỉ cập nhật liên kết cần thiết.

Việc tổ chức lại tài liệu và artifact loại bỏ tổng cộng 47 file: sáu tài liệu DW trung gian, 38 artifact/helper bị thay thế và ba placeholder; dọn 11 thư mục rỗng và 12 thư mục pytest tạm của DW. Riêng lần rà soát artifact bổ sung loại bỏ 19 file và bốn thư mục rỗng, giảm từ 33 còn 14 artifact DW. Kiểm tra liên kết, config/coverage và checksum runtime/evidence cuối đạt. Không thay đổi thuật toán, SQL migration, dữ liệu nguồn hoặc database; kết quả 223 tests là evidence của bộ runtime đã nghiệm thu, không phải lần chạy test mới cho thay đổi tài liệu.

## 13. Operations Mart

Triển khai `mart.daily_hotel_operations` và `mart.daily_hotel_operations_by_country` theo thiết kế/mục 8. Aggregate fact trước khi join context; kiểm tra không nhân/mất booking và roll-up từ sum/count.

Refresh/validation Mart phải cùng transaction và `data_version` với DW trước khi phục vụ. Loader hiện ngăn rebuild DW khi đối tượng Mart phục vụ đã tồn tại mà chưa tích hợp refresh đồng bộ. Nghiệm thu Mart cần PostgreSQL tests, đối soát ngày/country, rollback, rerun và evidence riêng.

Ngưỡng model, split hoặc feature window của mẫu ML không chặn nghiệm thu DW/Mart. API/ML contract được liên kết sau khi đầu ra Mart đã hiện thực.
