"""Integration tests use a uniquely named PostgreSQL database, never SQLite."""

import csv
import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from psycopg import sql

from pipeline.quality.staging_checks import report
from pipeline.source_to_staging.booking import BOOKING_FIELDS
from pipeline.source_to_staging.common import ROOT, connect, sha256
from pipeline.source_to_staging.run import run


@pytest.fixture(scope="module")
def test_database():
    name = "staging_test_" + uuid4().hex[:12]
    assert name.startswith("staging_test_") and len(name) == 25
    with connect() as admin:
        admin.autocommit = True
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        ddl = (ROOT / "database/staging/001_staging.sql").read_text(encoding="utf-8")
        with connect(name) as conn:
            conn.execute(ddl)
            conn.execute(ddl)  # migration rerun must be safe
        yield name
    finally:
        # Only the exact database created by this fixture can be removed.
        with connect() as admin:
            admin.autocommit = True
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def make_sources(tmp_path: Path) -> Path:
    booking_path = tmp_path / "booking.csv"
    base = {field: "X" for field in BOOKING_FIELDS}
    base.update({
        "hotel": "City Hotel", "is_canceled": "0", "lead_time": "1",
        "arrival_date_year": "2015", "arrival_date_month": "July",
        "arrival_date_week_number": "27", "arrival_date_day_of_month": "1",
        "stays_in_weekend_nights": "0", "stays_in_week_nights": "1",
        "adults": "2", "children": "NA", "babies": "0", "country": "NULL",
        "is_repeated_guest": "0", "previous_cancellations": "0",
        "previous_bookings_not_canceled": "0", "booking_changes": "0",
        "agent": "NULL", "company": "NULL", "days_in_waiting_list": "0",
        "adr": "76.5", "required_car_parking_spaces": "0",
        "total_of_special_requests": "0", "reservation_status_date": "2015-07-01",
    })
    resort = {**base, "hotel": "Resort Hotel"}
    invalid = {**base, "is_canceled": "2", "arrival_date_day_of_month": "32",
               "adults": "-1", "children": "not-a-number", "stays_in_week_nights": "-1"}
    zero = {**base, "children": "0", "adults": "0", "babies": "0",
            "arrival_date_day_of_month": "2"}
    with booking_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BOOKING_FIELDS)
        writer.writeheader()
        writer.writerows([resort, base, invalid, base, zero])
    holiday_path = tmp_path / "holiday.csv"
    with holiday_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "holiday_name", "country", "subdivision", "scope", "category", "observed"])
        writer.writeheader()
        writer.writerows([
            {"date": "2015-07-01", "holiday_name": "National example", "country": "PT", "subdivision": "", "scope": "national", "category": "public", "observed": "false"},
            {"date": "2015-07-01", "holiday_name": "Lisboa example", "country": "PT", "subdivision": "11", "scope": "Lisboa", "category": "public", "observed": "false"},
            {"date": "2015-02-30", "holiday_name": "Malformed example", "country": "PT", "subdivision": "11", "scope": "Mars", "category": "public", "observed": "maybe"},
        ])
    weather_path = tmp_path / "weather.json"
    weather_path.write_text(json.dumps({
        "timezone": "Europe/Lisbon",
        "daily_units": {"temperature_2m_mean": "°C", "precipitation_sum": "mm"},
        "daily": {"time": ["2015-07-01", "2015-07-01", "2015-07-02"],
                  "temperature_2m_mean": [19.1, 20.0, "bad"],
                  "precipitation_sum": [None, 5.0, 0.0]},
    }), encoding="utf-8")
    manifest = {
        "contract_version": "staging-test-v1",
        "sources": {
            "booking": {"file": str(booking_path), "sha256": sha256(booking_path),
                        "expected": {"raw_count": 5, "staged_count": 4, "out_of_scope_count": 1, "unidentified_count": 0}},
            "holiday": {"file": str(holiday_path), "sha256": sha256(holiday_path),
                        "expected": {"raw_count": 3, "staged_count": 3}},
            "weather": {"file": str(weather_path), "sha256": sha256(weather_path),
                        "expected": {"raw_count": 3, "staged_count": 3}},
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_load_rerun_failure_retry_and_quality(test_database, tmp_path):
    manifest_path = make_sources(tmp_path)
    first = run(manifest_path, dbname=test_database)
    assert first["status"] == "published"
    assert first["sources"]["booking"]["raw_count"] == 5
    with connect(test_database) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT _source_row_id FROM staging.v_booking_current ORDER BY _source_row_id")
            assert [row[0] for row in cur.fetchall()] == [3, 4, 5, 6]
            cur.execute("SELECT count(*) FROM staging.v_booking_current WHERE hotel <> 'City Hotel'")
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT children,country,raw_record->>'children' FROM staging.v_booking_current WHERE _source_row_id=3")
            assert cur.fetchone() == (None, None, "NA")
            cur.execute("SELECT arrival_date,is_canceled,adults,children,raw_record->>'children' FROM staging.v_booking_current WHERE _source_row_id=4")
            invalid_row = cur.fetchone()
            assert invalid_row == (None, 2, -1, None, "not-a-number")
            cur.execute("SELECT count(*) FROM staging.v_booking_current WHERE raw_record->>'children'='NA'")
            assert cur.fetchone()[0] == 2  # identical attributes but different raw positions
            cur.execute("SELECT count(*),count(DISTINCT date) FROM staging.v_holiday_current")
            assert cur.fetchone() == (3, 1)
            cur.execute("SELECT date,scope,observed,raw_record->>'date' FROM staging.v_holiday_current WHERE _source_row_id=4")
            assert cur.fetchone() == (None, "Mars", None, "2015-02-30")
            cur.execute("SELECT local_date,weather_ambiguous,precipitation_sum,is_holiday,is_weekend,array_length(holiday_names,1) FROM staging.v_daily_context_current ORDER BY local_date")
            context = cur.fetchall()
            assert context[0][1:] == (True, None, True, False, 2)
            assert context[1][1:] == (False, 0, None, False, None)
            cur.execute("SELECT precipitation_sum,raw_record->'precipitation_sum' FROM staging.v_weather_current WHERE _source_row_id=1")
            weather_null = cur.fetchone()
            assert weather_null[0] is None and weather_null[1] is None
            cur.execute("SELECT count(*) FROM staging.quality_issue WHERE batch_id=%s AND source_id='booking' AND rule_code='NUMERIC_PARSE_FAILED' AND raw_value='not-a-number'", (first["batch_id"],))
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT count(*) FROM staging.quality_issue WHERE batch_id=%s AND rule_code='WEATHER_DUPLICATE_DATE'", (first["batch_id"],))
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT count(*) FROM staging.quality_issue WHERE batch_id=%s AND source_id='holiday' AND issue_type='invalid'", (first["batch_id"],))
            assert cur.fetchone()[0] >= 3
        quality = report(conn)
        assert quality["passed"] is True
        assert quality["database_version"].startswith("17.")
    assert run(manifest_path, dbname=test_database)["status"] == "no-op"

    # Same source bytes, changed contract version: failed attempt cannot change active data.
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["contract_version"] = "staging-test-v2"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Injected failure"):
        run(manifest_path, dbname=test_database, inject_failure_after="booking")
    with connect(test_database) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT batch_id FROM staging.active_snapshot")
            assert str(cur.fetchone()[0]) == first["batch_id"]
            cur.execute("SELECT count(*) FROM staging.stg_booking")
            assert cur.fetchone()[0] == 4
            cur.execute("SELECT count(*) FROM staging.load_batch WHERE status='failed'")
            assert cur.fetchone()[0] == 1
    retry = run(manifest_path, dbname=test_database)
    assert retry["status"] == "published" and retry["batch_id"] != first["batch_id"]
    with connect(test_database) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM staging.stg_booking")
            assert cur.fetchone()[0] == 4
            cur.execute("SELECT count(*) FROM staging.quality_issue WHERE batch_id=%s AND rule_code='MISSING_CHILDREN'", (retry["batch_id"],))
            assert cur.fetchone()[0] == 2

    stale_id = uuid4()
    with connect(test_database) as conn:
        conn.execute("INSERT INTO staging.load_batch(batch_id,source_set_fingerprint,contract_version,status) VALUES (%s,%s,%s,'loading')",
                     (stale_id, "f" * 64, "stale-test"))
    assert run(manifest_path, dbname=test_database)["status"] == "no-op"
    with connect(test_database) as conn:
        row = conn.execute("SELECT status,error_summary FROM staging.load_batch WHERE batch_id=%s", (stale_id,)).fetchone()
        assert row == ("failed", "Interrupted before publication")

    # Structural error creates a failed batch/reject, without replacing the snapshot.
    bad = deepcopy(manifest)
    bad["contract_version"] = "staging-test-v3"
    weather_file = tmp_path / "bad-weather.json"
    weather_file.write_text(json.dumps({
        "timezone": "Europe/Lisbon",
        "daily_units": {"temperature_2m_mean": "°C", "precipitation_sum": "mm"},
        "daily": {"time": ["2015-07-01"], "temperature_2m_mean": [], "precipitation_sum": [0]},
    }), encoding="utf-8")
    bad["sources"]["weather"]["file"] = str(weather_file)
    bad["sources"]["weather"]["sha256"] = sha256(weather_file)
    bad_manifest = tmp_path / "bad-manifest.json"
    bad_manifest.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(Exception, match="Daily arrays are not aligned"):
        run(bad_manifest, dbname=test_database)
    with connect(test_database) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT batch_id FROM staging.active_snapshot")
            assert str(cur.fetchone()[0]) == retry["batch_id"]
            cur.execute("SELECT count(*) FROM staging.reject WHERE source_id='weather' AND rule_code='STRUCTURAL_READ_FAILURE'")
            assert cur.fetchone()[0] == 1

    wrong_hash = deepcopy(manifest)
    wrong_hash["contract_version"] = "staging-test-v4"
    wrong_hash["sources"]["booking"]["sha256"] = "0" * 64
    wrong_manifest = tmp_path / "wrong-hash-manifest.json"
    wrong_manifest.write_text(json.dumps(wrong_hash), encoding="utf-8")
    with pytest.raises(Exception, match="checksum differs"):
        run(wrong_manifest, dbname=test_database)
    with connect(test_database) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT batch_id FROM staging.active_snapshot")
            assert str(cur.fetchone()[0]) == retry["batch_id"]
            cur.execute("SELECT count(*) FROM staging.reject WHERE source_id='booking' AND reason LIKE '%checksum differs%'")
            assert cur.fetchone()[0] == 1
