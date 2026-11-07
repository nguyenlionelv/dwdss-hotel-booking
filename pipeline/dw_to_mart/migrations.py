"""Versioned Operations schema, sharing the Staging/DW writer lock."""

from pathlib import Path

import psycopg

from pipeline.source_to_staging.common import ROOT, sha256
from pipeline.staging_to_dw.migrations import WRITER_LOCK


MIGRATION = ROOT / "database/marts/operations_mart.sql"
GUEST_COMPONENTS_MIGRATION = ROOT / "database/marts/002_guest_components.sql"


def verify_mart_schema(conn, migration: Path = MIGRATION) -> None:
    """Reject unmanaged or partially installed serving objects."""
    ledger = conn.execute("SELECT to_regclass('mart.schema_migration')").fetchone()[0]
    if not ledger:
        raise ValueError("Operations Mart exists without its migration ledger; inspect setup first")
    recorded = dict(conn.execute("SELECT version,file_sha256 FROM mart.schema_migration"))
    expected = {path.name: sha256(path) for path in (migration, GUEST_COMPONENTS_MIGRATION)}
    if recorded != expected:
        raise ValueError("Operations Mart migration ledger/checksum mismatch")
    for name in ("dataset_state", "daily_hotel_operations", "daily_hotel_operations_by_country"):
        if conn.execute("SELECT to_regclass(%s)", ("mart." + name,)).fetchone()[0] is None:
            raise ValueError("Operations Mart schema is incomplete; inspect setup first")


def mart_installed(conn) -> bool:
    names = ("mart.schema_migration", "mart.dataset_state", "mart.daily_hotel_operations",
             "mart.daily_hotel_operations_by_country")
    return any(conn.execute("SELECT to_regclass(%s)", (name,)).fetchone()[0] for name in names)


def apply_mart_migration(conn, migration: Path = MIGRATION) -> dict:
    """Apply atomically on an idle connection; never adopt an unmanaged schema."""
    if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        raise ValueError("Mart migration requires an idle connection")
    migrations = (migration, GUEST_COMPONENTS_MIGRATION)
    applied, skipped = [], []
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (WRITER_LOCK,))
        if conn.execute("SELECT to_regclass('dw.load_run')").fetchone()[0] is None:
            raise ValueError("Apply DW migrations before Operations Mart")
        exists = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='mart')").fetchone()[0]
        ledger = conn.execute("SELECT to_regclass('mart.schema_migration')").fetchone()[0]
        if exists and not ledger:
            raise ValueError("Operations Mart exists without its migration ledger; inspect setup first")
        recorded = dict(conn.execute("SELECT version,file_sha256 FROM mart.schema_migration")) if ledger else {}
        names = [path.name for path in migrations]
        if set(recorded) != set(names[:len(recorded)]):
            raise ValueError("Operations Mart migration ledger is not a known prefix")
        for path in migrations:
            if path.name in recorded and recorded[path.name] != sha256(path):
                raise ValueError("Operations Mart migration ledger/checksum mismatch")
        for path in migrations:
            if path.name in recorded:
                skipped.append(path.name)
                continue
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO mart.schema_migration(version,file_sha256) VALUES (%s,%s)",
                         (path.name, sha256(path)))
            applied.append(path.name)
        verify_mart_schema(conn, migration)
    return {"schema": "mart", "status": "applied" if applied else "no-op",
            "version": GUEST_COMPONENTS_MIGRATION.name, "file_sha256": sha256(GUEST_COMPONENTS_MIGRATION),
            "applied": applied, "skipped": skipped}
