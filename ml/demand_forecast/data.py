"""Read-only, quality-gated Operations Mart snapshots and checksummed exports."""
from __future__ import annotations
from dataclasses import asdict, replace
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
from .contracts import CalendarDay, DailyTarget, DemandError, DemandSnapshot, STATUSES, local_date, nonnegative, utc_now

def json_default(value):
    return value.isoformat() if hasattr(value, "isoformat") else str(value)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=json_default).encode("utf-8")

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, allow_nan=False, default=json_default)
        f.write("\n")

def normalize_rows(rows):
    indexed, versions = {}, set()
    for raw in rows:
        row = asdict(raw) if isinstance(raw, DailyTarget) else dict(raw)
        day = local_date(row["full_date"])
        if day in indexed:
            raise DemandError("DUPLICATE_DATE", f"Duplicate actual date: {day}")
        if row.get("data_version") is not None:
            versions.add(str(row["data_version"]))
        if "date_key" in row and int(row["date_key"]) != int(day.strftime("%Y%m%d")):
            raise DemandError("INVALID_CALENDAR", f"Date key mismatch: {day}")
        for key, expected in (("day_of_week", day.isoweekday()), ("month", day.month), ("is_weekend", day.weekday() >= 5)):
            if key in row and (row[key] != expected or (key == "is_weekend" and not isinstance(row[key], bool))):
                raise DemandError("INVALID_CALENDAR", f"Calendar {key} mismatch: {day}")
        status, target = row["guest_data_status"], row.get("target_guests")
        if status not in STATUSES:
            raise DemandError("INVALID_STATUS", f"Unknown guest status: {day}")
        if status == "COMPLETE":
            if target is None:
                raise DemandError("INVALID_TARGET", f"COMPLETE date has no target: {day}")
            target = nonnegative(target, integer=True)
        elif target is not None:
            raise DemandError("INVALID_TARGET", f"Non-COMPLETE date must have a NULL target: {day}")
        indexed[day] = DailyTarget(day, target, status)
    if len(versions) > 1:
        raise DemandError("MIXED_VERSION", "Actual rows contain multiple data versions")
    if not indexed:
        raise DemandError("EMPTY_DATA", "No actual demand dates")
    result, day, last = [], min(indexed), max(indexed)
    while day <= last:
        result.append(indexed.get(day, DailyTarget(day, None, "MISSING")))
        day += timedelta(days=1)
    return tuple(result)

def validate_calendar(days, version):
    result, seen = [], set()
    for raw in days:
        row = asdict(raw) if isinstance(raw, CalendarDay) else dict(raw)
        day = local_date(row["full_date"])
        expected = CalendarDay.from_date(day, version)
        if day in seen or row.get("data_version") != version:
            raise DemandError("INVALID_CALENDAR", "Duplicate calendar date or incompatible version")
        if (row["day_of_week"], row["month"], row["is_weekend"]) != (expected.day_of_week, expected.month, expected.is_weekend) or not isinstance(row["is_weekend"], bool):
            raise DemandError("INVALID_CALENDAR", f"Incorrect horizon calendar: {day}")
        seen.add(day)
        result.append(expected)
    return tuple(sorted(result, key=lambda r: r.full_date))

def snapshot_payload(snapshot):
    result = asdict(snapshot)
    result.pop("snapshot_hash")
    return result

