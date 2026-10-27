"""Operations acceptance on real PostgreSQL, using fixture-owned databases."""

from concurrent.futures import ThreadPoolExecutor
import csv
from decimal import Decimal
import json
import subprocess
import sys

import pytest
from psycopg.rows import dict_row

from pipeline.dw_to_mart.migrations import MIGRATION, apply_mart_migration
from pipeline.dw_to_mart.run import run as refresh
from pipeline.quality.mart_checks import report
from pipeline.source_to_staging.common import ROOT, connect, sha256
from pipeline.source_to_staging.run import run as stage
from pipeline.staging_to_dw.config import load_config
from pipeline.staging_to_dw.migrations import WRITER_LOCK
from pipeline.staging_to_dw.run import run as load_dw
from test_dw_inputs_postgres import make_sources
from test_dw_postgres import database, config_for, change_config, changed_booking_manifest, active_state, write_json


EXPECTED = json.loads((ROOT / "tests/fixtures/dw/operations_expected.json").read_text(encoding="utf-8"))


def setup_mart(database, tmp_path):
    manifest = make_sources(tmp_path)
    stage(manifest,dbname=database)
    config = config_for(tmp_path,manifest)
    loaded = load_dw(config,dbname=database)
    with connect(database) as conn:
        apply_mart_migration(conn)
    return manifest,config,loaded


def mart_state(database):
    with connect(database) as conn:
        state = conn.execute("SELECT * FROM mart.dataset_state").fetchall()
        daily = conn.execute("SELECT * FROM mart.daily_hotel_operations ORDER BY date_key").fetchall()
        country = conn.execute("SELECT * FROM mart.daily_hotel_operations_by_country ORDER BY date_key,country_key").fetchall()
    return state,daily,country


def test_first_refresh_exact_fixture_country_calendar_and_rerun(database,tmp_path):
    _,config,loaded = setup_mart(database,tmp_path)
    first = refresh(config,dbname=database)
    assert first["status"] == "published" and first["passed"]
    assert first["data_version"] == loaded["data_version"]
    assert first["counts"] == {"daily_hotel_operations":3,"daily_hotel_operations_by_country":9}
    with connect(database) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM mart.daily_hotel_operations ORDER BY date_key")
        for row in cur:
            expected = EXPECTED["design_expected"][row["full_date"].isoformat()]
            for field,value in expected.items():
                if field not in row:
                    continue
                if isinstance(value,float):
                    assert float(row[field]) == pytest.approx(value)
                else:
                    assert row[field] == value, field
        cur.execute("SELECT full_date,country_code,observed_total_guests,guest_data_status FROM mart.daily_hotel_operations_by_country")
        rows = {(str(r["full_date"]),r["country_code"]):r for r in cur}
        acceptance = EXPECTED["country_acceptance_for_later_mart_tests"]
        for day in ("2017-08-01","2017-08-02"):
            for country,value in acceptance["guest_sum_"+day].items():
                assert rows[(day,country)]["observed_total_guests"] == value
        assert all(r["guest_data_status"] == "PARTIAL" for (day,_),r in rows.items() if day == "2017-08-02")
        assert cur.execute("SELECT count(*) FROM mart.daily_hotel_operations WHERE full_date>'2017-08-03'").fetchone()["count"] == 0
    before = mart_state(database)
    again = refresh(config,dbname=database)
    assert again["status"] == "no-op" and again["data_version"] == first["data_version"]
    assert mart_state(database) == before
    assert load_dw(config,dbname=database)["mart"]["passed"]
    assert mart_state(database) == before
    with connect(database) as conn:
        assert report(conn,load_config(config))["passed"]


def test_dw_noop_initializes_empty_mart_and_new_dw_refreshes_both(database,tmp_path):
    manifest,config,loaded = setup_mart(database,tmp_path)
    initialized = load_dw(config,dbname=database)
    assert initialized["status"] == "no-op" and initialized["mart"]["counts"]["daily_hotel_operations"] == 3
    assert initialized["data_version"] == loaded["data_version"]
    changed = changed_booking_manifest(manifest,tmp_path,{"adults":"4"})
    stage(changed,dbname=database)
    config = config_for(tmp_path,changed)
    newer = load_dw(config,dbname=database)
    assert newer["status"] == "published" and newer["data_version"] != loaded["data_version"]
    assert newer["mart"]["data_version"] == newer["data_version"]
    assert newer["mart"]["observed_totals"]["eligible_non_canceled_guests"] == 8
    assert newer["mart"]["counts"]["daily_hotel_operations_by_country"] == 9


