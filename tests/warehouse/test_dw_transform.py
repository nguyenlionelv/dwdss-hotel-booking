"""Booking transform acceptance examples; unit-only, no database connection."""

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
import json
from uuid import UUID

import pytest

from pipeline.source_to_staging.common import ROOT
from pipeline.staging_to_dw.config import load_config
from pipeline.staging_to_dw.transform import transform_booking


FIRST_BATCH = UUID("10000000-0000-0000-0000-000000000001")
ACTIVE_BATCH = UUID("20000000-0000-0000-0000-000000000002")
SOURCE_SHA = "a" * 64
EXAMPLES = json.loads((ROOT / "tests/fixtures/dw/operations_expected.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bundle():
    return load_config()


def booking_row(*, raw_overrides=None, **overrides):
    row = {
        "_source_id": "booking", "_source_file_sha256": SOURCE_SHA, "_source_row_id": 2, "_batch_id": FIRST_BATCH,
        "hotel": "City Hotel", "arrival_date": date(2017, 8, 1), "arrival_date_year": 2017,
        "arrival_date_month": "August", "arrival_date_day_of_month": 1, "is_canceled": 0,
        "adults": Decimal(2), "children": Decimal(1), "babies": Decimal(0),
        "stays_in_week_nights": 2, "stays_in_weekend_nights": 0, "lead_time": 10,
        "adr": Decimal("123.45678901234567890123456789012345"), "country": "PRT",
        "distribution_channel": "Direct", "market_segment": "Online TA", "customer_type": "Transient",
        "is_repeated_guest": 0, "reserved_room_type": "D", "assigned_room_type": "F",
    }
    row.update(overrides)
    raw = {key: ("NA" if key == "children" else "NULL" if key == "country" else "") if value is None else str(value)
           for key, value in row.items() if not key.startswith("_") and key != "arrival_date"}
    raw.update(raw_overrides or {})
    row["raw_record"] = raw
    return row


def transform(row, bundle, issues=()):
    return transform_booking(row, bundle["config"], bundle["mappings"], issues)


def stage_issue(row, field, code="NUMERIC_PARSE_FAILED", kind="invalid"):
    return {"batch_id": ACTIVE_BATCH, "source_id": "booking", "source_file_sha256": row["_source_file_sha256"],
            "source_row_id": row["_source_row_id"], "field": field, "rule_code": code, "issue_type": kind,
            "severity": "warning"}


def test_complete_booking_codes_measures_flags_and_precision(bundle):
    result = transform(booking_row(), bundle)
    fact = result.fact
    assert result.rejection is None and result.issues == [] and result.block_publish is False
    expected = {"source_file_sha256": SOURCE_SHA, "source_row_id": 2, "source_first_batch_id": FIRST_BATCH,
                "arrival_date": date(2017, 8, 1), "date_key": 20170801, "booking_count": 1, "is_canceled": 0,
                "adults": 2, "children": 1, "babies": 0, "total_guests": 3, "guest_eligible": True,
                "total_stay_nights": 2, "stay_eligible": True, "lead_time": 10,
                "country_code": "PRT", "country_raw": "PRT", "channel_code": "DIRECT",
                "market_segment_code": "ONLINE TA", "customer_type_code": "TRANSIENT",
                "customer_type_name": "Transient", "repeat_status": "NEW", "is_repeated_guest": False,
                "party_type": "FAMILY", "party_eligible": True, "reserved_room_type_code": "D",
                "assigned_room_type_code": "F", "room_changed_flag": True, "room_comparison_eligible": True,
                "adr": Decimal("123.45678901234567890123456789012345")}
    assert all(fact[key] == value for key, value in expected.items())
    assert type(fact["adults"]) is int and type(fact["adr"]) is Decimal
    assert "country_key" not in fact and "dw_run_id" not in fact and "transformed_at" not in fact


@pytest.mark.parametrize("canceled", [0, 1])
def test_d01_missing_children_retains_booking_and_other_measures(bundle, canceled):
    row = booking_row(children=None, is_canceled=canceled)
    issue = stage_issue(row, "children", "MISSING_CHILDREN", "missing")
    result = transform(row, bundle, [issue])
    assert result.fact is not None and result.rejection is None and not result.block_publish
    assert result.fact["children"] is None and result.fact["total_guests"] is None
    assert result.fact["guest_eligible"] is False and result.fact["party_type"] == "UNKNOWN"
    assert result.fact["stay_eligible"] is True and result.fact["total_stay_nights"] == 2
    assert result.fact["is_canceled"] == canceled and result.fact["source_first_batch_id"] == FIRST_BATCH
    assert len(result.issues) == 1
    assert result.issues[0]["raw_value"] == "NA"
    assert result.issues[0]["issue_type"] == "missing" and result.issues[0]["disposition"] == "NULL_MEASURE"


def test_d02_zero_guests_keep_zeros_and_one_warning(bundle):
    row = booking_row(adults=Decimal(0), children=Decimal(0), babies=Decimal(0))
    result = transform(row, bundle, [stage_issue(row, "adults,children,babies", "ZERO_GUESTS")])
    assert [result.fact[f] for f in ("adults", "children", "babies", "total_guests")] == [0, 0, 0, 0]
    assert result.fact["guest_eligible"] is False and result.fact["party_eligible"] is False
    assert result.fact["party_type"] == "UNKNOWN" and result.fact["stay_eligible"] is True
    assert [(i["rule_code"], i["issue_type"], i["disposition"]) for i in result.issues] == [("ZERO_GUESTS", "warning", "WARN_ONLY")]


@pytest.mark.parametrize("field", ["adults", "children", "babies"])
@pytest.mark.parametrize("value", [Decimal("1.5"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity"),
                                   Decimal("-Infinity"), Decimal("2147483648"), Decimal("1e999999"), True, 2.0])
def test_guest_invalid_fraction_nonfinite_overflow_is_never_truncated(bundle, field, value):
    result = transform(booking_row(**{field: value}), bundle)
    assert result.fact is not None and result.rejection is None
    assert result.fact[field] is None and result.fact["total_guests"] is None
    assert result.fact["guest_eligible"] is False
    issue = next(i for i in result.issues if i["field_name"] == field)
    assert issue["issue_type"] == "invalid" and issue["disposition"] == "NULL_MEASURE"


def test_numeric_integer_boundary_and_bigint_totals(bundle):
    result = transform(booking_row(adults=Decimal("2147483647"), children=Decimal("2147483647"), babies=Decimal("2147483647"),
                                   stays_in_week_nights=2147483647, stays_in_weekend_nights=2147483647), bundle)
    assert result.fact["total_guests"] == 6442450941 and result.fact["total_stay_nights"] == 4294967294
    assert result.fact["guest_eligible"] is True and result.fact["stay_eligible"] is True


@pytest.mark.parametrize("field", ["stays_in_week_nights", "stays_in_weekend_nights", "lead_time"])
@pytest.mark.parametrize("value", [None, -1, Decimal("1.5"), Decimal("Infinity"), 2147483648])
def test_invalid_nights_or_lead_only_nulls_its_measure(bundle, field, value):
    result = transform(booking_row(**{field: value}), bundle)
    assert result.fact[field] is None and result.fact["total_guests"] == 3 and result.fact["guest_eligible"] is True
    assert result.fact["stay_eligible"] is (field == "lead_time")
    issue = next(i for i in result.issues if i["field_name"] == field)
    assert issue["issue_type"] == ("missing" if value is None else "invalid")


@pytest.mark.parametrize("value", [None, Decimal("-0.01"), Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), 1.5, True])
def test_adr_missing_invalid_is_nullable_without_rejecting_booking(bundle, value):
    result = transform(booking_row(adr=value), bundle)
    assert result.fact["adr"] is None and result.fact["guest_eligible"] is True
    assert result.rejection is None
    assert next(i for i in result.issues if i["field_name"] == "adr")["issue_type"] == ("missing" if value is None else "invalid")


def test_zero_nights_lead_and_adr_are_valid(bundle):
    result = transform(booking_row(stays_in_week_nights=0, stays_in_weekend_nights=0, lead_time=0, adr=Decimal(0)), bundle)
    assert result.fact["total_stay_nights"] == 0 and result.fact["stay_eligible"] is True
    assert result.fact["lead_time"] == 0 and result.fact["adr"] == Decimal(0)
    assert [i["rule_code"] for i in result.issues] == ["ZERO_STAY_NIGHTS"]


@pytest.mark.parametrize("value,raw_token", [(None, "broken"), (None, "0"), (1, "1.5"), (0, "NA")])
def test_raw_typed_consistency_never_recovers_or_imputes_children(bundle, value, raw_token):
    result = transform(booking_row(children=value, raw_overrides={"children": raw_token}), bundle)
    assert result.fact["children"] is None and result.fact["total_guests"] is None
    kind = "missing" if raw_token == "NA" else "invalid"
    assert next(i for i in result.issues if i["field_name"] == "children")["issue_type"] == kind


def test_selected_staging_invalid_issue_overrides_plausible_typed_number(bundle):
    row = booking_row()
    result = transform(row, bundle, [stage_issue(row, "children", "GUEST_NOT_INTEGER")])
    assert result.fact["children"] is None and result.fact["guest_eligible"] is False
    assert "GUEST_NOT_INTEGER" in next(i for i in result.issues if i["field_name"] == "children")["reason"]
    assert transform(row, bundle, [stage_issue(row, "meal", "UNUSED_FIELD_ERROR")]).fact == transform(row, bundle).fact


@pytest.mark.parametrize("country,code,kind", [(" cn ", "CHN", None), ("TMP", "TLS", None),
    (None, "UNK", "missing"), ("NA", "UNK", "mapping"), ("NOT_A_COUNTRY", "UNK", "mapping")])
def test_country_aliases_and_unknown_preserve_raw_and_guests(bundle, country, code, kind):
    row = booking_row(country=country)
    result = transform(row, bundle)
    assert result.fact["country_code"] == code and result.fact["country_raw"] == row["raw_record"]["country"]
    assert result.fact["total_guests"] == 3 and result.rejection is None
    if kind:
        issue = next(i for i in result.issues if i["field_name"] == "country")
        assert issue["issue_type"] == kind and issue["disposition"] == "UNKNOWN_DIMENSION"
    else:
        assert not result.issues


def test_undefined_unmapped_and_raw_inconsistent_categorical_codes(bundle):
    result = transform(booking_row(distribution_channel="Undefined", market_segment="NEW_SEGMENT", customer_type="NULL"), bundle)
    assert result.fact["channel_code"] == result.fact["market_segment_code"] == result.fact["customer_type_code"] == "UNKNOWN"
    assert all(i["issue_type"] == "mapping" for i in result.issues)
    row = booking_row(country="PRT", raw_overrides={"country": "NULL"})
    assert transform(row, bundle).fact["country_code"] == "UNK"
    row = booking_row(country="PRT", raw_overrides={"country": "GBR"})
    result = transform(row, bundle)
    assert result.fact["country_code"] == "UNK" and result.issues[0]["issue_type"] == "invalid"


@pytest.mark.parametrize("kind,repeat,expected", [(None, 1, ("UNKNOWN", "REPEAT", True)),
    ("Transient", None, ("TRANSIENT", "UNKNOWN", None)), (None, None, ("UNKNOWN", "UNKNOWN", None)),
    ("Contract", 0, ("CONTRACT", "NEW", False)), ("Transient", 2, ("TRANSIENT", "UNKNOWN", None))])
def test_partial_customer_profile_keeps_known_half(bundle, kind, repeat, expected):
    result = transform(booking_row(customer_type=kind, is_repeated_guest=repeat), bundle)
    fact = result.fact
    assert (fact["customer_type_code"], fact["repeat_status"], fact["is_repeated_guest"]) == expected
    assert fact["customer_type_name"] == ("Unknown" if expected[0] == "UNKNOWN" else kind)


@pytest.mark.parametrize("adults,children,babies,party", [(1,0,0,"SINGLE"), (2,0,0,"COUPLE"),
    (3,0,0,"OTHER_GROUP"), (2,1,0,"FAMILY"), (2,0,1,"FAMILY"), (0,1,0,"FAMILY"), (0,0,0,"UNKNOWN")])
def test_party_rules_for_both_canceled_and_non_canceled(bundle, adults, children, babies, party):
    for canceled in (0, 1):
        result = transform(booking_row(adults=adults, children=children, babies=babies, is_canceled=canceled), bundle)
        assert result.fact["party_type"] == party
        assert result.fact["party_eligible"] is (party != "UNKNOWN")


@pytest.mark.parametrize("reserved,assigned,eligible,changed", [("A","A",True,False), ("A","K",True,True),
    (None,"A",False,None), (None,None,False,None), ("NEW_ROOM","A",False,None)])
def test_room_roles_known_missing_and_assigned_only_code(bundle, reserved, assigned, eligible, changed):
    result = transform(booking_row(reserved_room_type=reserved, assigned_room_type=assigned), bundle)
    assert result.fact["room_comparison_eligible"] is eligible and result.fact["room_changed_flag"] is changed
    assert result.fact["guest_eligible"] is True


@pytest.mark.parametrize("value", [None, 2, -1, Decimal("0.5"), Decimal("NaN"), True])
def test_invalid_cancellation_rejects_once_but_keeps_known_arrival(bundle, value):
    row = booking_row(is_canceled=value)
    result = transform(row, bundle)
    assert result.fact is None and not result.block_publish
    assert result.rejection["arrival_date"] == date(2017, 8, 1)
    assert len(result.rejection["reason_codes"]) == 1
    assert all(i["local_date"] == date(2017, 8, 1) and i["disposition"] == "REJECT_FACT" for i in result.issues)


@pytest.mark.parametrize("overrides", [
    {"arrival_date": None, "arrival_date_day_of_month": 32},
    {"arrival_date": None, "arrival_date_year": None},
    {"arrival_date": None}, {"arrival_date": date(2017,8,2)},
    {"arrival_date": datetime(2017,8,1)}, {"arrival_date_month": "Mars"},
    {"arrival_date_year": Decimal("2017.5")},
])
def test_unknown_or_inconsistent_date_rejects_and_blocks_publish(bundle, overrides):
    result = transform(booking_row(**overrides), bundle)
    assert result.fact is None and result.rejection["arrival_date"] is None and result.block_publish
    assert len(result.rejection["reason_codes"]) == 1
    assert {i["disposition"] for i in result.issues} == {"REJECT_FACT", "BLOCK_PUBLISH"}
    assert all(i["local_date"] is None for i in result.issues)


def test_multiple_core_errors_one_rejection_and_staging_date_issue(bundle):
    row = booking_row(arrival_date=None, is_canceled=2)
    result = transform(row, bundle)
    assert result.fact is None and len(result.rejection["reason_codes"]) == 2 and result.block_publish
    row = booking_row()
    assert transform(row, bundle, [stage_issue(row, "arrival_date", "DATE_PARSE_FAILED")]).block_publish
    assert transform(booking_row(raw_overrides={"arrival_date_year": "2016"}), bundle).block_publish


def test_calendar_failure_is_not_a_booking_rejection(bundle):
    config = deepcopy(bundle["config"])
    config["calendar"]["end"] = "2017-07-31"
    with pytest.raises(ValueError, match="Calendar does not cover"):
        transform_booking(booking_row(), config, bundle["mappings"])


@pytest.mark.parametrize("overrides", [{"_source_file_sha256": "wrong"}, {"_source_row_id": 1},
    {"_source_row_id": True}, {"_batch_id": "bad-uuid"}, {"hotel": "Resort Hotel"}, {"_source_id": "weather"}])
def test_invalid_lineage_or_scope_fails_as_input_error(bundle, overrides):
    with pytest.raises(ValueError):
        transform(booking_row(**overrides), bundle)


def test_raw_schema_issue_identity_and_room_config_errors(bundle):
    row = booking_row()
    del row["raw_record"]["children"]
    with pytest.raises(ValueError, match="raw_record"):
        transform(row, bundle)
    row = booking_row()
    issue = {**stage_issue(row, "children"), "source_row_id": 3}
    with pytest.raises(ValueError, match="does not belong"):
        transform(row, bundle, [issue])
    config = {**bundle["config"], "room_namespace": "unverified"}
    with pytest.raises(ValueError, match="verified shared namespace"):
        transform_booking(row, config, bundle["mappings"])


def test_transform_is_deterministic_preserves_inputs_and_does_not_deduplicate(bundle):
    row = booking_row(children=None)
    issues = [stage_issue(row, "children", "MISSING_CHILDREN", "missing")]
    original = deepcopy((row, bundle, issues))
    first = transform(row, bundle, issues)
    assert first == transform(row, bundle, issues)
    assert (row, bundle, issues) == original
    other = transform({**row, "_source_row_id": 3}, bundle)
    assert first.fact["source_row_id"] == 2 and other.fact["source_row_id"] == 3
    copied_issue = next(i for i in first.issues if i["field_name"] == "children")
    assert copied_issue["source_file_sha256"] == SOURCE_SHA and copied_issue["source_row_id"] == 2


def test_seven_row_design_fixture_has_independent_counts_and_sums(bundle):
    results = []
    for item in EXAMPLES["design_rows"]:
        day = date.fromisoformat(item["date"])
        values = {**EXAMPLES["defaults"], **{k:v for k,v in item.items() if k not in ("row_id","date")}}
        row = booking_row(**values, _source_row_id=item["row_id"], arrival_date=day, arrival_date_day_of_month=day.day)
        results.append(transform(row, bundle))
    facts = [r.fact for r in results if r.fact is not None]
    rejected = [r.rejection for r in results if r.rejection is not None]
    assert len(facts) == 6 and len(rejected) == 1 and rejected[0]["source_row_id"] == 8
    assert {f["source_row_id"] for f in facts}.isdisjoint(r["source_row_id"] for r in rejected)
    assert {f["source_row_id"] for f in facts} | {r["source_row_id"] for r in rejected} == set(range(2,9))
    guests = [f for f in facts if f["is_canceled"] == 0 and f["guest_eligible"]]
    assert sum(f["total_guests"] for f in guests) == 6
    assert sum(f["is_canceled"] == 0 for f in facts) == 5
    second = [f for f in facts if f["arrival_date"] == date(2017,8,2)]
    assert sum(f["guest_eligible"] for f in second) == 1
    assert sum(f["total_guests"] for f in second if f["guest_eligible"]) == 2
    assert sum(f["adr"] for f in second if f["adr"] is not None) == Decimal(140)
    assert not any(r.block_publish for r in results)
