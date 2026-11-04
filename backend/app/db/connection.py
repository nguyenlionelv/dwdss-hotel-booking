"""Database connection and transactional session utilities for read-only serving."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg.rows import dict_row

from backend.app.core.config import get_settings


def connect(dbname: str | None = None) -> psycopg.Connection:
    """Create a raw psycopg connection with dict_row factory.

    Vai trò (Role):
        Mở một kết nối trực tiếp tới cơ sở dữ liệu PostgreSQL sử dụng thư viện `psycopg`,
        cấu hình `row_factory=dict_row` để kết quả truy vấn trả về dưới dạng từ điển (`dict`).

    Input:
        - dbname (str | None, mặc định=None): Tên cơ sở dữ liệu cần kết nối. Nếu là `None`,
          hàm sẽ lấy tên DB mặc định từ `settings.postgres_db`.

    Output:
        - psycopg.Connection: Đối tượng kết nối cơ sở dữ liệu PostgreSQL sử dụng `dict_row`.
    """
    settings = get_settings()
    return psycopg.connect(
        dbname=dbname or settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        connect_timeout=10,
        row_factory=dict_row,
    )


@contextmanager
def read_only_tx(dbname: str | None = None) -> Generator[psycopg.Connection, None, None]:
    """Execute within a single REPEATABLE READ READ ONLY transaction.

    Ensures that multi-query aggregations or metadata lookups observe a single,
    consistent database snapshot and data_version.

    Vai trò (Role):
        Context manager cung cấp một phiên giao dịch (transaction) chỉ đọc với mức cô lập
        `REPEATABLE READ READ ONLY`. Đảm bảo các truy vấn tổng hợp nhiều bước hoặc tra cứu
        metadata nhìn thấy cùng một snapshot dữ liệu và `data_version` nhất quán, đồng thời
        tự động đóng kết nối khi kết thúc khối `with`.

    Input:
        - dbname (str | None, mặc định=None): Tên cơ sở dữ liệu tùy chọn để truyền vào `connect()`.

    Output:
        - Generator[psycopg.Connection, None, None]: Sinh ra (`yield`) đối tượng kết nối `psycopg.Connection`
          đang nằm trong transaction chỉ đọc.
    """
    with connect(dbname) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            yield conn