def make_snapshot(rows, *, data_version, extracted_at, source_checksums, quality, calendar, source_kind="postgresql", run_id=""):
    if not data_version or source_kind not in {"postgresql", "synthetic_fixture"}:
        raise DemandError("INVALID_PROVENANCE", "Data version and supported source kind required")
    try:
        if datetime.fromisoformat(extracted_at).utcoffset() is None:
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise DemandError("INVALID_PROVENANCE", "Extraction timestamp must be timezone-aware") from exc
    if set(source_checksums) != {"booking", "holiday", "weather"} or any(not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v) for v in source_checksums.values()):
        raise DemandError("INVALID_PROVENANCE", "Three pinned source SHA-256 values required")
    if quality.get("passed") is not True or quality.get("dw_quality", {}).get("passed") is not True:
        raise DemandError("QUALITY_FAILED", "DW and Mart quality must pass")
    if str(quality.get("data_version")) != data_version or str(quality.get("run_id")) != run_id:
        raise DemandError("MIXED_VERSION", "Quality evidence does not match snapshot run/version")
    raw_rows = list(rows)
    if any(str(r.get("data_version", data_version)) != data_version for r in raw_rows if isinstance(r, dict)):
        raise DemandError("MIXED_VERSION", "Actual row version differs from snapshot")
    snapshot = DemandSnapshot(normalize_rows(raw_rows), data_version, extracted_at, dict(source_checksums), quality,
                              validate_calendar(calendar, data_version), source_kind, run_id)
    return replace(snapshot, snapshot_hash=digest(snapshot_payload(snapshot)))

def save_snapshot(snapshot, path):
    write_json(Path(path), asdict(snapshot))

def load_snapshot(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = raw.pop("snapshot_hash")
    if digest(raw) != expected:
        raise DemandError("CORRUPT_SNAPSHOT", "Snapshot content hash mismatch")
    snapshot = make_snapshot(**raw)
    if snapshot.snapshot_hash != expected:
        raise DemandError("CORRUPT_SNAPSHOT", "Snapshot is not canonical")
    return snapshot

def extract_snapshot(dw_config=None, dbname=None):
    """Quality and extraction share one repeatable-read, read-only transaction."""
    import psycopg
    from psycopg.rows import dict_row
    from pipeline.source_to_staging.common import connect
    from pipeline.staging_to_dw.config import DEFAULT_CONFIG, load_config
    from pipeline.staging_to_dw.checks import validate_loaded
    from pipeline.dw_to_mart.checks import validate_operations
    config = load_config(dw_config or DEFAULT_CONFIG)
    try:
        with connect(dbname) as conn, conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '120s'")
            active = conn.execute("SELECT run_id FROM dw.active_dataset WHERE singleton_id=1").fetchone()
            if not active:
                raise DemandError("QUALITY_FAILED", "No published DW dataset")
            dw = validate_loaded(conn, active[0], config)
            mart = validate_operations(conn, active[0], config)
            quality = {**mart, "dw_quality": dw, "passed": bool(dw["passed"] and mart["passed"]), "generated_at_utc": utc_now()}
            if not quality["passed"]:
                error = DemandError("QUALITY_FAILED", "DW/Mart checks failed; formal training stopped")
                error.quality = quality
                raise error
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM mart.dataset_state WHERE singleton_id=1")
                state = cur.fetchone()
                if state is None or state["dw_run_id"] != active[0]:
                    raise DemandError("MIXED_VERSION", "Mart state differs from active DW run")
                cur.execute("SELECT * FROM mart.daily_hotel_operations ORDER BY full_date")
                rows = cur.fetchall()
                cur.execute("SELECT full_date,day_of_week,month,is_weekend FROM dw.dim_date ORDER BY full_date")
                calendar = [{**r, "data_version": str(state["data_version"])} for r in cur.fetchall()]
                cur.execute("""SELECT s.source_id,s.source_file_sha256 FROM staging.load_batch_source s
                               JOIN dw.load_run r ON r.staging_batch_id=s.batch_id WHERE r.run_id=%s""", (active[0],))
                checksums = {r["source_id"]: r["source_file_sha256"] for r in cur.fetchall()}
            return make_snapshot(rows, data_version=str(state["data_version"]), extracted_at=utc_now(),
                                 source_checksums=checksums, quality=quality, calendar=calendar, run_id=str(active[0]))
    except psycopg.Error as exc:
        code = "SOURCE_NOT_READY" if exc.sqlstate in {"42P01", "3F000"} else "DATABASE_UNAVAILABLE"
        raise DemandError(code, f"PostgreSQL snapshot failed (SQLSTATE {exc.sqlstate})") from None