@pytest.mark.parametrize("phase",["clear","facts","mart_refresh","mart_validation","publish"])
def test_dw_and_mart_rollback_as_one_unit(database,tmp_path,phase):
    _,config,_ = setup_mart(database,tmp_path)
    refresh(config,dbname=database)
    old_dw,old_mart = active_state(database),mart_state(database)
    change_config(config,"rollback-"+phase)
    with pytest.raises(RuntimeError,match="Injected failure"):
        load_dw(config,dbname=database,inject_failure_after=phase)
    assert active_state(database) == old_dw and mart_state(database) == old_mart
    retry = load_dw(config,dbname=database)
    assert retry["mart"]["passed"]


@pytest.mark.parametrize("phase",["refresh","publish"])
def test_initial_mart_failure_leaves_published_dw_and_empty_mart(database,tmp_path,phase):
    _,config,_ = setup_mart(database,tmp_path)
    old_dw = active_state(database)
    with pytest.raises(RuntimeError,match="Injected failure"):
        refresh(config,dbname=database,inject_failure_after=phase)
    assert active_state(database) == old_dw and mart_state(database) == ([],[],[])
    assert refresh(config,dbname=database)["passed"]


def test_migration_noop_checksum_mismatch_and_cli_failures(database,tmp_path):
    _,config,_ = setup_mart(database,tmp_path)
    with connect(database) as conn:
        assert apply_mart_migration(conn)["status"] == "no-op"
        changed = tmp_path / MIGRATION.name
        changed.write_text(MIGRATION.read_text(encoding="utf-8")+"\n-- changed",encoding="utf-8")
        with pytest.raises(ValueError,match="checksum"):
            apply_mart_migration(conn,changed)
    result_file = tmp_path / "refresh.json"
    command = [sys.executable,str(ROOT/"scripts/refresh_marts.py"),"--config",str(config),"--dbname",database,"--report",str(result_file)]
    first = subprocess.run(command,capture_output=True,text=True,cwd=ROOT)
    assert first.returncode == 0, first.stdout
    original = result_file.read_bytes()
    assert subprocess.run(command,capture_output=True,text=True,cwd=ROOT).returncode != 0
    assert result_file.read_bytes() == original
    blocker = tmp_path / "blocker"
    blocker.write_text("file",encoding="utf-8")
    failed = subprocess.run([*command[:-1],str(blocker/"report.json")],capture_output=True,text=True,cwd=ROOT)
    assert failed.returncode == 1 and json.loads(failed.stdout)["report_error"]
    assert mart_state(database)[0]


def test_independent_quality_detects_measures_context_keys_and_state_tampering(database,tmp_path):
    _,config,_ = setup_mart(database,tmp_path)
    refresh(config,dbname=database)
    with connect(database) as conn:
        conn.execute("UPDATE mart.daily_hotel_operations SET sum_adr=sum_adr+1 WHERE date_key=20170801")
        conn.execute("UPDATE mart.daily_hotel_operations_by_country SET temperature_mean=999 WHERE date_key=20170802")
        conn.execute("UPDATE mart.daily_hotel_operations_by_country SET full_date='2099-01-01' WHERE date_key=20170801 AND country_code='UNK'")
        conn.execute("DELETE FROM mart.daily_hotel_operations_by_country WHERE date_key=20170803 AND country_code='UNK'")
        conn.execute("UPDATE mart.dataset_state SET build_fingerprint=%s",("0"*64,))
        conn.commit()
        result = report(conn,load_config(config))
        assert not result["passed"]
        assert result["checks"]["daily_hotel_operations_measures"] == 1
        assert result["checks"]["daily_hotel_operations_by_country_context"] == 3
        assert result["checks"]["daily_hotel_operations_by_country_calendar"] == 1
        assert result["checks"]["daily_hotel_operations_by_country_keys"] == 1
        assert result["checks"]["dataset_state"] == 1


