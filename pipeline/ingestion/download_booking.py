#!/usr/bin/env python3
"""Download the required public Kaggle dataset without modifying source files."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


DATASET_SLUG = "mathsian/hotel-bookings"
METADATA_URL = f"https://www.kaggle.com/api/v1/datasets/view/{DATASET_SLUG}"
DOWNLOAD_URL = f"https://www.kaggle.com/api/v1/datasets/download/{DATASET_SLUG}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "hotel-dwdss-acquisition/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def safe_extract(archive: Path, destination: Path) -> list[Path]:
    destination_resolved = destination.resolve()
    extracted: list[Path] = []
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if destination_resolved not in target.parents and target != destination_resolved:
                raise ValueError(f"Unsafe archive member: {member.filename}")
        bundle.extractall(destination)
        extracted = [destination / member.filename for member in bundle.infolist() if not member.is_dir()]
    return extracted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/booking"))
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = args.output_dir / f"kaggle_metadata_mathsian_hotel-bookings_{args.run_id}.json"
    archive_path = args.output_dir / f"hotel-bookings_mathsian_{args.run_id}.zip"
    extract_dir = args.output_dir / f"mathsian_hotel-bookings_{args.run_id}"
    for target in (metadata_path, archive_path, extract_dir):
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite existing acquisition output: {target}")

    download(METADATA_URL, metadata_path)
    download(DOWNLOAD_URL, archive_path)
    extract_dir.mkdir()
    extracted = safe_extract(archive_path, extract_dir)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    manifest = {
        "dataset_slug": DATASET_SLUG,
        "metadata_url": METADATA_URL,
        "download_url": DOWNLOAD_URL,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "kaggle_version": metadata.get("currentVersionNumber"),
        "kaggle_last_updated": metadata.get("lastUpdated"),
        "license": metadata.get("licenseName"),
        "metadata_file": str(metadata_path),
        "metadata_sha256": sha256(metadata_path),
        "archive_file": str(archive_path),
        "archive_sha256": sha256(archive_path),
        "extracted_files": [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in extracted
        ],
    }
    manifest_path = args.output_dir / f"booking_acquisition_manifest_{args.run_id}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
