"""Application configuration and environment management."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load_dotenv(env_path: Path | None = None) -> None:
    """Read local .env without overwriting existing process environment variables.

    Vai trò (Role):
        Đọc tệp cấu hình `.env` cục bộ và nạp các cặp khóa-giá trị vào biến môi trường
        của tiến trình (`os.environ`) mà không ghi đè các biến môi trường đã tồn tại.

    Input:
        - env_path (Path | None, mặc định=None): Đường dẫn tới tệp `.env`. Nếu không truyền,
          hàm mặc định tìm tệp `.env` tại thư mục gốc của dự án (`ROOT / ".env"`).

    Output:
        - None: Không trả về giá trị (cập nhật trực tiếp vào `os.environ` dưới dạng side-effect).
    """
    target = env_path or (ROOT / ".env")
    if not target.is_file():
        return
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    postgres_db: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "hotel_dwdss"))
    postgres_user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "hotel_user"))
    postgres_password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", ""))
    postgres_host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    postgres_port: str = field(default_factory=lambda: os.getenv("POSTGRES_PORT", "5432"))

    hotel_name: str = "City Hotel"
    location: str = "Lisbon, Portugal"
    timezone: str = "Europe/Lisbon"
    api_prefix: str = "/api"

    cors_origins: list[str] = field(default_factory=lambda: [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
        ).split(",")
        if origin.strip()
    ])


def get_settings() -> Settings:
    """Load environment variables and return an immutable Settings instance.

    Vai trò (Role):
        Kích hoạt việc nạp tệp `.env` thông qua `load_dotenv()` và khởi tạo đối tượng
        cấu hình bất biến `Settings` chứa thông số kết nối PostgreSQL, thông tin khách sạn và CORS.

    Input:
        - Không có tham số đầu vào (đọc gián tiếp từ biến môi trường hệ thống và tệp `.env`).

    Output:
        - Settings: Đối tượng dataclass bất biến (`frozen=True`) chứa toàn bộ cấu hình ứng dụng.
    """
    load_dotenv()
    return Settings()
