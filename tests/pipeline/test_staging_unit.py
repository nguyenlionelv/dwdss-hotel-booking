from decimal import Decimal
from uuid import uuid4

from pipeline.source_to_staging.common import LoadResult, RecordParser


def parser(raw):
    result = LoadResult()
    return RecordParser("booking", "a" * 64, 42, raw, result, uuid4()), result


def test_missing_is_field_specific_and_not_global_na():
    record, result = parser({"children": "NA", "country": "NA"})
    assert record.value("children", "numeric", missing_tokens={"", "NA"}) is None
    assert record.value("country", missing_tokens={"", "NULL"}) == "NA"
    assert result.missing_json() == {"children": {"NA": 1}}
    assert result.issues[0][5:7] == ("MISSING_CHILDREN", "missing")


def test_present_invalid_is_not_missing_and_preserves_raw_value():
    record, result = parser({"children": "not-a-number"})
    assert record.value("children", "numeric", missing_tokens={"", "NA"}) is None
    assert result.missing_json() == {}
    assert result.issues[0][5:8] == ("NUMERIC_PARSE_FAILED", "invalid", "not-a-number")
    assert "cannot be parsed" in result.issues[0][8]


def test_zero_and_false_are_real_values():
    record, result = parser({"children": "0", "is_canceled": "0"})
    assert record.value("children", "numeric", missing_tokens={"", "NA"}) == Decimal(0)
    assert record.value("is_canceled", "integer") == 0
    assert result.missing_json() == {}
    assert result.issues == []


def test_oversized_numeric_remains_raw_invalid_not_missing():
    record, result = parser({"children": "1e10001"})
    assert record.value("children", "numeric", missing_tokens={"", "NA"}) is None
    assert result.issues[0][5:8] == ("NUMERIC_PARSE_FAILED", "invalid", "1e10001")
    assert result.missing_json() == {}
