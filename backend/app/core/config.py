"""Application configuration and environment management."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load_dotenv(env_path: Path | None = None) -> None:
    """Read local .env without overwriting existing process environment variables."""
    target = env_path or (ROOT / ".env")
    if not target.is_file():
        return
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    postgres_db: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "hotel_dwdss"))
    postgres_user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "hotel_user"))
    postgres_password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", ""))
    postgres_host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    postgres_port: str = field(default_factory=lambda: os.getenv("POSTGRES_PORT", "5432"))

    hotel_name: str = "City Hotel"
    location: str = "Lisbon, Portugal"
    timezone: str = "Europe/Lisbon"
    api_prefix: str = "/api"

    cors_origins: list[str] = field(default_factory=lambda: [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
        ).split(",")
        if origin.strip()
    ])


def get_settings() -> Settings:
    load_dotenv()
    return Settings()
