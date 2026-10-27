"""Shared, deliberately small Source -> Staging helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import psycopg


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "docs/data_dictionary/operations_source_set.json"
SOURCE_IDS = ("booking", "holiday", "weather")
INTEGER_RE = re.compile(r"[+-]?\d+\Z")


class StructuralError(Exception):
    def __init__(self, source_id: str, locator: str, reason: str, raw_fragment: str = ""):
        super().__init__(f"{source_id} {locator}: {reason}")
        self.source_id = source_id
        self.locator = locator
        self.reason = reason
        self.raw_fragment = raw_fragment[:2000]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_dotenv() -> None:
    """Read only the local DB settings, without logging or overriding the process env."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in {"POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT"}:
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def connect(dbname: str | None = None) -> psycopg.Connection:
    load_dotenv()
    return psycopg.connect(
        dbname=dbname or os.getenv("POSTGRES_DB", "hotel_dwdss"),
        user=os.getenv("POSTGRES_USER", "hotel_user"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        connect_timeout=10,
    )


def verify_sources(sources: dict[str, dict[str, Any]]) -> None:
    for source_id in SOURCE_IDS:
        spec = sources[source_id]
        path = spec["resolved_path"]
        if not path.is_file():
            raise StructuralError(source_id, str(path), "Required raw file is missing")
        try:
            actual = sha256(path)
        except OSError as exc:
            raise StructuralError(source_id, str(path), f"Unreadable raw file: {exc}") from exc
        if actual != spec["sha256"].lower():
            raise StructuralError(source_id, str(path), "Raw file checksum differs from selected manifest")
        if "metadata_file" in spec:
            metadata_relative = Path(spec["metadata_file"])
            metadata_path = metadata_relative if metadata_relative.is_absolute() else ROOT / metadata_relative
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise StructuralError(source_id, str(metadata_path), f"Unreadable acquisition metadata: {exc}") from exc
            if not isinstance(metadata, dict):
                raise StructuralError(source_id, str(metadata_path), "Acquisition metadata must be a JSON object")
            recorded = metadata.get("csv_sha256") or metadata.get("weather_sha256")
            if recorded != actual:
                raise StructuralError(source_id, str(metadata_path), "Acquisition metadata checksum mismatch")
            spec["acquisition_metadata"] = metadata
            if source_id == "holiday":
                checks = {
                    "country": spec.get("country"), "years": spec.get("years"),
                    "observed": spec.get("observed"), "library_version": spec.get("generator_version"),
                }
                if any(metadata.get(key) != value for key, value in checks.items() if value is not None):
                    raise StructuralError(source_id, str(metadata_path), "Holiday generation settings differ from selected manifest")
            elif source_id == "weather":
                try:
                    response = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                    raise StructuralError(source_id, str(path), f"Unreadable weather response: {exc}") from exc
                if not isinstance(response, dict):
                    raise StructuralError(source_id, str(path), "Weather response must be a JSON object")
                grid = spec.get("returned_coordinate", {})
                daily = response.get("daily", {})
                times = daily.get("time", []) if isinstance(daily, dict) else []
                units = response.get("daily_units")
                if not isinstance(units, dict):
                    raise StructuralError(source_id, str(path), "Weather daily_units must be an object")
                if (response.get("latitude") != grid.get("latitude")
                        or response.get("longitude") != grid.get("longitude")
                        or response.get("timezone") != spec.get("timezone")
                        or units.get("temperature_2m_mean") != spec.get("daily_variables", {}).get("temperature_2m_mean")
                        or units.get("precipitation_sum") != spec.get("daily_variables", {}).get("precipitation_sum")
                        or not times or times[0] != spec.get("start_date") or times[-1] != spec.get("end_date")
                        or metadata.get("model") != spec.get("model")):
                    raise StructuralError(source_id, str(path), "Weather location, timezone, units, model or date range differs from selected manifest")


def source_set(manifest_path: Path = DEFAULT_MANIFEST, *, verify: bool = True) -> tuple[str, dict[str, dict[str, Any]], str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = manifest["sources"]
    if set(sources) != set(SOURCE_IDS):
        raise ValueError("Manifest must select exactly booking, holiday, weather")
    for source_id in SOURCE_IDS:
        spec = sources[source_id]
        relative = Path(spec["file"])
        path = relative if relative.is_absolute() else ROOT / relative
        spec["resolved_path"] = path
    if verify:
        verify_sources(sources)
    canonical = "|".join(
        [manifest["contract_version"]] + [f"{sid}={sources[sid]['sha256']}" for sid in SOURCE_IDS]
    )
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return manifest["contract_version"], sources, fingerprint


@dataclass
class LoadResult:
    raw_count: int = 0
    staged_count: int = 0
    out_of_scope_count: int = 0
    unidentified_count: int = 0
    reject_count: int = 0
    missing: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    invalid: Counter = field(default_factory=Counter)
    issues: list[tuple] = field(default_factory=list)

    def missing_json(self) -> dict[str, dict[str, int]]:
        return {field: dict(tokens) for field, tokens in self.missing.items()}


class RecordParser:
    def __init__(self, source_id: str, sha: str, row_id: int, raw: dict, result: LoadResult, batch_id: uuid.UUID):
        self.source_id, self.sha, self.row_id = source_id, sha, row_id
        self.raw, self.result, self.batch_id = raw, result, batch_id

    def issue(self, field: str, code: str, issue_type: str, raw_value: Any, reason: str, severity: str = "error") -> None:
        value = None if raw_value is None else str(raw_value)
        self.result.issues.append(
            (self.batch_id, self.source_id, self.sha, self.row_id, field, code, issue_type, value, reason, severity)
        )
        if issue_type == "invalid":
            self.result.invalid[code] += 1

    def value(self, field: str, kind: str = "text", *, missing_tokens: set[str] | None = None,
              nonnegative: bool = False, guest: bool = False) -> Any:
        raw = self.raw.get(field)
        tokens = missing_tokens if missing_tokens is not None else {""}
        if raw is None or (isinstance(raw, str) and raw in tokens):
            token = "<JSON null>" if raw is None else raw
            self.result.missing[field][token] += 1
            if field == "children":
                self.issue(field, "MISSING_CHILDREN", "missing", raw, "Guest component is unknown", "warning")
            return None
        if kind == "text":
            return raw
        try:
            if kind == "integer":
                if not isinstance(raw, str) or not INTEGER_RE.fullmatch(raw):
                    raise ValueError("not an integer token")
                parsed = int(raw)
                if not -(2**31) <= parsed < 2**31:
                    raise ValueError("outside PostgreSQL integer range")
            elif kind == "numeric":
                parsed = Decimal(str(raw))
                if not parsed.is_finite():
                    raise ValueError("non-finite numeric value")
                # Keep a safe subset of PostgreSQL NUMERIC's range. Oversized
                # present tokens remain in raw_record and receive an issue.
                if len(parsed.as_tuple().digits) > 10000 or abs(parsed.adjusted()) > 10000:
                    raise ValueError("outside supported numeric range")
            elif kind == "date":
                parsed = date.fromisoformat(str(raw))
            elif kind == "boolean":
                if str(raw).lower() not in {"true", "false"}:
                    raise ValueError("not a boolean token")
                parsed = str(raw).lower() == "true"
            else:
                raise ValueError(f"Unsupported parser kind {kind}")
        except (ValueError, InvalidOperation, OverflowError) as exc:
            code = "DATE_PARSE_FAILED" if kind == "date" else "NUMERIC_PARSE_FAILED" if kind in {"integer", "numeric"} else "BOOLEAN_PARSE_FAILED"
            self.issue(field, code, "invalid", raw, f"Present value cannot be parsed as {kind}: {exc}")
            return None
        if nonnegative and parsed < 0:
            code = "WEATHER_NEGATIVE_PRECIPITATION" if field == "precipitation_sum" else "NEGATIVE_GUEST_OR_NIGHT" if guest or "nights" in field else "NEGATIVE_COUNT"
            self.issue(field, code, "invalid", raw, "Present value is negative")
        if guest and parsed != parsed.to_integral_value():
            self.issue(field, "GUEST_NOT_INTEGER", "invalid", raw, "Guest count must be integral")
        return parsed


def insert_issues(cur: psycopg.Cursor, issues: list[tuple]) -> None:
    if not issues:
        return
    cur.executemany(
        """INSERT INTO staging.quality_issue
           (batch_id,source_id,source_file_sha256,source_row_id,field,rule_code,issue_type,raw_value,reason,severity)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        issues,
    )
