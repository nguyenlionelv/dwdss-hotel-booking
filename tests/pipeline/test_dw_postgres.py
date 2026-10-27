"""Full DW load tests use real PostgreSQL and exclusively owned disposable databases."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from psycopg import sql
import pytest

from pipeline.quality.dw_checks import report
from pipeline.source_to_staging.common import ROOT, connect, sha256
from pipeline.source_to_staging.run import run as stage
from pipeline.staging_to_dw.config import DEFAULT_CONFIG, load_config
from pipeline.staging_to_dw.migrations import WRITER_LOCK, apply_dw_migrations
from pipeline.staging_to_dw.run import run
from pipeline.staging_to_dw.snapshot import read_snapshot
from test_dw_inputs_postgres import make_sources


@pytest.fixture
def database():
    name = "dw_loader_test_" + uuid4().hex[:12]
    with connect() as admin:
        admin.autocommit = True
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        with connect(name) as conn:
            conn.execute((ROOT / "database/staging/001_staging.sql").read_text(encoding="utf-8"))
            conn.commit()
            apply_dw_migrations(conn)
        yield name
    finally:
        assert name.startswith("dw_loader_test_") and len(name) == 27
        with connect() as admin:
            admin.autocommit = True
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def config_for(tmp_path, manifest):
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    selected = json.loads(manifest.read_text(encoding="utf-8"))
    config.update(source_manifest=str(manifest), calendar={"start":"2017-08-01","end":"2017-08-10","label_language":"en"},
                  actual={"start":"2017-08-01","end":"2017-08-03"}, data_coverage_end="2017-08-03")
    evidence = tmp_path / "fixture_evidence.json"
    write_json(evidence, {"kind":"synthetic_fixture", "statement":"Full capture/calendar is assumed only for the three fixture days"})
    coverage = {"version":"fixture-coverage-v1", "default_status":"UNKNOWN",
                "source_checksums":{sid:spec["sha256"] for sid,spec in selected["sources"].items()},
                "intervals":[{"source_id":sid,"scope":scope,"start":"2017-08-01","end":"2017-08-03", "status":"COMPLETE",
                              "reason":"Explicit synthetic fixture assumption", "evidence":{"file":str(evidence),"sha256":sha256(evidence)}}
                             for sid,scope in (("booking","all"),("holiday","national"),("holiday","Lisboa"),("weather","all"))]}
    coverage_path = tmp_path / "coverage.json"
    write_json(coverage_path, coverage)
    config["coverage"] = {"file":str(coverage_path),"sha256":sha256(coverage_path)}
    path = tmp_path / "dw.json"
    write_json(path, config)
    return path


def change_config(path, version):
    config = json.loads(path.read_text(encoding="utf-8"))
    config["config_version"] = version
    write_json(path, config)


def active_state(name):
    with connect(name) as conn:
        active = conn.execute("SELECT run_id,published_at FROM dw.active_dataset").fetchone()
        facts = conn.execute("SELECT source_file_sha256,source_row_id,total_guests,guest_eligible,dw_run_id FROM dw.fact_booking ORDER BY source_row_id").fetchall()
        return active, facts


def test_one_command_dw_runner_publishes_and_reruns_on_postgres(database, tmp_path):
    manifest = make_sources(tmp_path)
    staged = stage(manifest, dbname=database)
    config = config_for(tmp_path, manifest)
    summaries = []
    for index in range(2):
        output = tmp_path / f"runner_{index}"
        child = subprocess.run([sys.executable, str(ROOT / "scripts/run_dw.py"), "--config", str(config),
                                "--dbname", database, "--output-dir", str(output)],
                               capture_output=True, text=True, cwd=ROOT)
        assert child.returncode == 0, child.stdout
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        assert summary["status"] == "completed" and summary["verified"] is True
        assert summary["tests_run"] is False and len(summary["steps"]) == 5
        assert summary["load_status"] == ("published" if index == 0 else "no-op")
        summaries.append(summary)
    assert summaries[0]["run_id"] == summaries[1]["run_id"]
    assert summaries[0]["data_version"] == summaries[1]["data_version"]
    with connect(database) as conn:
        assert conn.execute("SELECT count(*) FROM dw.fact_booking").fetchone()[0] == 6
        assert conn.execute("SELECT count(*) FROM dw.load_run").fetchone()[0] == 1
        assert str(conn.execute("SELECT batch_id FROM staging.active_snapshot").fetchone()[0]) == staged["batch_id"]


def test_first_load_rerun_daily_quality_and_exact_source_sets(database, tmp_path):
    manifest = make_sources(tmp_path)
    staging = stage(manifest, dbname=database)
    config = config_for(tmp_path, manifest)
    first = run(config, dbname=database)
    assert first["status"] == "published" and first["quality"]["passed"]
    assert first["counts"]["fact_booking"] == 6 and first["counts"]["booking_rejection"] == 1
    assert first["counts"]["dim_date"] == first["counts"]["daily_hotel_context"] == first["counts"]["daily_data_quality"] == 10
    assert first["counts"]["dim_country"] == 3 and first["counts"]["dim_room_type"] == 3
    assert first["counts"]["dim_customer_profile"] == 2
    assert first["quality"]["actual_guest_quality_days"] == {"COMPLETE":2,"PARTIAL":1}
    assert first["quality"]["observed_totals"]["eligible_non_canceled_guests"] == 6
    before = active_state(database)
    assert run(config, dbname=database)["status"] == "no-op" and active_state(database) == before
    with connect(database) as conn:
        assert conn.execute("SELECT count(*) FROM dw.load_run").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM dw.source_coverage").fetchone()[0] == 30
        assert conn.execute("SELECT count(*) FROM dw.fact_booking WHERE source_first_batch_id=%s", (staging["batch_id"],)).fetchone()[0] == 6
        assert conn.execute("SELECT source_row_id FROM dw.booking_rejection").fetchall() == [(8,)]
        assert conn.execute("""SELECT guest_data_status,guest_ineligible_booking_count FROM dw.daily_data_quality
                                WHERE date_key IN (20170801,20170802,20170803,20170804) ORDER BY date_key""").fetchall() == [
            ("COMPLETE",0),("PARTIAL",2),("COMPLETE",0),("UNKNOWN",0)]
        assert conn.execute("SELECT is_holiday,has_national_holiday,has_lisboa_holiday FROM dw.daily_hotel_context WHERE date_key=20170801").fetchone() == (True,True,False)
        assert conn.execute("SELECT precipitation,temperature_status FROM dw.daily_hotel_context WHERE date_key=20170804").fetchone() == (None,"UNKNOWN")
        conn.rollback()
        assert report(conn, load_config(config))["passed"] is True


@pytest.mark.parametrize("phase", ["transform","clear","dimensions","facts","context","validation","publish"])
def test_failure_rolls_back_and_retains_failed_audit(database, tmp_path, phase):
    manifest = make_sources(tmp_path)
    stage(manifest, dbname=database)
    config = config_for(tmp_path, manifest)
    first = run(config, dbname=database)
    before = active_state(database)
    change_config(config, "rollback-" + phase)
    with pytest.raises(RuntimeError, match="Injected failure"):
        run(config, dbname=database, inject_failure_after=phase)
    assert active_state(database) == before
    with connect(database) as conn:
        failed = conn.execute("SELECT run_id,status,error_summary FROM dw.load_run WHERE status='failed'").fetchone()
        assert failed and phase in failed[2]
        assert conn.execute("SELECT count(*) FROM dw.row_issue WHERE run_id=%s", (failed[0],)).fetchone()[0] > 0
        assert conn.execute("SELECT count(*) FROM dw.booking_rejection WHERE run_id=%s", (failed[0],)).fetchone()[0] == 1
        assert str(conn.execute("SELECT run_id FROM dw.active_dataset").fetchone()[0]) == first["run_id"]
    retry = run(config, dbname=database)
    assert retry["status"] == "published" and retry["data_version"] != first["data_version"]
    assert retry["counts"]["fact_booking"] == 6


def test_interrupted_run_is_recovered_without_losing_snapshot(database, tmp_path):
    manifest = make_sources(tmp_path)
    stage(manifest, dbname=database)
    config = config_for(tmp_path, manifest)
    run(config, dbname=database)
    before = active_state(database)
    change_config(config, "interrupt-v2")
    with pytest.raises(KeyboardInterrupt):
        run(config, dbname=database, inject_interruption_after="facts")
    assert active_state(database) == before
    with connect(database) as conn:
        assert conn.execute("SELECT count(*) FROM dw.load_run WHERE status='loading'").fetchone()[0] == 1
    assert run(config, dbname=database)["status"] == "published"
    with connect(database) as conn:
        assert conn.execute("SELECT count(*) FROM dw.load_run WHERE status='loading'").fetchone()[0] == 0
        assert conn.execute("SELECT error_summary FROM dw.load_run WHERE status='failed'").fetchone()[0] == "Interrupted before publication"


def test_snapshot_repeatable_read_and_first_batch_differ_from_active(database, tmp_path):
    manifest = make_sources(tmp_path)
    first_stage = stage(manifest, dbname=database)
    config = config_for(tmp_path, manifest)
    with connect(database) as reader:
        reader.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        first = read_snapshot(reader, load_config(config))
        selected = json.loads(manifest.read_text(encoding="utf-8"))
        selected["contract_version"] = "fixture-staging-v2"
        next_manifest = tmp_path / "manifest_v2.json"
        write_json(next_manifest, selected)
        new_stage = stage(next_manifest, dbname=database)
        again = read_snapshot(reader, load_config(config))
        assert first.header == again.header and first.bookings == again.bookings
        assert str(first.header["batch_id"]) == first_stage["batch_id"]
    config = config_for(tmp_path, next_manifest)
    loaded = run(config, dbname=database)
    assert loaded["staging_batch_id"] == new_stage["batch_id"]
    with connect(database) as conn:
        assert conn.execute("SELECT count(*) FROM dw.fact_booking WHERE source_first_batch_id=%s", (first_stage["batch_id"],)).fetchone()[0] == 6
        assert conn.execute("""SELECT count(*) FROM dw.fact_booking f JOIN dw.load_run r ON r.run_id=f.dw_run_id
                                WHERE f.source_first_batch_id<>r.staging_batch_id""").fetchone()[0] == 6


def test_rule_mapping_versions_and_historical_fingerprint_do_not_noop(database, tmp_path):
    manifest = make_sources(tmp_path)
    stage(manifest, dbname=database)
    config = config_for(tmp_path, manifest)
    original = config.read_bytes()
    first = run(config, dbname=database)
    selected = json.loads(original)
    selected["rule_version"] = "fixture-rules-v2"
    write_json(config, selected)
    second = run(config, dbname=database)
    assert second["build_fingerprint"] != first["build_fingerprint"]
    selected["mappings"]["country"]["version"] = "fixture-country-v2"
    write_json(config, selected)
    third = run(config, dbname=database)
    assert third["build_fingerprint"] != second["build_fingerprint"]
    config.write_bytes(original)
    historical = run(config, dbname=database)
    assert historical["status"] == "published" and historical["build_fingerprint"] == first["build_fingerprint"]
    assert historical["data_version"] != first["data_version"]
    assert historical["counts"]["fact_booking"] == 6


def changed_booking_manifest(manifest, tmp_path, updates):
    import csv
    selected = json.loads(manifest.read_text(encoding="utf-8"))
    original = Path(selected["sources"]["booking"]["file"])
    with original.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns, rows = reader.fieldnames, list(reader)
    rows[0].update(updates)
    changed = tmp_path / ("booking_" + uuid4().hex[:6] + ".csv")
    with changed.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    selected["sources"]["booking"].update(file=str(changed), sha256=sha256(changed))
    path = tmp_path / ("manifest_" + uuid4().hex[:6] + ".json")
    write_json(path, selected)
    return path


def test_new_source_replaces_snapshot_and_unknown_date_blocks_publish(database, tmp_path):
    manifest = make_sources(tmp_path)
    stage(manifest, dbname=database)
    config = config_for(tmp_path, manifest)
    initial = run(config, dbname=database)
    changed = changed_booking_manifest(manifest, tmp_path, {"adults":"4"})
    stage(changed, dbname=database)
    config = config_for(tmp_path, changed)
    newer = run(config, dbname=database)
    assert newer["counts"]["fact_booking"] == 6 and newer["data_version"] != initial["data_version"]
    assert newer["quality"]["observed_totals"]["eligible_non_canceled_guests"] == 8
    before = active_state(database)
    bad = changed_booking_manifest(changed, tmp_path, {"arrival_date_day_of_month":"32"})
    stage(bad, dbname=database)
    config = config_for(tmp_path, bad)
    with pytest.raises(ValueError, match="Unknown-date"):
        run(config, dbname=database)
    assert active_state(database) == before
    with connect(database) as conn:
        failed = conn.execute("SELECT run_id FROM dw.load_run WHERE status='failed'").fetchone()[0]
        assert conn.execute("SELECT count(*) FROM dw.row_issue WHERE run_id=%s AND disposition='BLOCK_PUBLISH'", (failed,)).fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM dw.booking_rejection WHERE run_id=%s AND arrival_date IS NULL", (failed,)).fetchone()[0] == 1


def test_readers_see_old_snapshot_until_commit_and_writers_share_lock(database, tmp_path, monkeypatch):
    import importlib
    loader = importlib.import_module("pipeline.staging_to_dw.run")
    manifest = make_sources(tmp_path)
    stage(manifest, dbname=database)
    config = config_for(tmp_path, manifest)
    run(config, dbname=database)
    before = active_state(database)
    change_config(config, "concurrency-v2")
    original = loader.checkpoint
    observed = []

    def observe(phase, failure, interruption):
        if phase in ("clear","facts","publish"):
            observed.append(active_state(database))
        original(phase, failure, interruption)

    monkeypatch.setattr(loader, "checkpoint", observe)
    run(config, dbname=database)
    assert len(observed) == 3 and all(state == before for state in observed)
    monkeypatch.setattr(loader, "checkpoint", original)
    change_config(config, "concurrency-v3")
    with connect(database) as holder:
        holder.execute("SELECT pg_advisory_xact_lock(%s)", (WRITER_LOCK,))
        with ThreadPoolExecutor(max_workers=3) as pool:
            staging = pool.submit(stage, manifest, dbname=database)
            loads = [pool.submit(run, config, dbname=database) for _ in range(2)]
            holder.commit()
            assert staging.result(timeout=30)["status"] == "no-op"
            assert sorted(f.result(timeout=30)["status"] for f in loads) == ["no-op","published"]


def test_cli_report_failure_does_not_change_published_run_to_failed(database, tmp_path):
    manifest = make_sources(tmp_path)
    stage(manifest, dbname=database)
    config = config_for(tmp_path, manifest)
    blocker = tmp_path / "regular-file"
    blocker.write_text("Not a report directory", encoding="utf-8")
    completed = subprocess.run([sys.executable,str(ROOT/"scripts/run_pipeline.py"),"--to","dw","--config",str(config),
                                "--dbname",database,"--report",str(blocker/"report.json")], capture_output=True,text=True,cwd=ROOT)
    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["status"] == "published" and "report_error" in result
    with connect(database) as conn:
        assert conn.execute("SELECT status FROM dw.load_run").fetchall() == [("published",)]
    assert run(config, dbname=database)["status"] == "no-op"


def test_independent_quality_detects_tampering_and_unmanaged_mart_blocks_refresh(database, tmp_path):
    manifest = make_sources(tmp_path)
    stage(manifest, dbname=database)
    config = config_for(tmp_path, manifest)
    run(config, dbname=database)
    with connect(database) as conn:
        conn.execute("UPDATE dw.fact_booking SET adr=999 WHERE source_row_id=2")
        conn.commit()
        checked = report(conn,load_config(config))
        assert checked["passed"] is False and checked["checks"]["fact_source_measures"] == 1
    change_config(config,"repair-v2")
    run(config,dbname=database)
    before = active_state(database)
    with connect(database) as conn:
        conn.execute("CREATE SCHEMA mart")
        conn.execute("CREATE TABLE mart.daily_hotel_operations(date_key integer PRIMARY KEY)")
    change_config(config,"mart-v3")
    with pytest.raises(ValueError,match="Operations Mart exists without its migration ledger"):
        run(config,dbname=database)
    assert active_state(database) == before


def test_context_bad_sources_keep_booking_and_explicit_unknowns(database, tmp_path):
    manifest = make_sources(tmp_path)
    selected = json.loads(manifest.read_text(encoding="utf-8"))
    weather_file = tmp_path / "mixed_weather.json"
    write_json(weather_file, {"timezone":"Europe/Lisbon","daily_units":{"temperature_2m_mean":"°C","precipitation_sum":"mm"},
                             "daily":{"time":["2017-08-01","2017-08-01","2017-08-02"],
                                      "temperature_2m_mean":[20,21,"bad"],"precipitation_sum":[0,1,-1]}})
    holiday_file = tmp_path / "mixed_holiday.csv"
    holiday_file.write_text("date,holiday_name,country,subdivision,scope,category,observed\n"
                           "2017-08-01,Zed,PT,,national,public,false\n"
                           "2017-08-01,Alpha,PT,11,Lisboa,public,false\n"
                           "2017-08-01,Zed,PT,,national,public,false\n"
                           "2017-02-30,Broken,PT,11,Mars,public,false\n",encoding="utf-8")
    selected["sources"]["weather"] = {"file":str(weather_file),"sha256":sha256(weather_file)}
    selected["sources"]["holiday"] = {"file":str(holiday_file),"sha256":sha256(holiday_file)}
    write_json(manifest,selected)
    stage(manifest,dbname=database)
    config = config_for(tmp_path,manifest)
    result = run(config,dbname=database)
    assert result["quality"]["passed"] and result["counts"]["fact_booking"] == 6
    with connect(database) as conn:
        assert conn.execute("SELECT holiday_record_count,holiday_names,is_holiday,holiday_data_status FROM dw.daily_hotel_context WHERE date_key=20170801").fetchone() == (3,["Alpha","Zed"],True,"PARTIAL")
        assert conn.execute("SELECT is_holiday,has_national_holiday,has_lisboa_holiday FROM dw.daily_hotel_context WHERE date_key=20170802").fetchone() == (None,None,None)
        assert conn.execute("SELECT temperature_status,precipitation_status,temperature_mean,precipitation FROM dw.daily_hotel_context WHERE date_key=20170801").fetchone() == ("AMBIGUOUS","AMBIGUOUS",None,None)
        assert conn.execute("SELECT temperature_status,precipitation_status FROM dw.daily_hotel_context WHERE date_key=20170802").fetchone() == ("INVALID","INVALID")
        assert conn.execute("SELECT temperature_status FROM dw.daily_hotel_context WHERE date_key=20170803").fetchone()[0] == "MISSING"
        conn.execute("UPDATE dw.daily_hotel_context SET has_national_holiday=false,has_lisboa_holiday=false,is_holiday=false,holiday_data_status='COMPLETE' WHERE date_key=20170802")
        conn.commit()
        damaged = report(conn,load_config(config))
        assert not damaged["passed"] and damaged["checks"]["holiday_scope_coverage"] == 1
