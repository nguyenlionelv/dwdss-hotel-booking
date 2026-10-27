"""Bootstrap or verify Operations Mart for the currently published DW snapshot."""

from pathlib import Path

from pipeline.source_to_staging.common import connect
from pipeline.staging_to_dw.checks import validate_loaded
from pipeline.staging_to_dw.config import DEFAULT_CONFIG, load_config
from pipeline.staging_to_dw.migrations import WRITER_LOCK
from .checks import validate_operations
from .migrations import verify_mart_schema
from .operations import build_fingerprint, publish_state, refresh_operations


def run(config_path: Path = DEFAULT_CONFIG, *, dbname: str | None = None,
        inject_failure_after: str | None = None) -> dict:
    """Keep the DW version; refuse a config mismatch or invalid published DW."""
    bundle = load_config(config_path)
    with connect(dbname) as conn:
        conn.autocommit = True
        conn.execute("SELECT pg_advisory_lock(%s)", (WRITER_LOCK,))
        try:
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                verify_mart_schema(conn)
                active = conn.execute("""SELECT r.run_id,r.data_version FROM dw.active_dataset a
                    JOIN dw.load_run r USING(run_id) WHERE a.singleton_id=1 AND r.status='published'""").fetchone()
                if not active:
                    raise ValueError("No published DW dataset; load DW before refreshing Mart")
                run_id, version = active
                dw_quality = validate_loaded(conn, run_id, bundle)
                if not dw_quality["passed"]:
                    raise ValueError("DW validation failed before Mart refresh: " + "; ".join(dw_quality["errors"]))
                state = conn.execute("SELECT build_fingerprint FROM mart.dataset_state WHERE singleton_id=1").fetchone()
                if state and state[0] == build_fingerprint(version,bundle):
                    quality = validate_operations(conn,run_id,bundle)
                    if not quality["passed"]:
                        raise ValueError("Published Mart validation failed: " + "; ".join(quality["errors"]))
                    return {"status": "no-op", **quality}
                if state:
                    raise ValueError("Mart fingerprint differs from the published version; rebuild DW/Mart with scripts/run_dw.py --with-mart")
                refresh_operations(conn,run_id,version,bundle)
                if inject_failure_after == "refresh":
                    raise RuntimeError("Injected failure after Mart refresh")
                quality = validate_operations(conn,run_id,bundle,require_state=False)
                if not quality["passed"]:
                    raise ValueError("Mart validation failed: " + "; ".join(quality["errors"]))
                publish_state(conn,run_id,version,bundle,quality["counts"])
                if inject_failure_after == "publish":
                    raise RuntimeError("Injected failure after Mart publish")
            return {"status": "published", **quality}
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (WRITER_LOCK,))
