"""Preflight uses real PostgreSQL and an exclusively owned disposable database."""

import csv
from datetime import date
import json
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from pipeline.source_to_staging.booking import BOOKING_FIELDS
from pipeline.source_to_staging.common import ROOT, connect, sha256, source_set
from pipeline.source_to_staging.run import run as load_staging
from pipeline.staging_to_dw.preflight import report
from test_dw_inputs import FIXTURE, assert_values, fixture_bundle


@pytest.fixture(scope="module")
def input_database():
    name = "dw_inputs_test_" + uuid4().hex[:12]
    with connect() as admin:
        admin.autocommit = True
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        with connect(name) as conn:
            conn.execute((ROOT / "database/staging/001_staging.sql").read_text(encoding="utf-8"))
        yield name
    finally:
        assert name.startswith("dw_inputs_test_") and len(name) == 27
        with connect() as admin:
            admin.autocommit = True
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def make_sources(tmp_path):
    booking = tmp_path / "booking.csv"
    with booking.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BOOKING_FIELDS)
        writer.writeheader()
        for item in FIXTURE["design_rows"]:
            values = {**FIXTURE["defaults"], **item}
            day = date.fromisoformat(item["date"])
            row = {field: "0" for field in BOOKING_FIELDS}
            row.update({"hotel": "City Hotel", "arrival_date_year": str(day.year), "arrival_date_month": "August",
                        "arrival_date_day_of_month": str(day.day), "arrival_date_week_number": "31",
                        "distribution_channel": "Direct", "market_segment": "Direct", "customer_type": "Transient",
                        "reserved_room_type": "A", "assigned_room_type": "K", "reservation_status": "Check-Out",
                        "reservation_status_date": day.isoformat(), "agent": "NULL", "company": "NULL"})
            for field in (*FIXTURE["defaults"], "country"):
                value = values.get(field)
                row[field] = ("NA" if field == "children" else "NULL") if value is None else str(value)
            writer.writerow(row)
    holiday = tmp_path / "holiday.csv"
    holiday.write_text("date,holiday_name,country,subdivision,scope,category,observed\n2017-08-01,Example,PT,,national,public,false\n", encoding="utf-8")
    weather = tmp_path / "weather.json"
    weather.write_text(json.dumps({"timezone": "Europe/Lisbon", "daily_units": {"temperature_2m_mean": "°C", "precipitation_sum": "mm"},
        "daily": {"time": ["2017-08-01", "2017-08-02", "2017-08-03"], "temperature_2m_mean": [20, 21, 22], "precipitation_sum": [0, 1, 0]}}), encoding="utf-8")
    manifest = {"contract_version": "dw-inputs-staging-test-v1", "sources": {
        sid: {"file": str(path), "sha256": sha256(path)} for sid, path in (("booking", booking), ("holiday", holiday), ("weather", weather))}}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_preflight_is_read_only_and_preserves_first_batch_lineage(input_database, tmp_path):
    manifest = make_sources(tmp_path)
    first = load_staging(manifest, dbname=input_database)
    bundle = fixture_bundle()
    bundle["config"]["calendar"] = {"start": "2017-08-01", "end": "2017-08-10"}
    contract, sources, fingerprint = source_set(manifest)
    bundle.update({"sources": sources, "source_set_fingerprint": fingerprint, "staging_contract": contract})
    bundle["coverage"]["source_checksums"] = {sid: spec["sha256"] for sid, spec in sources.items()}
    for interval in bundle["coverage"]["intervals"]:
        if interval["source_id"] == "weather":
            interval.update({"start": "2017-08-01", "end": "2017-08-03"})
    with connect(input_database) as conn:
        before = conn.execute("SELECT batch_id,published_at FROM staging.active_snapshot").fetchone()
        conn.rollback()
        result = report(conn, bundle)
        assert result["passed"] is True
        assert result["dw_ready"] is False
        assert result["booking"]["accepted_candidate_count"] == 6
        assert result["booking"]["rejected_candidate_count"] == 1
        assert result["snapshot"]["batch_id"].hex == first["batch_id"].replace("-", "")
        for row in result["booking"]["daily_measures"]:
            assert_values(row, FIXTURE["design_expected"][row["date"]])
        assert conn.execute("SELECT batch_id,published_at FROM staging.active_snapshot").fetchone() == before
        assert conn.execute("SELECT count(*) FROM information_schema.schemata WHERE schema_name IN ('dw','mart')").fetchone()[0] == 0
        conn.rollback()
        # PostgreSQL itself rejects writes inside the transaction mode used by report().
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                conn.execute("DELETE FROM staging.active_snapshot")
        stale = dict(bundle, source_set_fingerprint="0" * 64)
        with pytest.raises(ValueError, match="differs from selected manifest"):
            report(conn, stale)

    # Republish the same source bytes under a new contract; physical rows keep first batch.
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["contract_version"] = "dw-inputs-staging-test-v2"
    manifest.write_text(json.dumps(value), encoding="utf-8")
    second = load_staging(manifest, dbname=input_database)
    contract, sources, fingerprint = source_set(manifest)
    bundle.update({"sources": sources, "source_set_fingerprint": fingerprint, "staging_contract": contract})
    with connect(input_database) as conn:
        result = report(conn, bundle)
        assert result["passed"] is True
        assert result["first_batch_differs_from_active_rows"] == 7
        assert str(result["snapshot"]["batch_id"]) == second["batch_id"]
        conn.execute("UPDATE staging.stg_weather SET precipitation_sum=-1 WHERE _source_row_id=2")
        conn.commit()
        failed = report(conn, bundle)
        assert failed["passed"] is False
        assert failed["context"]["weather_complete_claim_failures"] == ["2017-08-02"]
        assert conn.execute("SELECT count(*) FROM staging.stg_booking").fetchone()[0] == 7