@pytest.mark.parametrize("case",EXPECTED["measure_cases"],ids=lambda c:c["name"])
def test_sql_null_zero_eligibility_cases(database,tmp_path,case):
    manifest = make_sources(tmp_path)
    selected = json.loads(manifest.read_text(encoding="utf-8"))
    booking = tmp_path / "booking.csv"
    with booking.open(encoding="utf-8",newline="") as handle:
        reader = csv.DictReader(handle)
        fields,template = reader.fieldnames,next(reader)
    with booking.open("w",encoding="utf-8",newline="") as handle:
        writer = csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader()
        baseline = {**template,**{key:str(value) for key,value in EXPECTED["defaults"].items()}}
        for values in case["rows"]:
            row = {**baseline,**{key:str(value) if value is not None else "NULL" for key,value in values.items()}}
            writer.writerow(row)
        if case.get("rejected_count"):
            writer.writerow({**template,"is_canceled":"2"})
        # Keep another accepted day so empty-day cases still have a valid source.
        writer.writerow({**template,"arrival_date_day_of_month":"2"})
    selected["sources"]["booking"]["sha256"] = sha256(booking)
    write_json(manifest,selected)
    stage(manifest,dbname=database)
    config = config_for(tmp_path,manifest)
    cfg = json.loads(config.read_text(encoding="utf-8"))
    coverage_path = tmp_path / "coverage.json"
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    for interval in coverage["intervals"]:
        if interval["source_id"] == "booking":
            interval["status"] = case["coverage"]
    write_json(coverage_path,coverage)
    cfg["coverage"]["sha256"] = sha256(coverage_path)
    write_json(config,cfg)
    with connect(database) as conn:
        apply_mart_migration(conn)
    assert load_dw(config,dbname=database)["mart"]["passed"]
    with connect(database) as conn, conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute("SELECT * FROM mart.daily_hotel_operations WHERE date_key=20170801").fetchone()
        for key,value in case["expected"].items():
            assert row[key] == value, (case["name"],key)


def test_decimal_precision_and_rollup_denominators(database,tmp_path):
    manifest = make_sources(tmp_path)
    changed = changed_booking_manifest(manifest,tmp_path,{"adr":"100.12345678901234567890123456789"})
    stage(changed,dbname=database)
    config = config_for(tmp_path,changed)
    with connect(database) as conn:
        apply_mart_migration(conn)
    assert load_dw(config,dbname=database)["mart"]["passed"]
    with connect(database) as conn:
        daily = conn.execute("SELECT sum_adr,adr_valid_count,avg_party_size FROM mart.daily_hotel_operations WHERE date_key=20170801").fetchone()
        assert daily == (Decimal("220.12345678901234567890123456789"),2,Decimal(2))
        # Four guests / two bookings + two guests / one valid booking => 6/3,
        # irrespective of the other two guest-ineligible non-canceled bookings.
        assert conn.execute("SELECT sum(observed_total_guests)::numeric/sum(guest_valid_booking_count) FROM mart.daily_hotel_operations").fetchone()[0] == 2


def test_mvcc_readers_and_competing_mart_dw_writers(database,tmp_path,monkeypatch):
    import importlib
    loader = importlib.import_module("pipeline.staging_to_dw.run")
    _,config,_ = setup_mart(database,tmp_path)
    refresh(config,dbname=database)
    before = mart_state(database)
    change_config(config,"concurrency-v2")
    original = loader.checkpoint
    observed = []

    def observe(phase,failure,interruption):
        if phase in ("mart_refresh","publish"):
            observed.append(mart_state(database))
        original(phase,failure,interruption)

    monkeypatch.setattr(loader,"checkpoint",observe)
    assert load_dw(config,dbname=database)["mart"]["passed"]
    assert observed == [before,before]
    with connect(database) as holder:
        holder.execute("SELECT pg_advisory_xact_lock(%s)",(WRITER_LOCK,))
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(refresh,config,dbname=database),pool.submit(load_dw,config,dbname=database)]
            holder.commit()
            assert all(future.result(timeout=30)["status"] == "no-op" for future in futures)


