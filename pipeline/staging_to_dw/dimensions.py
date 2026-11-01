"""Build all six dimensions from accepted source candidates and explicit calendar."""

from __future__ import annotations

from datetime import date, timedelta

from psycopg import sql


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
DIMENSIONS = {
    "dim_country": ("country_key", ("country_code",), ("country_code", "country_name", "is_unknown")),
    "dim_channel": ("channel_key", ("channel_code",), ("channel_code", "channel_name", "is_unknown")),
    "dim_market_segment": ("market_segment_key", ("market_segment_code",), ("market_segment_code", "market_segment_name", "is_unknown")),
    "dim_customer_profile": ("customer_profile_key", ("customer_type_code", "repeat_status"),
                             ("customer_type_code", "customer_type_name", "repeat_status", "is_repeated_guest", "is_unknown")),
    "dim_room_type": ("room_type_key", ("room_type_code",), ("room_type_code", "room_type_name", "is_unknown")),
}
DATE_COLUMNS = ("date_key", "full_date", "year", "quarter", "month", "day_of_month", "iso_year", "iso_week",
                "day_of_week", "day_name", "month_name", "is_weekend")


def build_calendar(config: dict) -> list[dict]:
    day = date.fromisoformat(config["calendar"]["start"])
    end = date.fromisoformat(config["calendar"]["end"])
    rows = []
    while day <= end:
        iso = day.isocalendar()
        rows.append(dict(zip(DATE_COLUMNS, (
            day.year * 10000 + day.month * 100 + day.day, day, day.year, (day.month - 1) // 3 + 1, day.month, day.day,
            iso.year, iso.week, iso.weekday, WEEKDAYS[iso.weekday - 1], MONTHS[day.month - 1], iso.weekday >= 6))))
        day += timedelta(days=1)
    return rows


def build_dimensions(facts: list[dict], config: dict, mappings: dict) -> dict[str, list[dict]]:
    labels = {name: {r["target_code"]: r["target_name"] for r in mapping.values()} for name, mapping in mappings.items()}
    output = {"dim_date": build_calendar(config)}
    for table, name, field, unknown in (
        ("dim_country", "country", "country_code", "UNK"),
        ("dim_channel", "channel", "channel_code", "UNKNOWN"),
        ("dim_market_segment", "market_segment", "market_segment_code", "UNKNOWN"),
    ):
        name_field = DIMENSIONS[table][2][1]
        codes = {f[field] for f in facts} | {unknown}
        output[table] = [{field: code, name_field: labels[name][code], "is_unknown": code == unknown} for code in sorted(codes)]
    profiles = {(f["customer_type_code"], f["repeat_status"]) for f in facts} | {("UNKNOWN", "UNKNOWN")}
    output["dim_customer_profile"] = [
        {"customer_type_code": kind, "customer_type_name": labels["customer_type"][kind], "repeat_status": repeat,
         "is_repeated_guest": {"NEW": False, "REPEAT": True}.get(repeat), "is_unknown": (kind, repeat) == ("UNKNOWN", "UNKNOWN")}
        for kind, repeat in sorted(profiles)]
    rooms = {f[role] for f in facts for role in ("reserved_room_type_code", "assigned_room_type_code")} | {"UNKNOWN"}
    output["dim_room_type"] = [{"room_type_code": code, "room_type_name": labels["room_type"][code] or None,
                                "is_unknown": code == "UNKNOWN"} for code in sorted(rooms)]
    return output


def insert_dimensions(cur, dimensions: dict) -> dict:
    placeholders = sql.SQL(",").join(sql.Placeholder() for _ in DATE_COLUMNS)
    cur.executemany(sql.SQL("INSERT INTO dw.dim_date ({}) VALUES ({})").format(
        sql.SQL(",").join(map(sql.Identifier, DATE_COLUMNS)), placeholders),
        [tuple(r[c] for c in DATE_COLUMNS) for r in dimensions["dim_date"]])
    lookups = {}
    for table, (key, natural, columns) in DIMENSIONS.items():
        for is_unknown in (True, False):
            selected = [r for r in dimensions[table] if r["is_unknown"] == is_unknown]
            insert_columns = (key, *columns) if is_unknown else columns
            values = [((0,) if is_unknown else ()) + tuple(r[c] for c in columns) for r in selected]
            if values:
                cur.executemany(sql.SQL("INSERT INTO dw.{} ({}) VALUES ({})").format(
                    sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, insert_columns)),
                    sql.SQL(",").join(sql.Placeholder() for _ in insert_columns)), values)
        cur.execute(sql.SQL("SELECT {} FROM dw.{}").format(
            sql.SQL(",").join(map(sql.Identifier, (*natural, key))), sql.Identifier(table)))
        lookups[table] = {tuple(r[:-1]): r[-1] for r in cur.fetchall()}
    return lookups
