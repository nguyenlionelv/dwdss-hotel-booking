#!/usr/bin/env python3
"""Fetch Lisbon city-level historical weather from Open-Meteo."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


GEOCODING_ENDPOINT = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"


def get_json(url: str) -> tuple[dict, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "hotel-dwdss-acquisition/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = response.read()
    return json.loads(raw), raw


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/weather"))
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    geocoding_params = urllib.parse.urlencode(
        {"name": "Lisbon", "count": 10, "language": "en", "format": "json", "countryCode": "PT"}
    )
    geocoding_url = f"{GEOCODING_ENDPOINT}?{geocoding_params}"
    geocoding, geocoding_raw = get_json(geocoding_url)
    candidates = [
        item
        for item in geocoding.get("results", [])
        if item.get("country_code") == "PT" and item.get("name") in {"Lisbon", "Lisboa"}
    ]
    if not candidates:
        raise RuntimeError("Open-Meteo geocoding did not return a Lisbon, Portugal candidate")
    selected = candidates[0]
    latitude = selected["latitude"]
    longitude = selected["longitude"]

    weather_params = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": args.start_date,
            "end_date": args.end_date,
            "daily": "temperature_2m_mean,precipitation_sum",
            "timezone": "Europe/Lisbon",
            "models": "era5",
        }
    )
    weather_url = f"{ARCHIVE_ENDPOINT}?{weather_params}"
    weather, weather_raw = get_json(weather_url)
    if "daily" not in weather or "time" not in weather["daily"]:
        raise RuntimeError(f"Unexpected weather response: {weather}")

    geocoding_path = args.output_dir / f"open_meteo_lisbon_geocoding_{args.run_id}.json"
    weather_path = args.output_dir / f"open_meteo_lisbon_era5_{args.start_date}_{args.end_date}_{args.run_id}.json"
    metadata_path = args.output_dir / f"open_meteo_lisbon_era5_{args.start_date}_{args.end_date}_{args.run_id}.metadata.json"
    for path in (geocoding_path, weather_path, metadata_path):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing weather output: {path}")
    geocoding_path.write_bytes(geocoding_raw)
    weather_path.write_bytes(weather_raw)
    metadata = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "documentation": "https://open-meteo.com/en/docs/historical-weather-api",
        "geocoding_request": geocoding_url,
        "weather_request": weather_url,
        "selected_city_result": selected,
        "coordinate_semantics": "Representative Lisbon city coordinate, not the anonymized hotel's exact location.",
        "model": "ERA5",
        "timezone": "Europe/Lisbon",
        "daily_variables": ["temperature_2m_mean", "precipitation_sum"],
        "units": weather.get("daily_units", {}),
        "weather_file": str(weather_path),
        "weather_sha256": sha256_bytes(weather_raw),
        "geocoding_file": str(geocoding_path),
        "geocoding_sha256": sha256_bytes(geocoding_raw),
        "returned_days": len(weather["daily"]["time"]),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
