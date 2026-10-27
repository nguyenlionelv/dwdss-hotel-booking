"""Versioned input configuration for the Operations DW build."""

from __future__ import annotations

import csv
import json
import re
from datetime import date, timedelta
from pathlib import Path

from pipeline.source_to_staging.common import ROOT, sha256, source_set


DEFAULT_CONFIG = ROOT / "pipeline/config/dw_operations.json"
MAPPING_NAMES = {"country", "channel", "market_segment", "customer_type", "room_type"}
COVERAGE_SCOPES = {("booking", "all"), ("holiday", "national"),
                   ("holiday", "Lisboa"), ("weather", "all")}
STATUSES = {"COMPLETE", "PARTIAL", "MISSING", "UNKNOWN"}


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def checked_file(spec: dict) -> Path:
    """Reject missing or modified assets before querying Staging."""
    if not isinstance(spec.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", spec["sha256"]):
        raise ValueError("Asset requires a lowercase SHA-256")
    path = resolve_path(spec["file"])
    if sha256(path) != spec["sha256"]:
        raise ValueError(f"Asset checksum mismatch: {spec['file']}")
    return path


def load_mapping(path: Path, *, unknown_code: str, require_name: bool = True) -> dict:
    """Read explicit normalized-token mappings, including intentional unknowns."""
    result = {}
    names = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        if reader.fieldnames != ["source_code", "target_code", "target_name", "status", "note"]:
            raise ValueError(f"Invalid mapping header: {path.name}")
        for row in reader:
            token, code, name = row["source_code"], row["target_code"], row["target_name"]
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed mapping row: {path.name}")
            if not token or token != token.strip().upper() or token in result:
                raise ValueError(f"Duplicate or non-normalized mapping token: {path.name}")
            if not code or code != code.strip().upper() or row["status"] not in {"known", "unknown"}:
                raise ValueError(f"Invalid mapping target/status: {path.name}")
            if (code == unknown_code) != (row["status"] == "unknown"):
                raise ValueError(f"Inconsistent unknown mapping: {path.name}")
            if (require_name and not name) or not row["note"]:
                raise ValueError(f"Missing mapping name/evidence note: {path.name}")
            if code in names and names[code] != name:
                raise ValueError(f"Conflicting names for one target: {path.name}")
            names[code] = name
            result[token] = row
    if unknown_code not in result or result[unknown_code]["status"] != "unknown":
        raise ValueError(f"Missing explicit unknown row: {path.name}")
    return result


def mapped_value(value: str | None, mapping: dict, unknown_code: str) -> tuple[str, str]:
    """Return canonical code and a disposition without global missing tokens."""
    if value is None or not value.strip():
        return unknown_code, "missing"
    token = value.strip().upper()
    row = mapping.get(token)
    if row is None:
        return unknown_code, "unmapped"
    return row["target_code"], row["status"]


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    """Validate versions, dates and pinned mapping/coverage evidence assets."""
    config = json.loads(path.read_text(encoding="utf-8"))
    for key in ("contract_version", "rule_version", "config_version"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f"Missing version: {key}")
    if config.get("hotel_scope") != "City Hotel" or config.get("timezone") != "Europe/Lisbon":
        raise ValueError("Only City Hotel / Europe/Lisbon is supported")
    calendar = config["calendar"]
    start, end = date.fromisoformat(calendar["start"]), date.fromisoformat(calendar["end"])
    actual = config["actual"]
    actual_start, actual_end = date.fromisoformat(actual["start"]), date.fromisoformat(actual["end"])
    if not start <= actual_start <= actual_end <= end:
        raise ValueError("Calendar must contain the ordered actual interval")
    coverage_end = date.fromisoformat(config["data_coverage_end"])
    if coverage_end < actual_end or end < coverage_end + timedelta(days=7):
        raise ValueError("Calendar must extend at least seven days after data coverage end")
    if calendar["label_language"] != "en":
        raise ValueError("Calendar labels currently use explicit English names")
    if config.get("country_calendar") != "actual_dates_x_accepted_countries_including_UNK":
        raise ValueError("Unsupported country calendar policy")
    if config.get("room_namespace") != "shared_anonymized_source_codes":
        raise ValueError("Room namespace must be explicitly verified")
    if set(config["mappings"]) != MAPPING_NAMES:
        raise ValueError("Exactly five categorical mappings are required")
    loaded = {}
    for name, spec in config["mappings"].items():
        if not spec.get("version"):
            raise ValueError(f"Missing mapping version: {name}")
        expected_unknown = "UNK" if name == "country" else "UNKNOWN"
        if spec["unknown_code"] != expected_unknown:
            raise ValueError(f"Invalid unknown code: {name}")
        loaded[name] = load_mapping(checked_file(spec), unknown_code=expected_unknown,
                                    require_name=name != "room_type")
    coverage = json.loads(checked_file(config["coverage"]).read_text(encoding="utf-8"))
    if (not coverage.get("version") or coverage.get("default_status") != "UNKNOWN"
            or set(coverage["source_checksums"]) != {"booking", "holiday", "weather"}):
        raise ValueError("Coverage requires version and all three source checksums")
    intervals = {}
    for entry in coverage["intervals"]:
        scope = (entry["source_id"], entry["scope"])
        first, last = date.fromisoformat(entry["start"]), date.fromisoformat(entry["end"])
        if scope not in COVERAGE_SCOPES or first > last or entry["status"] not in STATUSES or not entry["reason"]:
            raise ValueError("Invalid coverage interval/scope/status/reason")
        for prior_start, prior_end in intervals.get(scope, []):
            if first <= prior_end and last >= prior_start:
                raise ValueError("Overlapping coverage intervals")
        intervals.setdefault(scope, []).append((first, last))
        checked_file(entry["evidence"])
    if set(intervals) != COVERAGE_SCOPES:
        raise ValueError("Coverage must distinguish Booking, Weather, national and Lisboa")
    contract, sources, fingerprint = source_set(resolve_path(config["source_manifest"]), verify=False)
    for sid, spec in sources.items():
        if coverage["source_checksums"][sid] != spec["sha256"]:
            raise ValueError(f"Coverage source checksum mismatch: {sid}")
    return {"config": config, "mappings": loaded, "coverage": coverage,
            "sources": sources, "staging_contract": contract, "source_set_fingerprint": fingerprint,
            "config_sha256": sha256(path)}


def coverage_status(coverage: dict, source_id: str, scope: str, day: date) -> str:
    """An interval without evidence never implies a zero or a non-holiday."""
    for entry in coverage["intervals"]:
        if (entry["source_id"] == source_id and entry["scope"] == scope
                and date.fromisoformat(entry["start"]) <= day <= date.fromisoformat(entry["end"])):
            return entry["status"]
    return "UNKNOWN"
