# Data

- `raw/`: bản gốc từ từng nguồn; giữ nguyên và ghi provenance/phiên bản nguồn trong `docs/data_dictionary/`.
- `sample/`: mẫu dữ liệu nhỏ, có thể chia sẻ và dùng cho demo/kiểm thử.

Tệp dữ liệu raw không được Git theo dõi. Không đặt dữ liệu cá nhân hoặc credential trong repo. Một dòng dữ liệu booking cần có khóa kỹ thuật ổn định khi nạp vào staging để trace qua DW/Mart.
