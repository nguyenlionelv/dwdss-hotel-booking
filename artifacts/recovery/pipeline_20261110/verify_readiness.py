"""Read-only handoff audit; run from the repository root after DW/Mart checks."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from psycopg.rows import dict_row
from pipeline.source_to_staging.common import connect


QUERIES = {
    "counts": """SELECT
        (SELECT count(*) FROM staging.v_booking_current) AS staging_booking,
        (SELECT count(*) FROM staging.v_holiday_current) AS staging_holiday,
        (SELECT count(*) FROM staging.v_weather_current) AS staging_weather,
        (SELECT count(*) FROM dw.fact_booking) AS fact_booking,
        (SELECT count(*) FROM dw.booking_rejection) AS booking_rejection,
        (SELECT count(*) FROM mart.daily_hotel_operations) AS mart_daily,
        (SELECT count(*) FROM mart.daily_hotel_operations_by_country) AS mart_country""",
    "guest_day_status": """SELECT guest_data_status,count(*) AS days
        FROM mart.daily_hotel_operations GROUP BY 1 ORDER BY 1""",
    "context": """SELECT count(*) AS days,min(full_date) AS first_date,max(full_date) AS last_date,
        count(*) FILTER (WHERE holiday_data_status='COMPLETE') AS holiday_complete,
        count(*) FILTER (WHERE temperature_status='COMPLETE' AND precipitation_status='COMPLETE') AS weather_complete,
        count(*) FILTER (WHERE is_holiday) AS holiday_days,
        count(*) FILTER (WHERE precipitation=0) AS valid_zero_precipitation_days,
        count(*) FILTER (WHERE target_guests IS NULL) AS null_target_days,
        count(*) FILTER (WHERE target_guests=0) AS valid_zero_target_days,
        count(*) FILTER (WHERE target_guests IS DISTINCT FROM
          CASE WHEN guest_data_status='COMPLETE' THEN observed_total_guests END) AS target_rule_violations
        FROM mart.daily_hotel_operations""",
    "lineage": """SELECT count(*) AS facts_after_source_and_context_join,
        count(DISTINCT (f.source_file_sha256,f.source_row_id)) AS distinct_source_keys,
        count(*) FILTER (WHERE s._source_row_id IS NULL) AS missing_source_rows,
        count(*) FILTER (WHERE f.source_first_batch_id IS DISTINCT FROM s._batch_id) AS first_batch_mismatch,
        count(*) FILTER (WHERE s.children IS NULL AND f.children IS NOT NULL) AS imputed_children,
        count(*) FILTER (WHERE f.children=0) AS valid_zero_children,
        count(*) FILTER (WHERE f.children IS NULL) AS null_children
        FROM dw.fact_booking f
        LEFT JOIN staging.v_booking_current s ON s._source_file_sha256=f.source_file_sha256
          AND s._source_row_id=f.source_row_id
        JOIN dw.daily_hotel_context c USING (date_key)""",
    "otb_attributes": """SELECT count(*) AS rows_with_raw_booking_fields
        FROM staging.v_booking_current WHERE raw_record ?&
          ARRAY['lead_time','arrival_date_year','arrival_date_month','arrival_date_day_of_month',
          'reservation_status','reservation_status_date','booking_changes','adults','children','babies']""",
    "published_sources": """SELECT source_id,source_file_sha256,raw_count,staged_count,reject_count
        FROM staging.load_batch_source WHERE batch_id=(SELECT batch_id FROM staging.active_snapshot)
        ORDER BY source_id""",
    "mart_state": "SELECT dw_run_id,data_version,row_counts FROM mart.dataset_state",
}


def main():
    result = {}
    with connect() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        with conn.cursor(row_factory=dict_row) as cur:
            for name, query in QUERIES.items():
                cur.execute(query)
                result[name] = cur.fetchall()
    counts, context, lineage = (result[k][0] for k in ("counts", "context", "lineage"))
    result["checks"] = {
        "staging_counts": [counts[k] for k in ("staging_booking", "staging_holiday", "staging_weather")] == [79330, 38, 793],
        "booking_reconciles": counts["staging_booking"] == counts["fact_booking"] + counts["booking_rejection"],
        "mart_calendar": counts["mart_daily"] == context["days"] == 793,
        "complete_context": context["holiday_complete"] == context["weather_complete"] == 793,
        "target_rule": context["target_rule_violations"] == 0,
        "partial_targets_remain_null": context["null_target_days"] == sum(r["days"] for r in result["guest_day_status"] if r["guest_data_status"] != "COMPLETE"),
        "join_does_not_duplicate": lineage["facts_after_source_and_context_join"] == lineage["distinct_source_keys"] == counts["fact_booking"],
        "lineage": lineage["missing_source_rows"] == lineage["first_batch_mismatch"] == 0,
        "no_children_imputation": lineage["imputed_children"] == 0,
        "booking_attributes_retained": result["otb_attributes"][0]["rows_with_raw_booking_fields"] == counts["staging_booking"],
    }
    result["passed"] = all(result["checks"].values())
    path = Path(__file__).with_name("readiness.json")
    with path.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, default=str)
        handle.write("\n")
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
