"""Load aligned Open-Meteo daily arrays as individual source records."""

from __future__ import annotations

import json
from pathlib import Path

from psycopg.types.json import Jsonb

from .common import LoadResult, RecordParser, StructuralError


VARIABLES = ("time", "temperature_2m_mean", "precipitation_sum")
INSERT_SQL = """INSERT INTO staging.stg_weather
    (_source_file,_source_file_sha256,_source_row_id,_batch_id,raw_record,
     local_date,temperature_2m_mean,precipitation_sum)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING"""


def load(cur, spec: dict, batch_id) -> LoadResult:
    result = LoadResult()
    path: Path = spec["resolved_path"]
    sha = spec["sha256"]
    try:
        response = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise StructuralError("weather", "$", f"Unreadable JSON response: {exc}") from exc
    daily = response.get("daily") if isinstance(response, dict) else None
    if not isinstance(daily, dict) or any(not isinstance(daily.get(name), list) for name in VARIABLES):
        raise StructuralError("weather", "$.daily", "Missing daily arrays or wrong structure")
    lengths = {name: len(daily[name]) for name in VARIABLES}
    if len(set(lengths.values())) != 1:
        raise StructuralError("weather", "$.daily", f"Daily arrays are not aligned: {lengths}")
    if response.get("timezone") != "Europe/Lisbon":
        raise StructuralError("weather", "$.timezone", "Expected Europe/Lisbon")
    units = response.get("daily_units")
    if not isinstance(units, dict):
        raise StructuralError("weather", "$.daily_units", "Missing weather units object")
    if units.get("temperature_2m_mean") != "°C" or units.get("precipitation_sum") != "mm":
        raise StructuralError("weather", "$.daily_units", "Unexpected weather units")
    seen_dates = set()
    pending = []
    for index in range(lengths["time"]):
        row_id = index + 1
        raw = {name: daily[name][index] for name in VARIABLES}
        parser = RecordParser("weather", sha, row_id, raw, result, batch_id)
        result.raw_count += 1
        local_date = parser.value("time", "date")
        temperature = parser.value("temperature_2m_mean", "numeric")
        precipitation = parser.value("precipitation_sum", "numeric", nonnegative=True)
        if local_date is not None:
            if local_date in seen_dates:
                parser.issue("time", "WEATHER_DUPLICATE_DATE", "invalid", raw["time"],
                             "More than one daily entry for this local date", "warning")
            seen_dates.add(local_date)
        pending.append((spec["file"], sha, row_id, batch_id, Jsonb(raw), local_date, temperature, precipitation))
        result.staged_count += 1
        if len(pending) >= 1000:
            cur.executemany(INSERT_SQL, pending)
            pending.clear()
    if pending:
        cur.executemany(INSERT_SQL, pending)
    return result
