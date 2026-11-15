# Data

- `raw/booking/`: Booking CSV và acquisition manifest.
- `raw/holiday/`: lịch PT/Lisboa và metadata generator.
- `raw/weather/`: Weather ERA5 Lisbon và metadata thu thập.
- `raw/event/`: thư mục dự phòng cho Phase 2, chưa có nguồn được chọn.

Các file được chọn đã có trong Git, được pin đường dẫn/checksum tại [source set](../docs/data_dictionary/operations_source_set.json). Có thể có bản thu thập cũ trên máy; không dùng chúng thay source set hiện hành.

Giữ nguyên bytes nguồn và metadata. Booking được truy vết bằng checksum file + ordinal dòng gốc. Xem [data dictionary](../docs/data_dictionary/operations_sources.md) và [Staging runbook](../docs/staging_runbook.md).
