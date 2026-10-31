# Chạy DW và Operations Mart

## 1. Cài và kích hoạt môi trường

Chạy từ thư mục gốc repository trong PowerShell. Lần đầu, tạo `.venv`, kích hoạt và cài dependency:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r pipeline/requirements.txt -r pipeline/requirements-dev.txt
```

Nếu đã có `.venv` và dependency, chỉ cần kích hoạt:

```powershell
.\.venv\Scripts\Activate.ps1
```

Điều kiện trước khi chạy:

- `.env` có cấu hình kết nối PostgreSQL đúng; nếu dùng Docker, khởi động bằng `docker compose up -d db` và đợi DB sẵn sàng.
- Staging đã publish và quality đạt theo [Staging runbook](staging_runbook.md). Lệnh DW không tự nạp lại Source → Staging.
- Giữ raw source, acquisition metadata theo [manifest](data_dictionary/operations_source_set.json), cùng config, mappings và coverage evidence của dự án.

<a id="9-xây-và-kiểm-tra-operations-mart"></a>

## 2. Chạy DW/Mart

Chọn một lệnh phù hợp; không cần chạy lần lượt cả ba:

```powershell
# DW
python scripts/run_pipeline.py --to dw

# DW và Operations Mart
python scripts/run_pipeline.py --to dw --with-mart

# DW và Mart, kèm toàn bộ test Staging/DW/Mart
python scripts/run_pipeline.py --to dw --with-mart --with-tests
```

Runner tự chạy **preflight → migration → load → quality độc lập → rerun → đối chiếu kết quả**, sau đó chạy pytest nếu có `--with-tests`. Có `--with-mart` thì thêm migration Mart và kiểm tra độc lập cả DW/Mart. Bộ test dùng database fixture riêng; tài khoản PostgreSQL cần quyền tạo database.

Nếu Mart đã cài, loader vẫn refresh/validate Mart cùng DW trong transaction dữ liệu, kể cả khi không truyền `--with-mart`.

Các tùy chọn bổ sung:

| Argument | Công dụng |
|---|---|
| `--config <file>` | Chọn config DW; mặc định `pipeline/config/dw_operations.json` |
| `--dbname <tên_db>` | Chọn database khác `POSTGRES_DB` |
| `--output-dir <thư_mục_mới>` | Chọn thư mục artifact chưa tồn tại |

Mỗi bước chỉ tiếp tục khi bước trước thành công. Có lỗi thì runner dừng và trả exit code khác `0`.

## 3. Xem kết quả

Runner in đường dẫn thư mục mới `artifacts/dw/operations/run_<id>/`. Mở `summary.json`, yêu cầu:

- `status=completed`, `verified=true`.
- Nếu chạy `--with-mart`: thêm `mart_verified=true`.
- Load, quality và rerun cùng `run_id`/`data_version`, counts không đổi; rerun là `no-op`.
- Nếu chạy `--with-tests`: `tests_run=true`, bước `tests` có `exit_code=0`.

| File | Nội dung |
|---|---|
| `summary.json` | Kết quả chung; `failed_step` nếu lỗi |
| `inputs/preflight.json` | Kiểm tra đầu vào |
| `migration.json`, `mart_migration.json` | Migration DW/Mart; file Mart chỉ có khi chọn `--with-mart` |
| `first_load.json`, `rerun.json` | Kết quả nạp và chạy lại |
| `quality_report.json` | Quality độc lập: `passed=true`, `errors=[]`, violation counts bằng `0` |
| `pytest.xml` | Kết quả test khi có `--with-tests` |

Giữ artifact cũ và các config/source versions để truy vết. Dữ liệu nghiệp vụ nằm trong PostgreSQL; runner không tự xuất CSV/Parquet. Hai bảng Mart là `mart.daily_hotel_operations` và `mart.daily_hotel_operations_by_country`.

## 4. Chỉ dựng Mart trên DW đã publish

Dùng khi DW đã hợp lệ và chỉ cần khởi tạo/kiểm tra Mart, giữ nguyên DW run/data version:

```powershell
$martEvidence = Join-Path 'artifacts/mart/operations' ('run_' + [guid]::NewGuid().ToString('N'))
python scripts/setup_db.py --schema mart --report (Join-Path $martEvidence 'migration.json')
python scripts/refresh_marts.py --report (Join-Path $martEvidence 'first_load.json')
python pipeline/quality/mart_checks.py --report (Join-Path $martEvidence 'quality_report.json')
python scripts/refresh_marts.py --report (Join-Path $martEvidence 'rerun.json')
```

Chạy từng lệnh, chỉ tiếp tục khi exit code bằng `0`. Yêu cầu quality đạt và rerun `no-op`. Nếu chưa có DW hoặc Mart fingerprint/config đã thay đổi, chạy lại quy trình DW/Mart ở mục 2 để dựng phiên bản phù hợp. Khi chọn `--config`/`--dbname` khác mặc định, truyền cùng giá trị cho các lệnh liên quan; setup chỉ nhận `--dbname`.

## 5. Chạy riêng một bước khi cần

Kiểm tra đầu vào hoặc quality, không nạp lại dữ liệu:

```powershell
python scripts/check_dw_inputs.py
python pipeline/quality/dw_checks.py
python pipeline/quality/mart_checks.py
```

Hai lệnh quality chỉ in kết quả nếu không có `--report`; có thể thêm `--report <file_mới.json>` để lưu. Preflight tự tạo thư mục artifact và chỉ chứng nhận đầu vào, không phải kết quả nghiệm thu DW/Mart.

Để chỉ nạp DW, schema phải có sẵn. Chạy lại cùng lệnh với file report mới để kiểm tra `no-op`:

```powershell
$dwEvidence = Join-Path 'artifacts/dw/operations' ('run_' + [guid]::NewGuid().ToString('N'))
python scripts/run_pipeline.py --to dw --step load --report (Join-Path $dwEvidence 'first_load.json')
```

`--step load` không tự chạy preflight/migration/quality độc lập/rerun. Dùng `--report` cho load riêng, `--output-dir` cho quy trình đầy đủ; `--with-mart`/`--with-tests` chỉ dùng với quy trình đầy đủ. `scripts/run_dw.py` vẫn là wrapper tương thích cho lệnh cũ.

## 6. Khi có lỗi

Xem `failed_step` trong `summary.json` và report của bước đó. Kiểm tra kết nối DB, published Staging hoặc checksum/config theo lỗi được ghi; không sửa raw, ledger hay xóa database để vượt kiểm tra. Khi thay source, kiểm tra metadata và đánh giá lại coverage/expected counts trước khi nạp.

Lỗi trong transaction nạp giữ snapshot phục vụ trước đó. Nếu bước sau lỗi, các bước đã commit trước đó vẫn còn hiệu lực; toàn bộ runner không có một transaction chung. Khi lỗi ghi report sau commit, kiểm tra lại bằng quality và lưu evidence mới trước khi kết luận trạng thái DB.

Chi tiết thiết kế tại [dw_design.md](dw_design/dw_design.md); kết quả triển khai và evidence tại [dw_report.md](dw_report.md).
