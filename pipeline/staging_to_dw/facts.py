"""Explicit-column bulk writes for DW rows; caller owns transaction/publication."""

from __future__ import annotations

from psycopg import sql
from psycopg.types.json import Jsonb


FACT_COLUMNS = (
    "source_file_sha256", "source_row_id", "source_first_batch_id", "dw_run_id", "date_key", "country_key",
    "channel_key", "market_segment_key", "customer_profile_key", "reserved_room_type_key", "assigned_room_type_key",
    "country_raw", "booking_count", "is_canceled", "adults", "children", "babies", "total_guests", "guest_eligible",
    "stays_in_week_nights", "stays_in_weekend_nights", "total_stay_nights", "stay_eligible", "lead_time", "adr",
    "party_type", "party_eligible", "room_changed_flag", "room_comparison_eligible",
)
ISSUE_COLUMNS = ("run_id", "source_id", "source_file_sha256", "source_row_id", "local_date", "field_name",
                 "rule_code", "issue_type", "severity", "disposition", "raw_value", "reason")
REJECTION_COLUMNS = ("run_id", "source_file_sha256", "source_row_id", "arrival_date", "reason_codes")
COVERAGE_COLUMNS = ("run_id", "source_id", "local_date", "coverage_status", "evidence_ref", "evidence_sha256", "reason")


def insert_rows(cur, table: str, columns: tuple[str, ...], rows: list[dict]) -> None:
    """Only callers supply controlled table/column constants; values stay parameterized."""
    if not rows:
        return
    query = sql.SQL("INSERT INTO dw.{} ({}) VALUES ({})").format(
        sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, columns)),
        sql.SQL(",").join(sql.Placeholder() for _ in columns))
    cur.executemany(query, [tuple(row[c] for c in columns) for row in rows])


def map_fact_keys(facts: list[dict], lookups: dict, run_id) -> list[dict]:
    output = []
    for candidate in facts:
        row = {**candidate, "dw_run_id": run_id}
        for key, table, fields in (
            ("country_key", "dim_country", ("country_code",)), ("channel_key", "dim_channel", ("channel_code",)),
            ("market_segment_key", "dim_market_segment", ("market_segment_code",)),
            ("customer_profile_key", "dim_customer_profile", ("customer_type_code", "repeat_status")),
            ("reserved_room_type_key", "dim_room_type", ("reserved_room_type_code",)),
            ("assigned_room_type_key", "dim_room_type", ("assigned_room_type_code",)),
        ):
            row[key] = lookups[table][tuple(row[c] for c in fields)]
        output.append({c: row[c] for c in FACT_COLUMNS})
    return output


def insert_audit(cur, run_id, issues: list[dict], rejections: list[dict], coverage: list[dict]) -> None:
    insert_rows(cur, "row_issue", ISSUE_COLUMNS,
                [{**r, "run_id": run_id, "raw_value": Jsonb(r["raw_value"])} for r in issues])
    insert_rows(cur, "booking_rejection", REJECTION_COLUMNS, [{**r, "run_id": run_id} for r in rejections])
    insert_rows(cur, "source_coverage", COVERAGE_COLUMNS, [{**r, "run_id": run_id} for r in coverage])
