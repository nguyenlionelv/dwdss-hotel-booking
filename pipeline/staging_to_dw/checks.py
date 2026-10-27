"""Independent source-key, dimension and SQL checks before DW publication."""

from __future__ import annotations

from collections import Counter
from datetime import date

from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from pipeline.source_to_staging.common import ROOT
from .dimensions import DIMENSIONS


SQL_CHECKS = ROOT / "database/validation/dw_checks.sql"


def validate_candidate_keys(snapshot, facts: list[dict], rejections: list[dict]) -> None:
    source = {(r["_source_file_sha256"], r["_source_row_id"]) for r in snapshot.bookings}
    accepted = {(r["source_file_sha256"], r["source_row_id"]) for r in facts}
    rejected = {(r["source_file_sha256"], r["source_row_id"]) for r in rejections}
    if len(accepted) != len(facts) or len(rejected) != len(rejections) or accepted & rejected or accepted | rejected != source:
        raise ValueError("Candidate fact/rejection keys do not partition the source snapshot")


def source_dimension_expectations(conn, run_id, mappings: dict) -> tuple[dict, dict]:
    """Derive natural codes from source raw tokens, independently of transformer output."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""SELECT b._source_file_sha256,b._source_row_id,b.raw_record,b.is_repeated_guest,
                              coalesce(i.bad,'{}'::text[]) AS bad
                       FROM dw.load_run r JOIN staging.load_batch_source bs
                         ON bs.batch_id=r.staging_batch_id AND bs.source_id='booking'
                       JOIN staging.stg_booking b ON b._source_file_sha256=bs.source_file_sha256
                       LEFT JOIN (SELECT source_file_sha256,source_row_id,array_agg(DISTINCT field) AS bad
                                  FROM staging.quality_issue WHERE batch_id=(SELECT staging_batch_id FROM dw.load_run WHERE run_id=%s)
                                    AND source_id='booking' AND issue_type='invalid' AND rule_code<>'ZERO_GUESTS'
                                  GROUP BY source_file_sha256,source_row_id) i
                         ON i.source_file_sha256=b._source_file_sha256 AND i.source_row_id=b._source_row_id
                       WHERE r.run_id=%s AND b.arrival_date IS NOT NULL AND b.is_canceled IN (0,1)
                         AND NOT (coalesce(i.bad,'{}'::text[]) &&
                           ARRAY['arrival_date','arrival_date_year','arrival_date_month','arrival_date_day_of_month','is_canceled'])""", (run_id, run_id))
        source = cur.fetchall()
    targets = {"dim_country": {("UNK",)}, "dim_channel": {("UNKNOWN",)}, "dim_market_segment": {("UNKNOWN",)},
               "dim_customer_profile": {("UNKNOWN", "UNKNOWN")}, "dim_room_type": {("UNKNOWN",)}}
    per_source = {}
    for row in source:
        raw, bad = row["raw_record"], set(row["bad"])

        def code(field, name, unknown="UNKNOWN"):
            token = raw[field]
            if field in bad or token is None:
                return unknown
            match = mappings[name].get(token.strip().upper())
            return match["target_code"] if match else unknown

        country, channel, segment = code("country", "country", "UNK"), code("distribution_channel", "channel"), code("market_segment", "market_segment")
        kind = code("customer_type", "customer_type")
        repeat = {0: "NEW", 1: "REPEAT"}.get(row["is_repeated_guest"], "UNKNOWN") if "is_repeated_guest" not in bad else "UNKNOWN"
        reserved, assigned = code("reserved_room_type", "room_type"), code("assigned_room_type", "room_type")
        values = (country, channel, segment, kind, repeat, reserved, assigned)
        per_source[(row["_source_file_sha256"], row["_source_row_id"])] = values
        targets["dim_country"].add((country,))
        targets["dim_channel"].add((channel,))
        targets["dim_market_segment"].add((segment,))
        targets["dim_customer_profile"].add((kind, repeat))
        targets["dim_room_type"].update(((reserved,), (assigned,)))
    return targets, per_source


