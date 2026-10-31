"""Verify DW DDL, rollback and constraints on fixture-owned PostgreSQL databases."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from pipeline.source_to_staging.common import ROOT, connect
from pipeline.staging_to_dw.migrations import MIGRATION_DIR, MIGRATION_FILES, WRITER_LOCK, apply_dw_migrations


TABLES = {
    "schema_migration", "load_run", "active_dataset", "source_coverage", "row_issue", "booking_rejection",
    "dim_date", "dim_country", "dim_channel", "dim_market_segment", "dim_customer_profile", "dim_room_type",
    "fact_booking", "daily_hotel_context", "daily_data_quality",
}


@pytest.fixture(scope="module")
def database_factory():
    owned = []

    def create(*, staging=True):
        name = "dw_migration_test_" + uuid4().hex[:12]
        with connect() as admin:
            admin.autocommit = True
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        owned.append(name)
        if staging:
            with connect(name) as conn:
                conn.execute((ROOT / "database/staging/001_staging.sql").read_text(encoding="utf-8"))
        return name

    try:
        yield create
    finally:
        for name in owned:
            assert name.startswith("dw_migration_test_") and len(name) == 30
            with connect() as admin:
                admin.autocommit = True
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture(scope="module")
def migrated_database(database_factory):
    name = database_factory()
    with connect(name) as conn:
        first = apply_dw_migrations(conn)
        assert first["status"] == "applied" and first["applied"] == list(MIGRATION_FILES)
    return name


@pytest.fixture
def conn(migrated_database):
    connection = connect(migrated_database)
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


@pytest.fixture
def booking(conn):
    first_batch, active_batch, run_id = uuid4(), uuid4(), uuid4()
    source_sha = hashlib.sha256(b"DW migration synthetic booking fixture").hexdigest()
    for batch, fingerprint in ((first_batch, "a" * 64), (active_batch, "b" * 64)):
        conn.execute("""INSERT INTO staging.load_batch(batch_id,source_set_fingerprint,contract_version,status)
                        VALUES (%s,%s,'migration-fixture','published')""", (batch, fingerprint))
    conn.execute("""INSERT INTO staging.stg_booking
                    (_source_file,_source_file_sha256,_source_row_id,_batch_id,raw_record,hotel,arrival_date)
                    VALUES ('synthetic-fixture',%s,2,%s,%s,'City Hotel','2016-01-01')""",
                 (source_sha, first_batch, Jsonb({"fixture": "migration"})))
    conn.execute("""INSERT INTO dw.load_run
                    (run_id,data_version,staging_batch_id,source_set_fingerprint,build_fingerprint,
                     contract_version,code_version,mapping_versions,config_sha256,status)
                    VALUES (%s,%s,%s,%s,%s,'dw-fixture','test',%s,%s,'loading')""",
                 (run_id, uuid4(), active_batch, "b" * 64, "c" * 64, Jsonb({}), "d" * 64))
    conn.execute("""INSERT INTO dw.dim_date
                    (date_key,full_date,year,quarter,month,day_of_month,iso_year,iso_week,day_of_week,day_name,month_name,is_weekend)
                    VALUES (20160101,'2016-01-01',2016,1,1,1,2015,53,5,'Friday','January',false)""")
    room_a = conn.execute("""INSERT INTO dw.dim_room_type(room_type_code,is_unknown)
                             VALUES ('A',false) RETURNING room_type_key""").fetchone()[0]
    room_b = conn.execute("""INSERT INTO dw.dim_room_type(room_type_code,is_unknown)
                             VALUES ('B',false) RETURNING room_type_key""").fetchone()[0]
    return {
        "source_file_sha256": source_sha, "source_row_id": 2, "source_first_batch_id": first_batch,
        "dw_run_id": run_id, "date_key": 20160101, "country_key": 0, "channel_key": 0,
        "market_segment_key": 0, "customer_profile_key": 0,
        "reserved_room_type_key": room_a, "assigned_room_type_key": room_a,
        "booking_count": 1, "is_canceled": 0, "adults": 2, "children": 1, "babies": 0,
        "total_guests": 3, "guest_eligible": True,
        "stays_in_week_nights": 2, "stays_in_weekend_nights": 0, "total_stay_nights": 2, "stay_eligible": True,
        "lead_time": 10, "adr": Decimal("123.45678901234567890123456789012345"),
        "party_type": "FAMILY", "party_eligible": True, "room_changed_flag": False, "room_comparison_eligible": True,
        "_active_batch": active_batch, "_room_b": room_b,
    }


def insert_row(conn, table, values):
    columns = [name for name in values if not name.startswith("_")]
    query = sql.SQL("INSERT INTO dw.{} ({}) VALUES ({})").format(
        sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, columns)),
        sql.SQL(",").join(sql.Placeholder() for _ in columns))
    conn.execute(query, tuple(values[name] for name in columns))


def test_inventory_unknowns_types_indexes_and_rerun(conn):
    conn.rollback()
    before = conn.execute("SELECT version,file_sha256,applied_at FROM dw.schema_migration ORDER BY version").fetchall()
    conn.rollback()
    rerun = apply_dw_migrations(conn)
    assert rerun["status"] == "no-op" and rerun["skipped"] == list(MIGRATION_FILES)
    assert conn.execute("SELECT version,file_sha256,applied_at FROM dw.schema_migration ORDER BY version").fetchall() == before
    tables = {r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='dw'")}
    assert tables == TABLES
    for table, key in (("dim_country", "country_key"), ("dim_channel", "channel_key"),
                       ("dim_market_segment", "market_segment_key"), ("dim_customer_profile", "customer_profile_key"),
                       ("dim_room_type", "room_type_key")):
        assert conn.execute(sql.SQL("SELECT {},is_unknown FROM dw.{}").format(sql.Identifier(key), sql.Identifier(table))).fetchall() == [(0, True)]
    assert conn.execute("SELECT count(*) FROM dw.dim_date").fetchone()[0] == 0
    columns = dict(conn.execute("""SELECT column_name,data_type FROM information_schema.columns
                                   WHERE table_schema='dw' AND table_name='fact_booking'"""))
    assert len(columns) == 31 and columns["adr"] == "numeric" and columns["total_guests"] == "bigint"
    fks = conn.execute("SELECT count(*) FROM pg_constraint WHERE conrelid='dw.fact_booking'::regclass AND contype='f'").fetchone()[0]
    assert fks == 10  # 7 dimension roles + run + first batch + compound source key.
    indexes = {r[0] for r in conn.execute("SELECT indexname FROM pg_indexes WHERE schemaname='dw' AND tablename='fact_booking'")}
    assert {"ix_fact_date", "ix_fact_country_date", "ix_fact_channel_date", "ix_fact_segment_date", "ix_fact_profile_date",
            "ix_fact_reserved_room_date", "ix_fact_assigned_room_date", "ix_fact_run", "ix_fact_first_batch"} <= indexes


def test_atomic_failure_checksum_guard_and_ledger_order(database_factory, tmp_path):
    name = database_factory()
    copied = tmp_path / "dw_sql"
    shutil.copytree(MIGRATION_DIR, copied)
    with (copied / MIGRATION_FILES[-1]).open("a", encoding="utf-8") as handle:
        handle.write("\nSELECT 1/0;\n")
    with connect(name) as connection:
        with pytest.raises(psycopg.errors.DivisionByZero):
            apply_dw_migrations(connection, copied)
        assert connection.execute("SELECT to_regnamespace('dw')").fetchone()[0] is None
        assert connection.execute("SELECT to_regclass('staging.stg_booking') IS NOT NULL").fetchone()[0] is True
        connection.rollback()
        apply_dw_migrations(connection)
        before = connection.execute("SELECT version,file_sha256,applied_at FROM dw.schema_migration ORDER BY version").fetchall()
        connection.rollback()
        with pytest.raises(ValueError, match="checksum mismatch"):
            apply_dw_migrations(connection, copied)
        assert connection.execute("SELECT version,file_sha256,applied_at FROM dw.schema_migration ORDER BY version").fetchall() == before
        connection.execute("INSERT INTO dw.schema_migration(version,file_sha256) VALUES ('999_unknown.sql',%s)", ("f" * 64,))
        connection.commit()
        with pytest.raises(ValueError, match="known ordered prefix"):
            apply_dw_migrations(connection)
    partial_name = database_factory()
    with connect(partial_name) as connection:
        control = (MIGRATION_DIR / MIGRATION_FILES[0]).read_bytes()
        connection.execute(control.decode("utf-8"))
        connection.execute("INSERT INTO dw.schema_migration(version,file_sha256) VALUES (%s,%s)",
                           (MIGRATION_FILES[0], hashlib.sha256(control).hexdigest()))
        connection.commit()
        with pytest.raises(psycopg.errors.DivisionByZero):
            apply_dw_migrations(connection, copied)
        assert connection.execute("SELECT version FROM dw.schema_migration").fetchall() == [(MIGRATION_FILES[0],)]
        assert connection.execute("SELECT to_regclass('dw.dim_country')").fetchone()[0] is None
        connection.rollback()
        upgraded = apply_dw_migrations(connection)
        assert upgraded["skipped"] == [MIGRATION_FILES[0]] and upgraded["applied"] == list(MIGRATION_FILES[1:])


def test_missing_staging_and_untracked_dw_fail_safely(database_factory):
    name = database_factory(staging=False)
    with connect(name) as connection:
        with pytest.raises(ValueError, match="Staging schema"):
            apply_dw_migrations(connection)
        assert connection.execute("SELECT to_regnamespace('dw')").fetchone()[0] is None
    name = database_factory()
    with connect(name) as connection:
        connection.execute("CREATE SCHEMA dw")
        connection.commit()
        with pytest.raises(ValueError, match="without a migration ledger"):
            apply_dw_migrations(connection)
        assert connection.execute("SELECT count(*) FROM pg_tables WHERE schemaname='dw'").fetchone()[0] == 0


def test_parallel_setup_serializes_on_the_shared_writer_lock(database_factory):
    name = database_factory()

    def setup():
        with connect(name) as connection:
            return apply_dw_migrations(connection)["status"]

    with connect(name) as holder:
        holder.execute("SELECT pg_advisory_xact_lock(%s)", (WRITER_LOCK,))
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(setup) for _ in range(2)]
            holder.commit()
            assert sorted(f.result(timeout=30) for f in futures) == ["applied", "no-op"]
    with connect(name) as connection:
        assert connection.execute("SELECT count(*) FROM dw.schema_migration").fetchone()[0] == 3


@pytest.mark.parametrize("overrides", [
    {"booking_count": 0}, {"is_canceled": 2}, {"adults": -1}, {"lead_time": -1},
    {"children": None}, {"total_guests": None}, {"total_guests": 99}, {"guest_eligible": False},
    {"stays_in_week_nights": None}, {"total_stay_nights": None}, {"total_stay_nights": 99}, {"stay_eligible": False},
    {"adr": Decimal("NaN")}, {"adr": Decimal("Infinity")}, {"adr": Decimal("-Infinity")}, {"adr": Decimal("-0.01")},
    {"party_type": "COUPLE"}, {"party_eligible": False},
    {"room_changed_flag": None}, {"room_changed_flag": True},
    {"reserved_room_type_key": 0}, {"room_comparison_eligible": False},
])
def test_fact_rejects_inconsistent_or_nonfinite_values(conn, booking, overrides):
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            insert_row(conn, "fact_booking", {**booking, **overrides})


def test_fact_accepts_missing_zero_bigint_precision_and_distinct_source_rows(conn, booking):
    insert_row(conn, "fact_booking", booking)
    assert conn.execute("SELECT adr FROM dw.fact_booking").fetchone()[0] == booking["adr"]
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction():
            insert_row(conn, "fact_booking", booking)
    conn.execute("DELETE FROM dw.fact_booking")
    missing = {**booking, "children": None, "total_guests": None, "guest_eligible": False,
               "party_type": "UNKNOWN", "party_eligible": False,
               "stays_in_week_nights": None, "total_stay_nights": None, "stay_eligible": False,
               "reserved_room_type_key": 0, "assigned_room_type_key": 0,
               "room_changed_flag": None, "room_comparison_eligible": False}
    insert_row(conn, "fact_booking", missing)
    conn.execute("DELETE FROM dw.fact_booking")
    zero = {**booking, "adults": 0, "children": 0, "babies": 0, "total_guests": 0, "guest_eligible": False,
            "party_type": "UNKNOWN", "party_eligible": False, "stays_in_week_nights": 0, "total_stay_nights": 0, "adr": Decimal(0)}
    insert_row(conn, "fact_booking", zero)
    conn.execute("DELETE FROM dw.fact_booking")
    large = {**booking, "adults": 2147483647, "children": 2147483647, "babies": 2147483647, "total_guests": 6442450941,
             "stays_in_week_nights": 2147483647, "stays_in_weekend_nights": 2147483647, "total_stay_nights": 4294967294}
    insert_row(conn, "fact_booking", large)
    conn.execute("""INSERT INTO staging.stg_booking
                    (_source_file,_source_file_sha256,_source_row_id,_batch_id,raw_record,hotel)
                    VALUES ('synthetic-fixture',%s,3,%s,'{}','City Hotel')""", (booking["source_file_sha256"], booking["source_first_batch_id"]))
    insert_row(conn, "fact_booking", {**large, "source_row_id": 3})
    assert conn.execute("SELECT count(*),sum(total_guests) FROM dw.fact_booking").fetchone() == (2, Decimal("12884901882"))


def test_first_batch_foreign_keys_and_integer_bounds(conn, booking):
    for overrides in ({"source_first_batch_id": booking["_active_batch"]}, {"source_row_id": 999},
                      {"date_key": 999}, {"country_key": 999}, {"channel_key": 999}, {"market_segment_key": 999},
                      {"customer_profile_key": 999}, {"reserved_room_type_key": 999, "room_changed_flag": True},
                      {"assigned_room_type_key": 999, "room_changed_flag": True}, {"dw_run_id": uuid4()}):
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with conn.transaction():
                insert_row(conn, "fact_booking", {**booking, **overrides})
    with pytest.raises(psycopg.errors.NumericValueOutOfRange):
        with conn.transaction():
            insert_row(conn, "fact_booking", {**booking, "adults": 2147483648})
    insert_row(conn, "fact_booking", {**booking, "assigned_room_type_key": booking["_room_b"], "room_changed_flag": True})
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with conn.transaction():
            conn.execute("UPDATE dw.fact_booking SET source_first_batch_id=%s", (booking["_active_batch"],))


def test_calendar_profile_and_unknown_member_constraints(conn, booking):
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute("UPDATE dw.dim_date SET iso_year=2016 WHERE date_key=20160101")
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute("UPDATE dw.dim_date SET day_name='Thursday' WHERE date_key=20160101")
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute("UPDATE dw.dim_country SET is_unknown=false WHERE country_key=0")
    conn.execute("""INSERT INTO dw.dim_customer_profile
                    (customer_type_code,customer_type_name,repeat_status,is_repeated_guest,is_unknown)
                    VALUES ('UNKNOWN','Unknown','REPEAT',true,false), ('TRANSIENT','Transient','UNKNOWN',NULL,false)""")
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute("""INSERT INTO dw.dim_customer_profile
                            (customer_type_code,customer_type_name,repeat_status,is_repeated_guest,is_unknown)
                            VALUES ('TRANSIENT','Transient','NEW',NULL,false)""")
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction():
            conn.execute("INSERT INTO dw.dim_room_type(room_type_code,is_unknown) VALUES ('A',false)")


def context_values(booking):
    return {"date_key": booking["date_key"], "dw_run_id": booking["dw_run_id"],
            "is_holiday": None, "has_national_holiday": False, "has_lisboa_holiday": None,
            "holiday_names": [], "holiday_record_count": 0, "holiday_data_status": "PARTIAL",
            "holiday_source_sha256": "e" * 64, "temperature_mean": Decimal("-1.25"), "precipitation": Decimal(0),
            "temperature_status": "COMPLETE", "precipitation_status": "COMPLETE", "weather_record_count": 1,
            "weather_ambiguous": False, "weather_source_sha256": "f" * 64}


@pytest.mark.parametrize("overrides", [
    {"is_holiday": False}, {"holiday_data_status": "COMPLETE"},
    {"holiday_record_count": 1}, {"precipitation": Decimal("-1")},
    {"temperature_mean": Decimal("NaN")}, {"precipitation": Decimal("Infinity")},
    {"temperature_mean": None}, {"precipitation_status": "INVALID"},
    {"weather_record_count": 2}, {"weather_ambiguous": True}, {"temperature_status": "AMBIGUOUS"},
])
def test_context_rejects_false_nonholiday_or_invalid_weather(conn, booking, overrides):
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            insert_row(conn, "daily_hotel_context", {**context_values(booking), **overrides})


def test_context_three_value_holiday_and_ambiguous_weather(conn, booking):
    values = context_values(booking)
    insert_row(conn, "daily_hotel_context", values)
    assert conn.execute("SELECT is_holiday,precipitation FROM dw.daily_hotel_context").fetchone() == (None, Decimal(0))
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction():
            insert_row(conn, "daily_hotel_context", values)
    conn.execute("DELETE FROM dw.daily_hotel_context")
    insert_row(conn, "daily_hotel_context", {**values, "is_holiday": True, "has_national_holiday": True,
        "holiday_record_count": 1, "holiday_names": ["National example"],
        "weather_record_count": 2, "weather_ambiguous": True, "temperature_mean": None, "precipitation": None,
        "temperature_status": "AMBIGUOUS", "precipitation_status": "AMBIGUOUS"})
    assert conn.execute("SELECT is_holiday,holiday_data_status,temperature_mean FROM dw.daily_hotel_context").fetchone() == (True, "PARTIAL", None)


@pytest.mark.parametrize("national,lisboa,combined", [
    (True, False, True), (False, True, True), (True, True, True),
    (False, False, False), (True, None, True), (False, None, None),
])
def test_holiday_scope_combinations(conn, booking, national, lisboa, combined):
    names = [name for name, flag in (("National example", national), ("Lisboa example", lisboa)) if flag is True]
    values = {**context_values(booking), "has_national_holiday": national, "has_lisboa_holiday": lisboa,
              "is_holiday": combined, "holiday_names": names, "holiday_record_count": len(names),
              "holiday_data_status": "COMPLETE" if national is not None and lisboa is not None else "PARTIAL"}
    insert_row(conn, "daily_hotel_context", values)
    assert conn.execute("SELECT has_national_holiday,has_lisboa_holiday,is_holiday FROM dw.daily_hotel_context").fetchone() == (national, lisboa, combined)


def quality_values(booking):
    names = ("source_booking_count", "fact_booking_count", "rejected_booking_count", "non_canceled_booking_count",
             "guest_ineligible_booking_count", "stay_ineligible_booking_count", "lead_time_unknown_booking_count",
             "adr_unknown_booking_count", "unknown_party_booking_count", "unknown_channel_booking_count",
             "unknown_segment_booking_count", "unknown_customer_type_booking_count", "unknown_repeat_booking_count", "room_ineligible_booking_count")
    return {**dict.fromkeys(names, 0), "date_key": booking["date_key"], "dw_run_id": booking["dw_run_id"],
            "booking_data_status": "UNKNOWN", "guest_data_status": "UNKNOWN", "stay_data_status": "UNKNOWN"}


def test_quality_rejections_and_active_publication_constraints(conn, booking):
    quality = quality_values(booking)
    insert_row(conn, "daily_data_quality", quality)  # Zero technical counts need not mean COMPLETE.
    for updates in ({"fact_booking_count": 1}, {"non_canceled_booking_count": 1}, {"source_booking_count": -1}):
        assignments = sql.SQL(",").join(sql.SQL("{}=%s").format(sql.Identifier(k)) for k in updates)
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.transaction():
                conn.execute(sql.SQL("UPDATE dw.daily_data_quality SET {}").format(assignments), tuple(updates.values()))
    conn.execute("DELETE FROM dw.daily_data_quality")
    dirty = {**quality, "source_booking_count": 1, "fact_booking_count": 1,
             "non_canceled_booking_count": 1, "guest_ineligible_booking_count": 1, "guest_data_status": "COMPLETE"}
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            insert_row(conn, "daily_data_quality", dirty)
    rejection = {"run_id": booking["dw_run_id"], "source_file_sha256": booking["source_file_sha256"],
                 "source_row_id": 2, "arrival_date": None, "reason_codes": ["UNKNOWN_DATE"]}
    for reasons in ([], [None], [""]):
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.transaction():
                insert_row(conn, "booking_rejection", {**rejection, "reason_codes": reasons})
    insert_row(conn, "booking_rejection", rejection)
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction():
            insert_row(conn, "booking_rejection", rejection)
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute("INSERT INTO dw.active_dataset(singleton_id,run_id) VALUES (1,%s)", (booking["dw_run_id"],))
    conn.execute("UPDATE dw.load_run SET status='published',finished_at=started_at WHERE run_id=%s", (booking["dw_run_id"],))
    conn.execute("INSERT INTO dw.active_dataset(singleton_id,run_id) VALUES (1,%s)", (booking["dw_run_id"],))
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute("UPDATE dw.load_run SET status='failed' WHERE run_id=%s", (booking["dw_run_id"],))


def test_control_coverage_issue_and_run_status_constraints(conn, booking):
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute("UPDATE dw.load_run SET status='published' WHERE run_id=%s", (booking["dw_run_id"],))
    coverage = {"run_id": booking["dw_run_id"], "source_id": "booking", "local_date": date(2016, 1, 1),
                "coverage_status": "COMPLETE", "evidence_ref": "fixture-decision.json", "evidence_sha256": "a" * 64}
    insert_row(conn, "source_coverage", coverage)
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction():
            insert_row(conn, "source_coverage", coverage)
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            insert_row(conn, "source_coverage", {**coverage, "local_date": date(2016, 1, 2), "evidence_sha256": None})
    issue = {"run_id": booking["dw_run_id"], "source_id": "booking", "source_file_sha256": booking["source_file_sha256"],
             "source_row_id": 2, "field_name": "children", "rule_code": "MISSING_CHILDREN", "issue_type": "missing",
             "severity": "warning", "disposition": "NULL_MEASURE", "raw_value": Jsonb("NA"), "reason": "Synthetic missing component"}
    insert_row(conn, "row_issue", issue)
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            insert_row(conn, "row_issue", {**issue, "source_file_sha256": None})
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            insert_row(conn, "row_issue", {**issue, "disposition": "SILENT_DROP"})


def test_setup_cli_preserves_staging_default_and_reports_dw(database_factory, tmp_path):
    name = database_factory(staging=False)
    command = [sys.executable, str(ROOT / "scripts/setup_db.py"), "--dbname", name]
    first = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    assert first.returncode == 0 and "Staging migration applied" in first.stdout
    path = tmp_path / "setup.json"
    dw = subprocess.run([*command, "--schema", "dw", "--report", str(path)], capture_output=True, text=True, cwd=ROOT)
    assert dw.returncode == 0 and json.loads(path.read_text(encoding="utf-8"))["status"] == "applied"
    original = path.read_bytes()
    repeat = subprocess.run([*command, "--schema", "dw", "--report", str(path)], capture_output=True, text=True, cwd=ROOT)
    assert repeat.returncode != 0 and path.read_bytes() == original
    no_op = subprocess.run([*command, "--schema", "dw"], capture_output=True, text=True, cwd=ROOT)
    assert no_op.returncode == 0 and json.loads(no_op.stdout)["status"] == "no-op"
