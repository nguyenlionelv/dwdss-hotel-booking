"""Transactional three-source Staging load and atomic published snapshot switch."""

from __future__ import annotations

import uuid
from pathlib import Path

from psycopg.types.json import Jsonb

from . import booking, holiday, weather
from .common import DEFAULT_MANIFEST, SOURCE_IDS, StructuralError, connect, insert_issues, source_set, verify_sources


LOADERS = {"booking": booking.load, "holiday": holiday.load, "weather": weather.load}
TABLES = {"booking": "stg_booking", "holiday": "stg_holiday", "weather": "stg_weather"}


def _check_results(cur, sources: dict, results: dict) -> dict:
    summary = {}
    for source_id in SOURCE_IDS:
        spec = sources[source_id]
        result = results[source_id]
        if result.raw_count != (result.staged_count + result.out_of_scope_count
                                + result.unidentified_count + result.reject_count):
            raise RuntimeError(f"{source_id}: raw/staged/scope/reject reconciliation failed")
        for name, expected in spec.get("expected", {}).items():
            if getattr(result, name) != expected:
                raise RuntimeError(f"{source_id}: {name}={getattr(result, name)} differs from manifest expectation {expected}")
        cur.execute(
            f"SELECT count(*) FROM staging.{TABLES[source_id]} WHERE _source_file_sha256 = %s",
            (spec["sha256"],),
        )
        physical = cur.fetchone()[0]
        if physical != result.staged_count:
            raise RuntimeError(f"{source_id}: physical rows {physical} != staged records {result.staged_count}")
        summary[source_id] = {
            "sha256": spec["sha256"],
            "raw_count": result.raw_count,
            "staged_count": result.staged_count,
            "out_of_scope_count": result.out_of_scope_count,
            "unidentified_count": result.unidentified_count,
            "reject_count": result.reject_count,
            "missing_counts": result.missing_json(),
            "invalid_counts": dict(result.invalid),
        }
    # Group before join: same-day holiday names never multiply bookings.
    cur.execute(
        """WITH h AS (SELECT date FROM staging.stg_holiday WHERE _source_file_sha256=%s GROUP BY date),
                  w AS (SELECT local_date FROM staging.stg_weather WHERE _source_file_sha256=%s GROUP BY local_date)
           SELECT count(*) FROM staging.stg_booking AS b
           LEFT JOIN h ON h.date=b.arrival_date
           LEFT JOIN w ON w.local_date=b.arrival_date
           WHERE b._source_file_sha256=%s""",
        (sources["holiday"]["sha256"], sources["weather"]["sha256"], sources["booking"]["sha256"]),
    )
    join_count = cur.fetchone()[0]
    if join_count != results["booking"].staged_count:
        raise RuntimeError("Daily context join multiplied or lost Booking records")
    summary["context_join_booking_rows"] = join_count
    return summary


def run(manifest_path: Path = DEFAULT_MANIFEST, *, dbname: str | None = None,
        inject_failure_after: str | None = None) -> dict:
    contract_version, sources, fingerprint = source_set(manifest_path, verify=False)
    with connect(dbname) as conn:
        with conn.cursor() as cur:
            # Session lock serializes loads; a crashed process releases it automatically.
            cur.execute("SELECT pg_advisory_lock(634718250)")
            cur.execute(
                """UPDATE staging.load_batch SET status='failed',finished_at=now(),
                          error_summary='Interrupted before publication'
                   WHERE status='loading'"""
            )
            conn.commit()
            try:
                verify_sources(sources)
            except StructuralError as exc:
                failed_id = uuid.uuid4()
                cur.execute(
                    """INSERT INTO staging.load_batch
                       (batch_id,source_set_fingerprint,contract_version,status,finished_at,error_summary)
                       VALUES (%s,%s,%s,'failed',now(),%s)""",
                    (failed_id, fingerprint, contract_version, str(exc)[:2000]),
                )
                cur.execute(
                    """INSERT INTO staging.reject
                       (batch_id,source_id,source_file_sha256,source_locator,raw_fragment,rule_code,reason)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (failed_id, exc.source_id, sources[exc.source_id]["sha256"], exc.locator,
                     exc.raw_fragment, "STRUCTURAL_READ_FAILURE", exc.reason),
                )
                conn.commit()
                raise
            cur.execute(
                "SELECT batch_id FROM staging.load_batch WHERE source_set_fingerprint=%s AND status='published'",
                (fingerprint,),
            )
            existing = cur.fetchone()
            if existing:
                conn.rollback()
                return {"status": "no-op", "batch_id": str(existing[0]), "source_set_fingerprint": fingerprint}
            batch_id = uuid.uuid4()
            cur.execute(
                "INSERT INTO staging.load_batch(batch_id,source_set_fingerprint,contract_version,status) VALUES (%s,%s,%s,'loading')",
                (batch_id, fingerprint, contract_version),
            )
            conn.commit()  # Persist attempt before the atomic data/publication transaction.
            current_source = "booking"
            try:
                results = {}
                for source_id in SOURCE_IDS:
                    current_source = source_id
                    spec = sources[source_id]
                    result = LOADERS[source_id](cur, spec, batch_id)
                    results[source_id] = result
                    insert_issues(cur, result.issues)
                    metadata = {key: value for key, value in spec.items()
                                if key not in {"resolved_path", "expected"}}
                    cur.execute(
                        """INSERT INTO staging.load_batch_source
                           (batch_id,source_id,source_file,source_file_sha256,source_metadata,
                            raw_count,staged_count,out_of_scope_count,unidentified_count,reject_count,
                            missing_counts,invalid_counts)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (batch_id, source_id, spec["file"], spec["sha256"], Jsonb(metadata),
                         result.raw_count, result.staged_count, result.out_of_scope_count,
                         result.unidentified_count, result.reject_count,
                         Jsonb(result.missing_json()), Jsonb(dict(result.invalid))),
                    )
                    if inject_failure_after == source_id:
                        raise RuntimeError(f"Injected failure after {source_id}")
                summary = _check_results(cur, sources, results)
                cur.execute("SELECT pg_advisory_xact_lock(634718252)")
                cur.execute(
                    "UPDATE staging.load_batch SET status='published', finished_at=now() WHERE batch_id=%s",
                    (batch_id,),
                )
                cur.execute(
                    """INSERT INTO staging.active_snapshot(singleton_id,batch_id,published_at)
                       VALUES (1,%s,now()) ON CONFLICT (singleton_id)
                       DO UPDATE SET batch_id=EXCLUDED.batch_id,published_at=EXCLUDED.published_at""",
                    (batch_id,),
                )
                conn.commit()
                return {"status": "published", "batch_id": str(batch_id),
                        "source_set_fingerprint": fingerprint, "sources": summary}
            except Exception as exc:
                conn.rollback()
                cur.execute(
                    "UPDATE staging.load_batch SET status='failed', finished_at=now(), error_summary=%s WHERE batch_id=%s",
                    (str(exc)[:2000], batch_id),
                )
                if isinstance(exc, StructuralError):
                    cur.execute(
                        """INSERT INTO staging.reject
                           (batch_id,source_id,source_file_sha256,source_locator,raw_fragment,rule_code,reason)
                           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                        (batch_id, exc.source_id, sources[exc.source_id]["sha256"], exc.locator,
                         exc.raw_fragment, "STRUCTURAL_READ_FAILURE", exc.reason),
                    )
                conn.commit()
                raise
