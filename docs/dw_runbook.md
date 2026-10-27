# Hướng dẫn vận hành Staging → DW → Operations Mart

## 1. Phạm vi

Pipeline nạp City Hotel từ published Staging vào sáu dimension, FactBooking, DailyContext và các bảng chất lượng, truy vết DW. Operations Mart gồm hai bảng tổng hợp lưu sẵn theo ngày và ngày × country. Thiết kế tại [dw_design.md](dw_design/dw_design.md); quá trình triển khai, danh mục file và kết quả tại [dw_report.md](dw_report.md). Hướng dẫn Mart tại mục 9; chưa triển khai OLAP/Reporting/API/ML.

## 2. Chuẩn bị

- Chạy lệnh từ thư mục gốc repository trong PowerShell, dùng Python 3.12 và `.venv` của dự án.
- PostgreSQL đang hoạt động. `.env` hoặc environment có `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`; không ghi credential vào config/report.
- Staging có published snapshot hợp lệ theo [staging_runbook.md](staging_runbook.md). DW đọc current views, registry và issues của snapshot này.
- Giữ đủ raw files và acquisition metadata theo [manifest nguồn](data_dictionary/operations_source_set.json). Preflight kiểm tra file nguồn; loader dùng registry và dữ liệu đã publish trong Staging.
- Giữ config, mappings và coverage evidence đi kèm repository. Đổi source checksum phải đánh giá lại coverage và expected counts trước khi nạp.