def validate_loaded(conn, run_id, bundle: dict) -> dict:
    """Use inside the caller's stable transaction; run may still be loading."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT run_id,data_version,staging_batch_id,config_sha256,source_set_fingerprint FROM dw.load_run WHERE run_id=%s", (run_id,))
        run = cur.fetchone()
    if not run:
        raise ValueError("DW run does not exist")
    if run["config_sha256"] != bundle["config_sha256"] or run["source_set_fingerprint"] != bundle["source_set_fingerprint"]:
        raise ValueError("Quality check requires the config/source selection used to build this DW run")
    violations = dict(conn.execute(SQL_CHECKS.read_text(encoding="utf-8"), {"run_id": run_id, "coverage": Jsonb(bundle["coverage"])}).fetchall())
    calendar = bundle["config"]["calendar"]
    expected_dates = {r[0] for r in conn.execute("SELECT generate_series(%s::date,%s::date,interval '1 day')::date", (calendar["start"], calendar["end"]))}
    actual_dates = {r[0] for r in conn.execute("SELECT full_date FROM dw.dim_date")}
    violations["calendar_exact_set"] = len(expected_dates ^ actual_dates)
    targets, per_source = source_dimension_expectations(conn, run_id, bundle["mappings"])
    labels = {name: {r["target_code"]: r["target_name"] for r in rows.values()} for name, rows in bundle["mappings"].items()}
    for table, (key, natural, columns) in DIMENSIONS.items():
        rows = conn.execute(sql.SQL("SELECT {} FROM dw.{}").format(
            sql.SQL(",").join(map(sql.Identifier, (key, *columns))), sql.Identifier(table))).fetchall()
        actual = {tuple(row[1 + columns.index(field)] for field in natural) for row in rows}
        violations[f"{table}_exact_set"] = len(actual ^ targets[table])
        wrong = 0
        for row in rows:
            identifier, *values = row
            token = values[0]
            if table == "dim_customer_profile":
                name = labels["customer_type"][token]
                wrong += values[1] != name or (identifier == 0) != (token == "UNKNOWN" and values[2] == "UNKNOWN")
            else:
                mapping_name = {"dim_country": "country", "dim_channel": "channel", "dim_market_segment": "market_segment", "dim_room_type": "room_type"}[table]
                name = labels[mapping_name].get(token)
                if table == "dim_room_type":
                    name = name or None
                wrong += values[1] != name
        violations[f"{table}_labels"] = wrong
    rows = conn.execute("""SELECT f.source_file_sha256,f.source_row_id,c.country_code,ch.channel_code,m.market_segment_code,
                                  p.customer_type_code,p.repeat_status,rr.room_type_code,ar.room_type_code
                           FROM dw.fact_booking f JOIN dw.dim_country c USING(country_key) JOIN dw.dim_channel ch USING(channel_key)
                           JOIN dw.dim_market_segment m USING(market_segment_key) JOIN dw.dim_customer_profile p USING(customer_profile_key)
                           JOIN dw.dim_room_type rr ON rr.room_type_key=f.reserved_room_type_key
                           JOIN dw.dim_room_type ar ON ar.room_type_key=f.assigned_room_type_key""").fetchall()
    violations["fact_categorical_assignments"] = sum(per_source.get((r[0], r[1])) != tuple(r[2:]) for r in rows)
    counts = {}
    for table in ("fact_booking", "daily_hotel_context", "daily_data_quality", "dim_date", *DIMENSIONS):
        counts[table] = conn.execute(sql.SQL("SELECT count(*) FROM dw.{}").format(sql.Identifier(table))).fetchone()[0]
    counts["booking_rejection"] = conn.execute("SELECT count(*) FROM dw.booking_rejection WHERE run_id=%s", (run_id,)).fetchone()[0]
    counts["row_issue"] = conn.execute("SELECT count(*) FROM dw.row_issue WHERE run_id=%s", (run_id,)).fetchone()[0]
    actual = bundle["config"]["actual"]
    statuses = dict(conn.execute("""SELECT guest_data_status,count(*) FROM dw.daily_data_quality q JOIN dw.dim_date d USING(date_key)
                                   WHERE d.full_date BETWEEN %s AND %s GROUP BY guest_data_status""", (actual["start"], actual["end"])).fetchall())
    totals = conn.execute("""SELECT count(*) FILTER (WHERE is_canceled=0),count(*) FILTER (WHERE is_canceled=1),
                                    sum(total_guests) FILTER (WHERE is_canceled=0 AND guest_eligible),
                                    sum(total_stay_nights) FILTER (WHERE is_canceled=0 AND stay_eligible),
                                    sum(adr) FILTER (WHERE is_canceled=0 AND adr IS NOT NULL)
                             FROM dw.fact_booking""").fetchone()
    return {"passed": not any(violations.values()), "run_id": str(run_id), "data_version": str(run["data_version"]),
            "staging_batch_id": str(run["staging_batch_id"]), "checks": violations,
            "errors": [f"{name}: {n} violations" for name, n in violations.items() if n], "counts": counts,
            "actual_guest_quality_days": statuses, "observed_totals": dict(zip(
                ("non_canceled_bookings", "cancellations", "eligible_non_canceled_guests", "eligible_non_canceled_nights", "non_canceled_adr_sum"), totals))}
