"""Full-refresh Staging -> DW with pinned input, audit, rollback and atomic publish."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from pipeline.source_to_staging.common import ROOT, connect, sha256
from .checks import validate_candidate_keys, validate_loaded
from .config import DEFAULT_CONFIG, load_config, resolve_path
from .context import CONTEXT_COLUMNS, build_context
from .dimensions import DIMENSIONS, build_dimensions, insert_dimensions
from .facts import FACT_COLUMNS, insert_audit, insert_rows, map_fact_keys
from .migrations import MIGRATION_DIR, MIGRATION_FILES, WRITER_LOCK
from .quality import QUALITY_COLUMNS, build_coverage, build_daily_quality
from .snapshot import pin_published_snapshot, read_snapshot
from .transform import transform_booking
from pipeline.dw_to_mart.migrations import mart_installed, verify_mart_schema
from pipeline.dw_to_mart.operations import clear_operations, publish_state, refresh_operations, runtime_version
from pipeline.dw_to_mart.checks import validate_operations


RUNTIME_FILES = (
    "pipeline/staging_to_dw/run.py", "pipeline/staging_to_dw/snapshot.py", "pipeline/staging_to_dw/transform.py",
    "pipeline/staging_to_dw/config.py", "pipeline/staging_to_dw/dimensions.py", "pipeline/staging_to_dw/facts.py",
    "pipeline/staging_to_dw/context.py", "pipeline/staging_to_dw/quality.py", "pipeline/staging_to_dw/checks.py",
    "pipeline/staging_to_dw/migrations.py", "pipeline/quality/dw_checks.py", "database/validation/dw_checks.sql",
    "pipeline/source_to_staging/common.py", "pipeline/source_to_staging/booking.py",
)


def build_fingerprints(bundle: dict, header: dict) -> tuple[str, str]:
    hashes = {name: sha256(ROOT / name) for name in RUNTIME_FILES}
    hashes["operations_mart_runtime"] = runtime_version()
    hashes.update({f"database/dw/{name}": sha256(MIGRATION_DIR / name) for name in MIGRATION_FILES})
    code = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    material = {"code": code, "staging_batch_id": str(header["batch_id"]), "config_sha256": bundle["config_sha256"],
                "source_set_fingerprint": bundle["source_set_fingerprint"],
                "manifest_sha256": sha256(resolve_path(bundle["config"]["source_manifest"]))}
    return code, hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def verify_migration_ledger(conn) -> None:
    expected = [(name, sha256(MIGRATION_DIR / name)) for name in MIGRATION_FILES]
    if conn.execute("SELECT version,file_sha256 FROM dw.schema_migration ORDER BY version").fetchall() != expected:
        raise ValueError("DW migration ledger differs from implemented migrations; inspect setup first")


def checkpoint(phase: str, failure: str | None, interruption: str | None) -> None:
    """Fault hooks used only by rollback/interruption tests."""
    if phase == failure:
        raise RuntimeError(f"Injected failure after {phase}")
    if phase == interruption:
        raise KeyboardInterrupt(f"Injected interruption after {phase}")


def clear_serving_tables(cur) -> None:
    for table in ("fact_booking", "daily_hotel_context", "daily_data_quality", *DIMENSIONS, "dim_date"):
        cur.execute(sql.SQL("DELETE FROM dw.{}").format(sql.Identifier(table)))


def error_summary(exc: Exception) -> str:
    if isinstance(exc, psycopg.Error):
        return f"PostgreSQL DW operation failed (SQLSTATE {exc.sqlstate})"
    return str(exc)[:2000]


def run(config_path: Path = DEFAULT_CONFIG, *, dbname: str | None = None,
        inject_failure_after: str | None = None, inject_interruption_after: str | None = None) -> dict:
    bundle = load_config(config_path)
    candidate = {"facts": [], "rejections": [], "issues": [], "coverage": []}
    with connect(dbname) as conn:
        conn.autocommit = True
        conn.execute("SELECT pg_advisory_lock(%s)", (WRITER_LOCK,))
        try:
            verify_migration_ledger(conn)
            with conn.transaction():
                conn.execute("""UPDATE dw.load_run SET status='failed',finished_at=now(),error_summary='Interrupted before publication'
                                WHERE status='loading'""")
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                header, _ = pin_published_snapshot(conn, bundle)
                code_version, fingerprint = build_fingerprints(bundle, header)
                active = conn.execute("""SELECT r.run_id,r.data_version,r.build_fingerprint,r.row_counts
                                         FROM dw.active_dataset a JOIN dw.load_run r USING(run_id)
                                         WHERE a.singleton_id=1 AND r.status='published'""").fetchone()
                with_mart = mart_installed(conn)
                if with_mart:
                    verify_mart_schema(conn)
                if active and active[2] == fingerprint:
                    if with_mart:
                        # A freshly installed Mart still needs its first build on a DW no-op.
                        state = conn.execute("SELECT 1 FROM mart.dataset_state WHERE singleton_id=1").fetchone()
                        if not state:
                            dw_quality = validate_loaded(conn,active[0],bundle)
                            if not dw_quality["passed"]:
                                raise ValueError("DW validation failed before Mart initialization")
                            refresh_operations(conn,active[0],active[1],bundle)
                            mart_quality = validate_operations(conn,active[0],bundle,require_state=False)
                            if not mart_quality["passed"]:
                                raise ValueError("Mart validation failed: " + "; ".join(mart_quality["errors"]))
                            publish_state(conn,active[0],active[1],bundle,mart_quality["counts"])
                        else:
                            mart_quality = validate_operations(conn,active[0],bundle)
                            if not mart_quality["passed"]:
                                raise ValueError("Published Mart validation failed: " + "; ".join(mart_quality["errors"]))
                    return {"status": "no-op", "run_id": str(active[0]), "data_version": str(active[1]),
                            "staging_batch_id": str(header["batch_id"]), "build_fingerprint": fingerprint, "counts": active[3],
                            **({"mart":mart_quality} if with_mart else {})}
                run_id, data_version = uuid4(), uuid4()
                conn.execute("""INSERT INTO dw.load_run
                                (run_id,data_version,staging_batch_id,source_set_fingerprint,build_fingerprint,
                                 contract_version,code_version,mapping_versions,config_sha256,status)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'loading')""",
                             (run_id, data_version, header["batch_id"], bundle["source_set_fingerprint"], fingerprint,
                              bundle["config"]["contract_version"], code_version,
                              Jsonb({name: {"version": v["version"], "sha256": v["sha256"]} for name, v in bundle["config"]["mappings"].items()}),
                              bundle["config_sha256"]))
            try:
                with conn.transaction():
                    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                    snapshot = read_snapshot(conn, bundle)
                    if snapshot.header["batch_id"] != header["batch_id"]:
                        raise ValueError("Staging publication changed while preparing the DW run")
                    grouped_issues = snapshot.booking_issues()
                    blocked = False
                    for source in snapshot.bookings:
                        result = transform_booking(source, bundle["config"], bundle["mappings"],
                                                   grouped_issues[(source["_source_file_sha256"], source["_source_row_id"])])
                        if result.fact is not None:
                            candidate["facts"].append(result.fact)
                        else:
                            candidate["rejections"].append(result.rejection)
                        candidate["issues"].extend(result.issues)
                        blocked = blocked or result.block_publish
                    validate_candidate_keys(snapshot, candidate["facts"], candidate["rejections"])
                    if blocked:
                        raise ValueError("Unknown-date Booking rejection blocks publication under D06")
                    actual = bundle["config"]["actual"]
                    if any(r["arrival_date"] is not None and not date.fromisoformat(actual["start"]) <= r["arrival_date"] <= date.fromisoformat(actual["end"])
                           for r in snapshot.bookings):
                        raise ValueError("Actual interval excludes a known source arrival date")
                    dimensions = build_dimensions(candidate["facts"], bundle["config"], bundle["mappings"])
                    contexts, context_issues = build_context(dimensions["dim_date"], snapshot, bundle["coverage"])
                    candidate["issues"].extend(context_issues)
                    candidate["coverage"] = build_coverage(dimensions["dim_date"], contexts, bundle)
                    qualities = build_daily_quality(dimensions["dim_date"], snapshot.bookings, candidate["facts"], candidate["rejections"], bundle["coverage"])
                    checkpoint("transform", inject_failure_after, inject_interruption_after)
                    with conn.cursor() as cur:
                        if with_mart:
                            clear_operations(conn)
                        clear_serving_tables(cur)
                        checkpoint("clear", inject_failure_after, inject_interruption_after)
                        lookups = insert_dimensions(cur, dimensions)
                        checkpoint("dimensions", inject_failure_after, inject_interruption_after)
                        insert_rows(cur, "fact_booking", FACT_COLUMNS, map_fact_keys(candidate["facts"], lookups, run_id))
                        checkpoint("facts", inject_failure_after, inject_interruption_after)
                        insert_rows(cur, "daily_hotel_context", CONTEXT_COLUMNS, [{**r, "dw_run_id": run_id} for r in contexts])
                        insert_rows(cur, "daily_data_quality", QUALITY_COLUMNS, [{**r, "dw_run_id": run_id} for r in qualities])
                        insert_audit(cur, run_id, candidate["issues"], candidate["rejections"], candidate["coverage"])
                    checkpoint("context", inject_failure_after, inject_interruption_after)
                    quality = validate_loaded(conn, run_id, bundle)
                    if not quality["passed"]:
                        raise ValueError("DW validation failed: " + "; ".join(quality["errors"]))
                    checkpoint("validation", inject_failure_after, inject_interruption_after)
                    mart_quality = None
                    if with_mart:
                        refresh_operations(conn,run_id,data_version,bundle)
                        checkpoint("mart_refresh", inject_failure_after, inject_interruption_after)
                        mart_quality = validate_operations(conn,run_id,bundle,require_state=False)
                        if not mart_quality["passed"]:
                            raise ValueError("Mart validation failed: " + "; ".join(mart_quality["errors"]))
                        checkpoint("mart_validation", inject_failure_after, inject_interruption_after)
                        publish_state(conn,run_id,data_version,bundle,mart_quality["counts"])
                    conn.execute("UPDATE dw.load_run SET status='published',finished_at=now(),row_counts=%s WHERE run_id=%s",
                                 (Jsonb(quality["counts"]), run_id))
                    conn.execute("""INSERT INTO dw.active_dataset(singleton_id,run_id) VALUES (1,%s)
                                    ON CONFLICT(singleton_id) DO UPDATE SET run_id=EXCLUDED.run_id,published_at=now()""", (run_id,))
                    checkpoint("publish", inject_failure_after, inject_interruption_after)
                return {"status": "published", "run_id": str(run_id), "data_version": str(data_version),
                        "staging_batch_id": str(header["batch_id"]), "source_set_fingerprint": bundle["source_set_fingerprint"],
                        "build_fingerprint": fingerprint, "config_sha256": bundle["config_sha256"], "code_version": code_version,
                        "counts": quality["counts"], "quality": quality,
                        **({"mart":mart_quality} if mart_quality is not None else {}),
                        "input_versions": {"config": bundle["config"], "coverage": bundle["coverage"]}}
            except Exception as exc:
                with conn.transaction():
                    conn.execute("UPDATE dw.load_run SET status='failed',finished_at=now(),error_summary=%s WHERE run_id=%s",
                                 (error_summary(exc), run_id))
                    with conn.cursor() as cur:
                        insert_audit(cur, run_id, candidate["issues"], candidate["rejections"], candidate["coverage"])
                raise
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (WRITER_LOCK,))