def test_one_command_runner_installs_and_verifies_mart(database,tmp_path):
    manifest = make_sources(tmp_path)
    stage(manifest,dbname=database)
    config = config_for(tmp_path,manifest)
    output = tmp_path / "runner"
    child = subprocess.run([sys.executable,str(ROOT/"scripts/run_dw.py"),"--with-mart","--config",str(config),
                            "--dbname",database,"--output-dir",str(output)],capture_output=True,text=True,cwd=ROOT)
    assert child.returncode == 0,child.stdout
    summary = json.loads((output/"summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "completed" and summary["mart_verified"]
    assert summary["mart_counts"] == {"daily_hotel_operations":3,"daily_hotel_operations_by_country":9}
    assert len(summary["steps"]) == 6


def test_candidate_mart_validation_failure_rolls_back_dw(database,tmp_path,monkeypatch):
    import importlib
    loader = importlib.import_module("pipeline.staging_to_dw.run")
    _,config,_ = setup_mart(database,tmp_path)
    refresh(config,dbname=database)
    old_dw,old_mart = active_state(database),mart_state(database)
    original = loader.refresh_operations

    def damage(conn,*args):
        original(conn,*args)
        conn.execute("UPDATE mart.daily_hotel_operations SET sum_adr=sum_adr+1 WHERE date_key=20170801")

    monkeypatch.setattr(loader,"refresh_operations",damage)
    change_config(config,"invalid-mart-v2")
    with pytest.raises(ValueError,match="Mart validation failed"):
        load_dw(config,dbname=database)
    assert active_state(database) == old_dw and mart_state(database) == old_mart


def test_holiday_scope_and_ambiguous_weather_survive_mart_join(database,tmp_path):
    manifest = make_sources(tmp_path)
    selected = json.loads(manifest.read_text(encoding="utf-8"))
    holiday = tmp_path / "holiday.csv"
    holiday.write_text("date,holiday_name,country,subdivision,scope,category,observed\n"
                       "2017-08-01,National,PT,,national,public,false\n"
                       "2017-08-01,Lisboa,PT,11,Lisboa,public,false\n",encoding="utf-8")
    weather = tmp_path / "weather.json"
    write_json(weather,{"timezone":"Europe/Lisbon","daily_units":{"temperature_2m_mean":"°C","precipitation_sum":"mm"},
                        "daily":{"time":["2017-08-01","2017-08-01"],"temperature_2m_mean":[20,21],"precipitation_sum":[0,1]}})
    for key,path in (("holiday",holiday),("weather",weather)):
        selected["sources"][key]["sha256"] = sha256(path)
    write_json(manifest,selected)
    stage(manifest,dbname=database)
    config = config_for(tmp_path,manifest)
    with connect(database) as conn:
        apply_mart_migration(conn)
    result = load_dw(config,dbname=database)
    assert result["mart"]["passed"] and result["mart"]["observed_totals"]["eligible_non_canceled_guests"] == 6
    with connect(database) as conn:
        assert conn.execute("""SELECT has_national_holiday,has_lisboa_holiday,holiday_names,temperature_mean,
                                      temperature_status,precipitation FROM mart.daily_hotel_operations
                               WHERE date_key=20170801""").fetchone() == (True,True,["Lisboa","National"],None,"AMBIGUOUS",None)
        assert conn.execute("SELECT count(*) FROM mart.daily_hotel_operations_by_country WHERE date_key=20170801 AND temperature_status='AMBIGUOUS'").fetchone()[0] == 3


def test_refresh_refuses_changed_fingerprint_within_published_version(database,tmp_path,monkeypatch):
    import importlib
    runner = importlib.import_module("pipeline.dw_to_mart.run")
    _,config,_ = setup_mart(database,tmp_path)
    refresh(config,dbname=database)
    before = mart_state(database)
    monkeypatch.setattr(runner,"build_fingerprint",lambda *args:"0"*64)
    with pytest.raises(ValueError,match="rebuild DW/Mart"):
        refresh(config,dbname=database)
    assert mart_state(database) == before
