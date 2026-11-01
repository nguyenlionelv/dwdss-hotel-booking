"""Independent input-contract and hand-calculated measure expectations."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
import subprocess
import sys

import pytest

from pipeline.source_to_staging.common import ROOT, sha256
from pipeline.staging_to_dw.config import DEFAULT_CONFIG, coverage_status, load_config, load_mapping, mapped_value
from pipeline.staging_to_dw.preflight import measure_values, profile_bookings, profile_context, valid_number


FIXTURE = json.loads((ROOT / "tests/fixtures/dw/operations_expected.json").read_text(encoding="utf-8"))


def assert_values(actual, expected):
    for key, value in expected.items():
        if isinstance(value, float):
            assert float(actual[key]) == pytest.approx(value), key
        else:
            assert actual[key] == value, key


def test_explicit_mapping_aliases_unknowns_and_partial_profiles():
    bundle = load_config()
    mappings = bundle["mappings"]
    assert mapped_value(" cn ", mappings["country"], "UNK") == ("CHN", "known")
    assert mapped_value("TMP", mappings["country"], "UNK") == ("TLS", "known")
    assert mapped_value("Undefined", mappings["channel"], "UNKNOWN") == ("UNKNOWN", "unknown")
    assert mapped_value("NA", mappings["country"], "UNK") == ("UNK", "unmapped")
    assert mapped_value(None, mappings["country"], "UNK") == ("UNK", "missing")
    assert mappings["room_type"]["K"]["target_name"] == ""


@pytest.mark.parametrize("value,valid", [(None, False), (True, False), ("NaN", False), ("Infinity", False),
    ("-1", False), ("1.5", False), ("2147483648", False), ("2147483647", True), ("0", True), (Decimal("2.0"), True)])
def test_guest_domain_checked_before_cast(value, valid):
    assert valid_number(value, integer=True) is valid


def test_decimal_adr_precision_is_preserved():
    rows = [{**FIXTURE["defaults"], "adr": Decimal("123.4567890123456789")}]
    values = measure_values(rows, "COMPLETE", 0)
    assert values["sum_adr"] == Decimal("123.4567890123456789")
    assert values["avg_adr"] == Decimal("123.4567890123456789")
    rows = [{**FIXTURE["defaults"], "adr": Decimal("123456789012345678901234567890.12345")},
            {**FIXTURE["defaults"], "adr": Decimal("0.00001")}]
    assert measure_values(rows, "COMPLETE", 0)["sum_adr"] == Decimal("123456789012345678901234567890.12346")


@pytest.mark.parametrize("case", FIXTURE["measure_cases"], ids=lambda case: case["name"])
def test_independent_null_zero_and_denominator_examples(case):
    rows = [{**FIXTURE["defaults"], **row} for row in case["rows"]]
    result = measure_values(rows, case["coverage"], case.get("rejected_count", 0))
    assert_values(result, case["expected"])


def fixture_bookings():
    result = []
    for item in FIXTURE["design_rows"]:
        row = {**FIXTURE["defaults"], **item}
        row.update({"_source_row_id": item["row_id"], "arrival_date": date.fromisoformat(item["date"]),
                    "distribution_channel": "Direct", "market_segment": "Direct", "customer_type": "Transient",
                    "is_repeated_guest": 0, "reserved_room_type": "A", "assigned_room_type": "K"})
        row["raw_record"] = {k: None if v is None else str(v) for k, v in row.items()}
        result.append(row)
    return result


def fixture_bundle():
    bundle = load_config()
    bundle["config"]["actual"] = {"start": "2017-08-01", "end": "2017-08-03"}
    bundle["coverage"]["intervals"][0]["status"] = "COMPLETE"  # Explicit synthetic assumption only.
    return bundle


def test_design_fixture_counts_sums_and_quality():
    result = profile_bookings(fixture_bookings(), fixture_bundle())
    expected = FIXTURE["design_expected"]
    assert_values(result, {k: expected[k] for k in ("source_count", "accepted_candidate_count", "rejected_candidate_count")})
    assert result["errors"] == []
    for row in result["daily_measures"]:
        assert_values(row, expected[row["date"]])
    assert result["dimension_codes"]["room_type"] == ["A", "K", "UNKNOWN"]
    assert result["dimension_codes"]["country"] == ["GBR", "PRT", "UNK"]
    assert result["country_calendar_row_count"] == 9
    assert result["room_comparison"]["eligible_rows"] == 6
    assert result["room_comparison"]["different_code_rows"] == 6


def test_unknown_date_calendar_and_unreviewed_codes_are_explicit_errors():
    rows = fixture_bookings()
    rows[0]["arrival_date"] = None
    rows[1]["arrival_date"] = date(1900, 1, 1)
    rows[2]["market_segment"] = "NOT_REVIEWED"
    rows[2]["raw_record"]["market_segment"] = "NOT_REVIEWED"
    result = profile_bookings(rows, fixture_bundle())
    assert any("UNKNOWN_ARRIVAL_DATE" in e for e in result["errors"])
    assert any("CALENDAR_OUT_OF_RANGE" in e for e in result["errors"])
    assert any("unreviewed codes" in e for e in result["errors"])


def test_profile_preserves_known_half_and_ignores_codes_only_in_rejections():
    rows = fixture_bookings()
    rows[0]["customer_type"] = None
    rows[0]["is_repeated_guest"] = 1
    rows[1]["is_repeated_guest"] = 9
    rows[-1]["assigned_room_type"] = "B"
    result = profile_bookings(rows, fixture_bundle())
    assert {"customer_type_code": "UNKNOWN", "repeat_status": "REPEAT", "rows": 1} in result["customer_profiles"]
    assert {"customer_type_code": "TRANSIENT", "repeat_status": "UNKNOWN", "rows": 1} in result["customer_profiles"]
    assert "B" not in result["dimension_codes"]["room_type"]


def test_coverage_outside_interval_is_unknown_and_scopes_are_independent():
    coverage = load_config()["coverage"]
    assert coverage_status(coverage, "weather", "all", date(2017, 9, 1)) == "UNKNOWN"
    assert coverage_status(coverage, "holiday", "national", date(2017, 9, 1)) == "COMPLETE"
    coverage["intervals"] = [i for i in coverage["intervals"] if i["scope"] != "Lisboa"]
    assert coverage_status(coverage, "holiday", "Lisboa", date(2017, 9, 1)) == "UNKNOWN"


def test_accepted_booking_assumption_is_bounded_and_preserves_measure_quality():
    bundle = load_config()
    coverage = bundle["coverage"]
    assert coverage_status(coverage, "booking", "all", date(2015, 7, 1)) == "COMPLETE"
    assert coverage_status(coverage, "booking", "all", date(2017, 8, 31)) == "COMPLETE"
    assert coverage_status(coverage, "booking", "all", date(2015, 6, 30)) == "UNKNOWN"
    assert coverage_status(coverage, "booking", "all", date(2017, 9, 1)) == "UNKNOWN"
    interval = next(i for i in coverage["intervals"] if i["source_id"] == "booking")
    decision = json.loads((ROOT / interval["evidence"]["file"]).read_text(encoding="utf-8"))
    assert decision["basis"] == "user_accepted_dataset_completeness_assumption"
    assert decision["source_file_sha256"] == bundle["sources"]["booking"]["sha256"]
    assert (decision["start"], decision["end"]) == (interval["start"], interval["end"])
    rows = fixture_bookings()
    assert measure_values([rows[0]], "COMPLETE", 0)["target_guests"] == 3
    zero_guest_day = measure_values([rows[5]], "COMPLETE", 0)
    assert zero_guest_day["guest_data_status"] == "PARTIAL"
    assert zero_guest_day["target_guests"] is None
    canceled_missing = {**rows[3], "is_canceled": 1}
    assert measure_values([canceled_missing], "COMPLETE", 0)["target_guests"] == 0


def test_mapping_rejects_duplicates_and_conflicting_names(tmp_path):
    path = tmp_path / "mapping.csv"
    path.write_text("source_code,target_code,target_name,status,note\nUNK,UNK,Unknown,unknown,member\nPRT,PRT,Portugal,known,source\nPRT,PRT,Portugal,known,source\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_mapping(path, unknown_code="UNK")
    path.write_text("source_code,target_code,target_name,status,note\nUNK,UNK,Unknown,unknown,member\nCN,CHN,China,known,source\nCHN,CHN,Other,known,source\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Conflicting names"):
        load_mapping(path, unknown_code="UNK")


def write_config(tmp_path, config):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_config_rejects_modified_assets_calendar_gaps_and_stale_coverage(tmp_path):
    base = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config = deepcopy(base)
    config["calendar"]["end"] = "2017-09-01"
    with pytest.raises(ValueError, match="seven days"):
        load_config(write_config(tmp_path, config))
    config = deepcopy(base)
    config["mappings"]["country"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="checksum"):
        load_config(write_config(tmp_path, config))
    coverage = deepcopy(load_config()["coverage"])
    coverage["intervals"].append(deepcopy(coverage["intervals"][0]))
    coverage_path = tmp_path / "coverage.json"
    coverage_path.write_text(json.dumps(coverage), encoding="utf-8")
    config = deepcopy(base)
    config["coverage"] = {"file": str(coverage_path), "sha256": sha256(coverage_path)}
    with pytest.raises(ValueError, match="Overlapping"):
        load_config(write_config(tmp_path, config))
    coverage["intervals"].pop()
    coverage["source_checksums"]["weather"] = "f" * 64
    coverage_path.write_text(json.dumps(coverage), encoding="utf-8")
    config["coverage"]["sha256"] = sha256(coverage_path)
    with pytest.raises(ValueError, match="Coverage source checksum"):
        load_config(write_config(tmp_path, config))


def test_weather_complete_claim_and_national_null_subdivision():
    bundle = fixture_bundle()
    bundle["config"]["calendar"] = {"start": "2017-08-01", "end": "2017-08-02"}
    holidays = [{"_source_row_id": 2, "date": date(2017, 8, 1), "holiday_name": "Example", "country": "PT",
                 "subdivision": None, "scope": "national", "category": "public", "observed": False}]
    weather = [{"_source_row_id": 1, "local_date": date(2017, 8, 1), "temperature_2m_mean": Decimal("20"), "precipitation_sum": Decimal("0")}]
    result = profile_context(holidays, weather, [], bundle)
    assert result["holiday_valid_rows"] == 1
    assert result["weather_complete_claim_failures"] == ["2017-08-02"]
    weather.append({**weather[0], "_source_row_id": 2})
    result = profile_context(holidays, weather, [], bundle)
    assert result["weather_duplicate_dates"] == ["2017-08-01"]
    assert result["weather_complete_claim_failures"] == ["2017-08-01", "2017-08-02"]


def test_cli_failure_exit_and_existing_evidence_is_preserved(tmp_path):
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config["mappings"]["country"]["sha256"] = "0" * 64
    path = write_config(tmp_path, config)
    output = tmp_path / "new-evidence"
    command = [sys.executable, str(ROOT / "scripts/check_dw_inputs.py"), "--config", str(path), "--output-dir", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 1
    report_path = output / "preflight.json"
    original = report_path.read_bytes()
    assert json.loads(original)["passed"] is False
    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 1
    assert "already exists" in result.stdout
    assert report_path.read_bytes() == original
    # A raw checksum failure must also produce failure evidence before DB access.
    manifest = json.loads((ROOT / config["source_manifest"]).read_text(encoding="utf-8"))
    raw = tmp_path / "wrong-booking.csv"
    raw.write_text("wrong bytes", encoding="utf-8")
    manifest["sources"]["booking"]["file"] = str(raw)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config["source_manifest"] = str(manifest_path)
    path = write_config(tmp_path, config)
    output = tmp_path / "raw-failure"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/check_dw_inputs.py"), "--config", str(path),
                             "--output-dir", str(output)], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 1
    failure = json.loads((output / "preflight.json").read_text(encoding="utf-8"))
    assert failure["passed"] is False
    assert "Raw file checksum differs" in failure["errors"][0]
