"""Load individual PT/Lisboa holiday records without collapsing same-day names."""

from __future__ import annotations

import csv
from pathlib import Path

from psycopg.types.json import Jsonb

from .common import LoadResult, RecordParser, StructuralError


HOLIDAY_FIELDS = ["date", "holiday_name", "country", "subdivision", "scope", "category", "observed"]
INSERT_SQL = """INSERT INTO staging.stg_holiday
    (_source_file,_source_file_sha256,_source_row_id,_batch_id,raw_record,
     date,holiday_name,country,subdivision,scope,category,observed)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING"""


def load(cur, spec: dict, batch_id) -> LoadResult:
    result = LoadResult()
    path: Path = spec["resolved_path"]
    sha = spec["sha256"]
    pending = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            if reader.fieldnames is None or set(reader.fieldnames) != set(HOLIDAY_FIELDS) or len(reader.fieldnames) != 7:
                raise StructuralError("holiday", "header", "Holiday CSV must contain exactly seven contracted fields", str(reader.fieldnames))
            for row_id, raw in enumerate(reader, start=2):
                result.raw_count += 1
                if None in raw or any(value is None for value in raw.values()):
                    raise StructuralError("holiday", f"record {row_id}", "Malformed CSV field count", str(raw))
                parser = RecordParser("holiday", sha, row_id, raw, result, batch_id)
                values = [parser.value("date", "date")]
                values.extend(parser.value(field) for field in ("holiday_name", "country", "subdivision", "scope", "category"))
                values.append(parser.value("observed", "boolean"))
                if values[2] is not None and values[2] != "PT":
                    parser.issue("country", "HOLIDAY_COUNTRY_DOMAIN", "invalid", raw["country"], "Expected PT")
                if values[4] is not None and values[4] not in {"national", "Lisboa"}:
                    parser.issue("scope", "HOLIDAY_SCOPE_DOMAIN", "invalid", raw["scope"], "Expected national or Lisboa")
                if values[5] is not None and values[5] != "public":
                    parser.issue("category", "HOLIDAY_CATEGORY_DOMAIN", "invalid", raw["category"], "Expected public")
                if values[6] is True:
                    parser.issue("observed", "HOLIDAY_OBSERVED_MISMATCH", "invalid", raw["observed"], "Acquisition setting is observed=false")
                pending.append((spec["file"], sha, row_id, batch_id, Jsonb(raw), *values))
                result.staged_count += 1
                if len(pending) >= 1000:
                    cur.executemany(INSERT_SQL, pending)
                    pending.clear()
            if pending:
                cur.executemany(INSERT_SQL, pending)
    except (csv.Error, UnicodeError) as exc:
        raise StructuralError("holiday", f"CSV line {getattr(reader, 'line_num', '?')}", str(exc)) from exc
    return result