Nếu chưa có môi trường Python:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r pipeline/requirements.txt -r pipeline/requirements-dev.txt
```

Nếu sử dụng PostgreSQL qua Docker Compose:

```powershell
docker compose up -d db
```

Không chạy lại Source → Staging khi snapshot đầu vào đã được kiểm chứng và không thay đổi.

## 3. Nạp và kiểm tra DW

### Chạy bằng một lệnh

```powershell
.\.venv\Scripts\python.exe scripts/run_dw.py
```

Lệnh tự thực hiện preflight → migration → load → quality độc lập → rerun. Mỗi bước chạy tuần tự và tự chuyển sang bước tiếp theo khi thành công. Bước lỗi làm luồng dừng, CLI trả mã khác `0` và ghi tên bước lỗi trong `summary.json`.

Khi cần chạy cả bộ test để nghiệm thu:

```powershell
.\.venv\Scripts\python.exe scripts/run_dw.py --with-tests
```

Script tự tạo thư mục `artifacts/dw/operations/run_<id>` mới và in đường dẫn kết quả. Nhận `--output-dir` nếu cần chọn thư mục chưa tồn tại; `--config` và `--dbname` được truyền cho các CLI DW tương ứng. Bộ test dùng database fixture riêng và cấu hình kết nối từ environment.

Runner xác nhận load, quality và rerun có cùng run/data version, số dòng không đổi và rerun là no-op. Các CLI giữ transaction riêng; nếu bước sau thất bại, việc dừng luồng không hoàn tác migration hoặc publication đã commit ở bước trước. Không có transaction chung bao quanh toàn bộ chuỗi lệnh.

### Chạy từng bước

Các lệnh riêng dưới đây dùng khi cần kiểm tra một bước cụ thể. Chỉ tiếp tục khi lệnh trước thành công; mã thoát khác `0` yêu cầu xử lý lỗi trước bước tiếp theo.

#### Bước 1. Chọn thư mục report mới

```powershell
$dwEvidence = Join-Path 'artifacts/dw/operations' ('run_' + [guid]::NewGuid().ToString('N'))
```

Dùng `$dwEvidence` cho các lệnh tiếp theo trong cùng phiên PowerShell. Script tự tạo thư mục khi ghi report; file report đã tồn tại sẽ bị từ chối.

#### Bước 2. Áp dụng migration

```powershell
.\.venv\Scripts\python.exe scripts/setup_db.py --schema dw --report (Join-Path $dwEvidence 'migration.json')
```

Kết quả: schema `dw` có đủ bảng/ràng buộc; ledger ghi version và checksum. Migration đã áp dụng đúng nội dung được bỏ qua khi chạy lại.

#### Bước 3. Nạp published Staging vào DW

```powershell
.\.venv\Scripts\python.exe scripts/run_pipeline.py --to dw --report (Join-Path $dwEvidence 'first_load.json')
```

Mặc định dùng [dw_operations.json](../pipeline/config/dw_operations.json). `status=published` nghĩa là đã tạo phiên bản mới; `status=no-op` nghĩa là active DW đã dùng cùng fingerprint. Cả hai là kết quả hợp lệ. Phiên bản mới chỉ được publish khi các kiểm tra trong transaction đạt.

#### Bước 4. Kiểm tra quality độc lập

```powershell
.\.venv\Scripts\python.exe pipeline/quality/dw_checks.py --report (Join-Path $dwEvidence 'quality_report.json')
```

Yêu cầu `passed=true`, `errors=[]`, violation counts bằng `0`. CLI chỉ đọc và đối soát DW với source version của published run.

#### Bước 5. Kiểm tra chạy lại

```powershell
.\.venv\Scripts\python.exe scripts/run_pipeline.py --to dw --report (Join-Path $dwEvidence 'rerun.json')
```

Nếu source/config/mappings/runtime code không đổi, yêu cầu `status=no-op`, cùng `run_id` và `data_version` với bước 3, số dòng không tăng.

Các CLI nhận `--dbname` để chọn database khác. Lệnh nạp và quality nhận `--config`; phải dùng cùng cấu hình cho một bộ kiểm chứng. Đích DW chọn manifest qua config; `--manifest` của pipeline dành cho Staging.

## 4. Kiểm tra đầu vào khi thay source hoặc cấu hình

```powershell
.\.venv\Scripts\python.exe scripts/check_dw_inputs.py
```

CLI tự tạo thư mục evidence mới và in đường dẫn `preflight.json`. Có thể truyền `--output-dir` để chọn thư mục chưa tồn tại, `--config` và `--dbname` khi cần.

`passed=true` chỉ chứng nhận kiểm tra đầu vào. Preflight không nạp DW và luôn giữ `dw_ready=false`; nghiệm thu dựa trên load, quality, rerun và kiểm thử PostgreSQL.

## 5. Kiểm tra trong PostgreSQL

Chạy các truy vấn trong cùng transaction chỉ đọc để trạng thái active run và các số đếm thuộc cùng snapshot:

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;

SELECT r.run_id, r.data_version, r.status, r.staging_batch_id, r.row_counts
FROM dw.active_dataset AS a
JOIN dw.load_run AS r ON r.run_id = a.run_id
WHERE a.singleton_id = 1;

SELECT 'fact_booking' AS table_name, count(*) AS row_count FROM dw.fact_booking
UNION ALL SELECT 'dim_date', count(*) FROM dw.dim_date
UNION ALL SELECT 'dim_country', count(*) FROM dw.dim_country
UNION ALL SELECT 'dim_channel', count(*) FROM dw.dim_channel
UNION ALL SELECT 'dim_market_segment', count(*) FROM dw.dim_market_segment
UNION ALL SELECT 'dim_customer_profile', count(*) FROM dw.dim_customer_profile
UNION ALL SELECT 'dim_room_type', count(*) FROM dw.dim_room_type
UNION ALL SELECT 'daily_hotel_context', count(*) FROM dw.daily_hotel_context
UNION ALL SELECT 'daily_data_quality', count(*) FROM dw.daily_data_quality;

COMMIT;
```

