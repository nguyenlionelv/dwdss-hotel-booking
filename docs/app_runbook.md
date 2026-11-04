# Chạy development bằng Docker

Mở Docker Desktop, chạy lệnh tại thư mục gốc repository. Chuẩn bị `.env` theo [.env.example](../.env.example). Giữ nguyên nếu đã có.

## 1. Chạy app

```powershell
docker compose up -d --build
```

- Frontend: [localhost:5173](http://localhost:5173)
- Swagger: [localhost:8000/docs](http://localhost:8000/docs)

Những lần sau, chỉ cần:

```powershell
docker compose up -d
```

## 2. Khi code

Source đã được mount vào container. Frontend và backend hỗ trợ tự reload khi sửa code.

Khi đổi Dockerfile hoặc dependency, build lại:

```powershell
docker compose up -d --build -V
```

`-V` làm mới volume dependency frontend, giữ nguyên volume PostgreSQL.

## 3. Xem trạng thái và log

```powershell
docker compose ps
docker compose logs -f backend frontend
```

Đợi các service `healthy`. Nhấn `Ctrl+C` để thoát xem log.

## 4. Dừng app

```powershell
docker compose down
```

Dữ liệu PostgreSQL được giữ lại. Không thêm `-v` nếu muốn giữ database.

Database mới cần nạp dữ liệu theo [Staging runbook](staging_runbook.md) và [DW/Mart runbook](dw_runbook.md).
