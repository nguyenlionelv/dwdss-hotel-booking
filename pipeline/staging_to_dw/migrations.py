"""Apply the ordered DW SQL files atomically, with an immutable checksum ledger."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

import psycopg

from pipeline.source_to_staging.common import ROOT


MIGRATION_DIR = ROOT / "database/dw"
MIGRATION_FILES = ("001_control.sql", "002_dimensions.sql", "003_fact_context_quality.sql")
WRITER_LOCK = 634718250


def apply_dw_migrations(conn: psycopg.Connection, migration_dir: Path = MIGRATION_DIR) -> dict:
    """Require an idle connection; all pending files and ledger entries commit together."""
    if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        raise ValueError("DW migration requires an idle connection")
    migrations = []
    for name in MIGRATION_FILES:
        content = (migration_dir / name).read_bytes()
        migrations.append((name, hashlib.sha256(content).hexdigest(), content.decode("utf-8")))
    applied, skipped = [], []
    with conn.transaction():
        # Same lock as Staging/DW writers; concurrent setup calls cannot race the ledger.
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (WRITER_LOCK,))
        required = ("staging.load_batch", "staging.load_batch_source", "staging.stg_booking")
        if any(conn.execute("SELECT to_regclass(%s)", (table,)).fetchone()[0] is None for table in required):
            raise ValueError("Apply the Staging schema before the DW migration")
        schema_exists = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='dw')").fetchone()[0]
        ledger_exists = conn.execute("SELECT to_regclass('dw.schema_migration') IS NOT NULL").fetchone()[0]
        if schema_exists and not ledger_exists:
            raise ValueError("DW schema exists without a migration ledger; inspect it before applying migrations")
        recorded = dict(conn.execute("SELECT version,file_sha256 FROM dw.schema_migration ORDER BY version").fetchall()) if ledger_exists else {}
        names = [name for name, _, _ in migrations]
        if list(recorded) != names[:len(recorded)]:
            raise ValueError("DW migration ledger is not a known ordered prefix")
        for name, checksum, _ in migrations:
            if name in recorded and recorded[name] != checksum:
                raise ValueError(f"Applied DW migration checksum mismatch: {name}")
        for name, checksum, ddl in migrations:
            if name in recorded:
                skipped.append(name)
                continue
            conn.execute(ddl)
            conn.execute("INSERT INTO dw.schema_migration(version,file_sha256) VALUES (%s,%s)", (name, checksum))
            applied.append(name)
        database_version = conn.execute("SHOW server_version").fetchone()[0]
    return {"schema": "dw", "status": "applied" if applied else "no-op", "applied": applied, "skipped": skipped,
            "migrations": [{"version": name, "file_sha256": checksum} for name, checksum, _ in migrations],
            "database_version": database_version, "finished_at_utc": datetime.now(timezone.utc).isoformat()}