Đối chiếu report của đúng run. Số liệu nghiệm thu hiện có nằm tại [kết quả DW](dw_report.md#results). Bộ [dw_checks.sql](../database/validation/dw_checks.sql) cần tham số run/coverage; dùng quality CLI để thực thi toàn bộ.

## 6. Kiểm thử

```powershell
$dwTestTemp = Join-Path 'artifacts/tests' ('dw_' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m pytest -q tests/pipeline --basetemp "$dwTestTemp" --tb=short --junitxml (Join-Path $dwEvidence 'pytest.xml')
```

Dùng `$dwEvidence` của cách chạy từng bước ở mục 3 và đường dẫn `pytest.xml` mới. Khi dùng runner, truyền `--with-tests` để script tự chọn đường dẫn test/report. Integration tests dùng PostgreSQL thật, tạo database test tên riêng và chỉ dọn database do fixture tạo; tài khoản test cần quyền tạo database. Mỗi lần chạy dùng `--basetemp` mới trong workspace, không trỏ vào thư mục có dữ liệu cần giữ.

## 7. File kết quả

| File trong thư mục run | Nội dung |
|---|---|
| `inputs/preflight.json` | Kết quả kiểm tra đầu vào khi dùng runner |
| `migration.json` | Kết quả migration và checksum ledger |
| `first_load.json` | Trạng thái nạp, run/data version, số dòng; lần publish mới có kết quả kiểm tra trong transaction |
| `quality_report.json` | Kiểm tra độc lập, đối soát và quality |
| `rerun.json` | No-op cùng active version |
| `pytest.xml` | Kết quả kiểm thử nếu thực hiện mục 6 |
| `summary.json` | Kết quả runner, các bước đã chạy, mã thoát, run/data version hoặc bước lỗi |

Dữ liệu nghiệp vụ lưu trong PostgreSQL, không tự xuất CSV/Parquet. Giữ report cùng config/source versions để tái lập. [Báo cáo tổng hợp](dw_report.md#evidence) liệt kê evidence nghiệm thu và dependency coverage phải giữ nguyên.

## 8. Xử lý lỗi

| Hiện tượng | Xử lý |
|---|---|
| Không kết nối được PostgreSQL | Kiểm tra dịch vụ và environment; không in credential vào log |
| Chưa có published Staging hoặc metadata lệch | Kiểm tra source selection, registry và quality theo runbook Staging |
| Migration ledger/checksum không khớp | Kiểm tra đúng SQL đã áp dụng; không sửa ledger để bỏ qua kiểm tra |
| Mapping/coverage hash không khớp | Khôi phục đúng asset hoặc cập nhật version/hash sau khi kiểm tra nội dung thay đổi |
| Ngày Booking không xác định hoặc thiếu ngày calendar | Kiểm tra source/config; không đoán ngày hoặc loại dòng để vượt kiểm tra |
| Load/quality thất bại | Xem error summary và issues; lỗi trước commit giữ snapshot đang phục vụ |
| Tiến trình bị ngắt | Xử lý nguyên nhân rồi chạy lại; loader đánh dấu attempt loading bị ngắt là failed trước lần nạp mới |
| Report không ghi được sau DB commit | Kiểm tra active run bằng SQL/quality vì DB có thể đã published; lưu evidence mới, không reset dữ liệu |
| Đã có Mart và cần rebuild DW | Loader tự refresh/validate Mart cùng transaction/data_version; dùng runner `--with-mart` để lưu quality độc lập cho cả hai lớp |

Full refresh có thể cấp surrogate keys mới. Đối chiếu bằng source keys/natural codes; ứng dụng đọc nhiều query cho một kết quả phải dùng cùng transaction/snapshot và `data_version`.

## 9. Xây và kiểm tra Operations Mart

### 9.1. Chạy toàn bộ DW/Mart bằng một lệnh

Điều kiện đầu vào như mục 2. Không nạp lại Staging khi published snapshot không đổi.

```powershell
.\.venv\Scripts\python.exe scripts/run_dw.py --with-mart
```

Runner chạy preflight → migration DW → migration Mart → load DW/Mart → quality độc lập DW/Mart → rerun. Muốn chạy thêm toàn bộ tests, thêm `--with-tests`. Có thể chọn `--config`, `--dbname` và `--output-dir` mới như mục 3. Tất cả lệnh dùng Python trong `.venv`.

Kết quả `summary.json` phải có `status=completed`, `verified=true`, `mart_verified=true`; load/quality/rerun cùng run/data version, cùng Mart fingerprint/counts. Hai bảng Mart có đủ actual dates; country có actual dates × accepted countries + UNK. Không đưa bảy ngày horizon vào actual.

Khi Mart schema đã cài, DW loader luôn refresh/validate Mart trong cùng data transaction trước publish, kể cả chạy `--to dw` riêng. Cùng fingerprint thì no-op có kiểm tra Mart; nếu chưa có `dataset_state`, loader dựng Mart lần đầu trên phiên bản DW hiện hành sau khi validate DW. Thay runtime/rule/config/source khiến DW build mới và Mart cùng dùng version mới. Schema Mart không có ledger hoặc checksum lệch bị chặn, không tự nhận làm schema hợp lệ.

### 9.2. Chỉ khởi tạo hoặc kiểm tra Mart trên DW đã published

```powershell
$martEvidence = Join-Path 'artifacts/mart/operations' ('run_' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe scripts/setup_db.py --schema mart --report (Join-Path $martEvidence 'migration.json')
.\.venv\Scripts\python.exe scripts/refresh_marts.py --report (Join-Path $martEvidence 'first_load.json')
.\.venv\Scripts\python.exe pipeline/quality/mart_checks.py --report (Join-Path $martEvidence 'quality_report.json')
.\.venv\Scripts\python.exe scripts/refresh_marts.py --report (Join-Path $martEvidence 'rerun.json')
```

Chạy từng lệnh và chỉ tiếp tục khi mã thoát là `0`. Setup yêu cầu DW schema đã có. Refresh yêu cầu DW published hợp lệ với đúng config/source selection; nhận `--config`, `--dbname`. Không có DW thì chạy mục 9.1. Cách này giữ nguyên DW run/data version, chỉ dựng Mart từ snapshot DW đã được kiểm tra; không tải raw hay nạp Staging/DW lại.

Lần đầu refresh trả `published`; chạy lại cùng Mart fingerprint trả `no-op` sau validation, không đổi `dataset_state.published_at`. Mart bị sửa sai trong khi fingerprint không đổi sẽ báo lỗi thay vì coi no-op thành công. Quality trả `passed=true`, `errors=[]`, các checks bằng 0 và có `dw_quality` của cùng snapshot. Lỗi ghi report sau commit trả mã khác 0 nhưng không hoàn tác dữ liệu đã publish; dùng quality kiểm tra và lưu report mới.

Nếu đã có state nhưng Mart fingerprint thay đổi, refresh riêng từ chối thay nội dung trong cùng `data_version`; chạy mục 9.1 để rebuild DW/Mart và cấp phiên bản mới.

### 9.3. Kiểm tra phiên bản phục vụ

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT s.dw_run_id, s.data_version, s.actual_start, s.actual_end, s.row_counts,
       s.published_at, r.status, a.run_id = s.dw_run_id AS matches_active_dw
FROM mart.dataset_state AS s
JOIN dw.load_run AS r ON r.run_id = s.dw_run_id AND r.data_version = s.data_version
JOIN dw.active_dataset AS a ON a.singleton_id = s.singleton_id
WHERE s.singleton_id = 1;
COMMIT;
```

Phải có đúng một state, DW `published`, `matches_active_dw=true`. Hai đầu ra `mart.daily_hotel_operations` và `mart.daily_hotel_operations_by_country` là bảng lưu sẵn. Country lặp context/quality cấp ngày để giữ trạng thái khi lọc; không SUM các trường đó qua country. Các cột sum/valid count dùng để tính lại average/rate; mẫu số 0 giữ NULL. `target_guests` theo mục 9.3 thiết kế chỉ có giá trị khi guest COMPLETE; chưa tạo feature dataset.

### 9.4. Evidence và xử lý lỗi Mart

Giữ thư mục run mới cho từng lần kiểm chứng. Runner bổ sung `mart_migration.json`; `first_load.json`/`rerun.json` có phần `mart`, quality report có các checks Mart và `dw_quality`. `summary.json` ghi Mart counts/fingerprint. Bộ test có fixture ngày/country, coverage, eligibility, precision, rollback, validation failure, reader/writer đồng thời và CLI/report errors.

Lỗi trước commit giữ nguyên cả DW/Mart/state đang phục vụ; attempt DW mới được ghi failed. Không xóa schema/database hoặc sửa ledger để vượt lỗi. Khi chỉ đổi config, chạy lại DW/Mart bằng mục 9.1; refresh Mart riêng sẽ từ chối config khác DW đã published. Khi đổi source, đánh giá lại coverage và expected values trước, theo mục 8 và runbook Staging.
