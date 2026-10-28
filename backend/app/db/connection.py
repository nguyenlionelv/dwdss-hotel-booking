"""Database connection and transactional session utilities for read-only serving."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg.rows import dict_row

from backend.app.core.config import get_settings


def connect(dbname: str | None = None) -> psycopg.Connection:
    """Create a raw psycopg connection with dict_row factory."""
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
    """
    with connect(dbname) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            yield conn
