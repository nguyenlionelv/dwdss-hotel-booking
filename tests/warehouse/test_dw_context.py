"""Hand-calculated daily context/calendar fixtures independent of the loader SQL."""

from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest

from pipeline.staging_to_dw.context import build_context
from pipeline.staging_to_dw.dimensions import build_calendar
from pipeline.staging_to_dw.snapshot import StagingSnapshot


DAY = date(2017,8,1)


def fixture():
    calendar = build_calendar({"calendar":{"start":"2017-08-01","end":"2017-08-03"}})
    coverage = {"intervals":[{"source_id":sid,"scope":scope,"start":"2017-08-01","end":"2017-08-03","status":"COMPLETE"}
                             for sid,scope in (("holiday","national"),("holiday","Lisboa"),("weather","all"))]}
    snapshot = StagingSnapshot({}, {"holiday":{"source_file_sha256":"a"*64},"weather":{"source_file_sha256":"b"*64}}, [], [], [], [])
    return calendar,coverage,snapshot


def holiday(row_id, scope="national", day=DAY, name="Example"):
    return {"_source_file_sha256":"a"*64,"_source_row_id":row_id,"date":day,"holiday_name":name,"country":"PT",
            "scope":scope,"subdivision":None if scope=="national" else "11","category":"public","observed":False,
            "raw_record":{"date":day.isoformat() if day else "2017-02-30","holiday_name":name}}


def weather(row_id=1,temperature=Decimal(20),rain=Decimal(0)):
    return {"_source_file_sha256":"b"*64,"_source_row_id":row_id,"local_date":DAY,
            "temperature_2m_mean":temperature,"precipitation_sum":rain,
            "raw_record":{"time":DAY.isoformat(),"temperature_2m_mean":str(temperature) if temperature is not None else None,
                          "precipitation_sum":str(rain) if rain is not None else None}}


@pytest.mark.parametrize("national,lisboa,combined", [(True,False,True),(False,True,True),(True,True,True),(False,False,False),(True,None,True),(False,None,None)])
def test_holiday_scopes_three_values(national,lisboa,combined):
    calendar,coverage,snapshot = fixture()
    if national:
        snapshot.holidays.append(holiday(2))
    if lisboa:
        snapshot.holidays.append(holiday(3,"Lisboa"))
    if lisboa is None:
        coverage["intervals"][1]["status"] = "UNKNOWN"
    rows,_ = build_context(calendar,snapshot,coverage)
    row = rows[0]
    assert (row["has_national_holiday"],row["has_lisboa_holiday"],row["is_holiday"]) == (national,lisboa,combined)
    assert row["holiday_data_status"] == ("PARTIAL" if lisboa is None else "COMPLETE")


def test_holiday_names_unique_sorted_and_unknown_date_does_not_imply_nonholiday():
    calendar,coverage,snapshot = fixture()
    snapshot.holidays = [holiday(2,name="Zed"),holiday(3,"Lisboa",name="Alpha"),holiday(4,name="Zed")]
    rows,_ = build_context(calendar,snapshot,coverage)
    assert rows[0]["holiday_names"] == ["Alpha","Zed"] and rows[0]["holiday_record_count"] == 3
    snapshot.holidays.append(holiday(5,day=None))
    rows,issues = build_context(calendar,snapshot,coverage)
    assert rows[1]["has_national_holiday"] is None and rows[1]["is_holiday"] is None
    assert issues[0]["local_date"] is None and issues[0]["source_row_id"] == 5


@pytest.mark.parametrize("temperature,rain,temp_status,rain_status", [
    (Decimal(-5),Decimal(0),"COMPLETE","COMPLETE"), (None,Decimal(0),"MISSING","COMPLETE"),
    (Decimal("NaN"),Decimal(-1),"INVALID","INVALID"), (Decimal(20),None,"COMPLETE","MISSING")])
def test_weather_fields_have_independent_quality(temperature,rain,temp_status,rain_status):
    calendar,coverage,snapshot = fixture()
    snapshot.weather = [weather(temperature=temperature,rain=rain)]
    rows,_ = build_context(calendar,snapshot,coverage)
    assert rows[0]["temperature_status"] == temp_status and rows[0]["precipitation_status"] == rain_status
    if temp_status != "COMPLETE":
        assert rows[0]["temperature_mean"] is None
    if rain_status != "COMPLETE":
        assert rows[0]["precipitation"] is None
    assert rows[1]["temperature_status"] == "MISSING"


def test_duplicate_weather_is_ambiguous_and_no_input_is_mutated():
    calendar,coverage,snapshot = fixture()
    snapshot.weather = [weather(),weather(2,temperature=Decimal(21))]
    before = deepcopy(snapshot)
    rows,_ = build_context(calendar,snapshot,coverage)
    assert rows[0]["weather_record_count"] == 2 and rows[0]["weather_ambiguous"]
    assert rows[0]["temperature_mean"] is None and rows[0]["precipitation"] is None
    assert rows[0]["temperature_status"] == rows[0]["precipitation_status"] == "AMBIGUOUS"
    assert snapshot == before


def test_iso_calendar_crosses_year_with_continuous_dates():
    rows = build_calendar({"calendar":{"start":"2015-12-31","end":"2016-01-02"}})
    assert [r["date_key"] for r in rows] == [20151231,20160101,20160102]
    assert [(r["iso_year"],r["iso_week"]) for r in rows] == [(2015,53)]*3
    assert rows[2]["is_weekend"] is True
