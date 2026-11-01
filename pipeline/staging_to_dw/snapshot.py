"""Read one published Staging snapshot under the caller's transaction and writer lock."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from psycopg import sql
from psycopg.rows import dict_row

from pipeline.source_to_staging.booking import BOOKING_FIELDS


@dataclass
class StagingSnapshot:
    header: dict
    sources: dict
    bookings: list[dict]
    holidays: list[dict]
    weather: list[dict]
    issues: list[dict]

    def booking_issues(self) -> dict:
        grouped = defaultdict(list)
        for issue in self.issues:
            if issue["source_id"] == "booking":
                grouped[(issue["source_file_sha256"], issue["source_row_id"])].append(issue)
        return grouped


def pin_published_snapshot(conn, bundle: dict) -> tuple[dict, dict]:
    """Caller starts REPEATABLE READ before this first query; never commits here."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""SELECT b.batch_id,b.status,b.source_set_fingerprint,b.contract_version,a.published_at
                       FROM staging.active_snapshot a JOIN staging.load_batch b ON b.batch_id=a.batch_id
                       WHERE a.singleton_id=1""")
        header = cur.fetchone()
        if not header or header["status"] != "published":
            raise ValueError("No published Staging snapshot")
        if (header["source_set_fingerprint"] != bundle["source_set_fingerprint"]
                or header["contract_version"] != bundle["staging_contract"]):
            raise ValueError("Published Staging snapshot differs from the selected manifest")
        cur.execute("""SELECT source_id,source_file_sha256,source_metadata,raw_count,staged_count,
                              out_of_scope_count,unidentified_count,reject_count
                       FROM staging.load_batch_source WHERE batch_id=%s ORDER BY source_id""", (header["batch_id"],))
        sources = {r["source_id"]: r for r in cur.fetchall()}
        if set(sources) != {"booking", "holiday", "weather"}:
            raise ValueError("Published snapshot must have exactly three registered sources")
        for sid, registered in sources.items():
            selected = bundle["sources"][sid]
            if registered["source_file_sha256"] != selected["sha256"]:
                raise ValueError(f"{sid}: selected checksum differs from snapshot registry")
            for key in ("timezone", "model", "daily_variables", "requested_coordinate", "returned_coordinate",
                        "country", "subdivision", "years", "observed", "generator_version", "hotel_scope"):
                if key in selected and registered["source_metadata"].get(key) != selected[key]:
                    raise ValueError(f"{sid}: selected metadata differs from registry ({key})")
            if registered["raw_count"] != sum(registered[k] for k in
                    ("staged_count", "out_of_scope_count", "unidentified_count", "reject_count")):
                raise ValueError(f"{sid}: source reconciliation failed")
            if registered["reject_count"] or registered["unidentified_count"]:
                raise ValueError(f"{sid}: unresolved structural/scope rejects")
            for key, expected in selected.get("expected", {}).items():
                if registered[key] != expected:
                    raise ValueError(f"{sid}: registry differs from manifest expected {key}")
        cur.execute("SELECT count(*) AS n FROM staging.reject WHERE batch_id=%s", (header["batch_id"],))
        if cur.fetchone()["n"]:
            raise ValueError("Published snapshot has structural rejects")
    return header, sources


def read_snapshot(conn, bundle: dict) -> StagingSnapshot:
    header, sources = pin_published_snapshot(conn, bundle)
    metadata = ("_source_id", "_source_file_sha256", "_source_row_id", "_batch_id", "raw_record")
    columns = {
        "booking": (*metadata, *BOOKING_FIELDS, "arrival_date"),
        "holiday": (*metadata, "date", "holiday_name", "country", "subdivision", "scope", "category", "observed"),
        "weather": (*metadata, "local_date", "temperature_2m_mean", "precipitation_sum"),
    }
    rows = {}
    with conn.cursor(row_factory=dict_row) as cur:
        for sid, names in columns.items():
            cur.execute(sql.SQL("SELECT {} FROM staging.{} ORDER BY _source_row_id").format(
                sql.SQL(",").join(map(sql.Identifier, names)), sql.Identifier(f"v_{sid}_current")))
            rows[sid] = cur.fetchall()
            if len(rows[sid]) != sources[sid]["staged_count"]:
                raise ValueError(f"{sid}: current view count differs from pinned registry")
            if any(r["_source_file_sha256"] != sources[sid]["source_file_sha256"] for r in rows[sid]):
                raise ValueError(f"{sid}: mixed source versions in current view")
        cur.execute("""SELECT batch_id,source_id,source_file_sha256,source_row_id,field,rule_code,
                              issue_type,severity,raw_value,reason
                       FROM staging.quality_issue WHERE batch_id=%s ORDER BY issue_id""", (header["batch_id"],))
        issues = cur.fetchall()
        source_keys = {sid: {r["_source_row_id"] for r in records} for sid, records in rows.items()}
        for issue in issues:
            sid = issue["source_id"]
            if (issue["source_file_sha256"] != sources[sid]["source_file_sha256"]
                    or issue["source_row_id"] not in source_keys[sid]):
                raise ValueError("Staging issue lineage is outside the pinned source rows")
        cur.execute("""SELECT count(*) AS n FROM staging.v_booking_current b
                       LEFT JOIN staging.load_batch_source s ON s.batch_id=b._batch_id
                        AND s.source_id='booking' AND s.source_file_sha256=b._source_file_sha256
                       WHERE s.batch_id IS NULL""")
        if cur.fetchone()["n"]:
            raise ValueError("Booking first-batch registry lineage is invalid")
    return StagingSnapshot(header, sources, rows["booking"], rows["holiday"], rows["weather"], issues)
