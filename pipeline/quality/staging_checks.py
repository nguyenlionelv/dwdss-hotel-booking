"""Read-only PostgreSQL quality and reconciliation report for the active Staging batch."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.source_to_staging.common import SOURCE_IDS, connect  # noqa: E402


def report(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT b.batch_id,b.status,b.source_set_fingerprint,b.contract_version,
                      a.published_at,current_setting('server_version')
               FROM staging.active_snapshot a JOIN staging.load_batch b ON b.batch_id=a.batch_id
               WHERE a.singleton_id=1"""
        )
        active = cur.fetchone()
        if not active:
            raise RuntimeError("No published Staging snapshot")
        batch_id, status, fingerprint, contract_version, published_at, db_version = active
        cur.execute(
            """SELECT source_id,source_file,source_file_sha256,source_metadata,
                      raw_count,staged_count,out_of_scope_count,unidentified_count,reject_count,
                      missing_counts,invalid_counts
               FROM staging.load_batch_source WHERE batch_id=%s ORDER BY source_id""",
            (batch_id,),
        )
        sources = {}
        errors = []
        for row in cur.fetchall():
            sid, path, sha, metadata, raw, staged, out_scope, unidentified, rejected, missing, invalid = row
            sources[sid] = {
                "file": path, "sha256": sha.strip(), "source_metadata": metadata,
                "raw_count": raw, "staged_count": staged, "out_of_scope_count": out_scope,
                "unidentified_count": unidentified, "reject_count": rejected,
                "missing_counts": missing, "invalid_counts": invalid,
                "reconciles": raw == staged + out_scope + unidentified + rejected,
            }
            if not sources[sid]["reconciles"]:
                errors.append(f"{sid}: record reconciliation failed")
        if set(sources) != set(SOURCE_IDS):
            errors.append("Published batch does not contain exactly three sources")
        counts = {}
        for sid in SOURCE_IDS:
            cur.execute(f"SELECT count(*) FROM staging.v_{sid}_current")
            counts[sid] = cur.fetchone()[0]
            if sid in sources and counts[sid] != sources[sid]["staged_count"]:
                errors.append(f"{sid}: active count differs from batch count")
        cur.execute("SELECT count(*) FROM staging.v_booking_current WHERE hotel <> 'City Hotel'")
        non_city = cur.fetchone()[0]
        if non_city:
            errors.append("Non-City records are present in active Booking")
        cur.execute(
            """SELECT source_id,issue_type,rule_code,count(*),
                      count(DISTINCT (source_file_sha256,source_row_id))
               FROM staging.quality_issue WHERE batch_id=%s
               GROUP BY source_id,issue_type,rule_code ORDER BY source_id,issue_type,rule_code""",
            (batch_id,),
        )
        issues = [
            {"source_id": sid, "issue_type": kind, "rule_code": code,
             "issue_count": count, "affected_records": affected}
            for sid, kind, code, count, affected in cur.fetchall()
        ]
        cur.execute("SELECT count(*),count(DISTINCT local_date),count(*) FILTER (WHERE weather_ambiguous),count(*) FILTER (WHERE precipitation_sum IS NULL) FROM staging.v_daily_context_current")
        days, unique_days, ambiguous, unknown_rain = cur.fetchone()
        if days != unique_days:
            errors.append("Daily context duplicates a date")
        cur.execute(
            """SELECT count(*) FROM staging.v_booking_current b
               LEFT JOIN staging.v_daily_context_current c
               ON c.local_date=b.arrival_date AND c.hotel=b.hotel"""
        )
        joined = cur.fetchone()[0]
        if joined != counts["booking"]:
            errors.append("Context join multiplied or lost Booking records")
        cur.execute("SELECT count(*) FROM staging.reject WHERE batch_id=%s", (batch_id,))
        rejected_rows = cur.fetchone()[0]
        if rejected_rows:
            errors.append("Published batch contains structural rejects")
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "database_version": db_version,
            "batch_id": str(batch_id), "batch_status": status,
            "source_set_fingerprint": fingerprint.strip(),
            "contract_version": contract_version, "published_at": published_at.isoformat(),
            "sources": sources, "active_counts": counts, "non_city_booking_rows": non_city,
            "issues": issues, "structural_rejects": rejected_rows,
            "context": {"days": days, "unique_days": unique_days,
                        "ambiguous_weather_days": ambiguous, "unknown_precipitation_days": unknown_rain,
                        "booking_rows_after_join": joined},
            "passed": not errors, "errors": errors,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dbname")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    with connect(args.dbname) as conn:
        result = report(conn)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
