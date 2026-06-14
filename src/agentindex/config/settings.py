"""Runtime settings: JSON config + credential env vars."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from agentindex.config.loader import load_app_config, repo_root
from agentindex.config.models import AppConfig, NetworkConfig


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f"{name} must be an integer, got: {raw!r}") from None


def _load_credentials() -> Path:
    creds = os.path.expanduser(_require("GOOGLE_APPLICATION_CREDENTIALS"))
    if creds.startswith("AIza"):
        raise SystemExit(
            "GOOGLE_APPLICATION_CREDENTIALS must be a service account JSON path"
        )
    if not Path(creds).is_file():
        raise SystemExit(f"GOOGLE_APPLICATION_CREDENTIALS file not found: {creds}")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds
    return Path(creds)


@dataclass(frozen=True)
class Settings:
    """BigQuery ingest settings."""

    config: AppConfig
    credentials_path: Path
    max_bytes_billed: int

    @classmethod
    def load(cls) -> Settings:
        load_dotenv(repo_root() / ".env")
        return cls(
            config=load_app_config(),
            credentials_path=_load_credentials(),
            max_bytes_billed=_int_env("BQ_MAX_BYTES_BILLED", 3_221_225_472),
        )

    @property
    def data_dir(self) -> Path:
        return self.config.data_dir

    def network(self, key: str | None = None) -> NetworkConfig:
        return self.config.network(key)


@dataclass(frozen=True)
class IndexSettings:
    """Local SQLite build settings (no BigQuery credentials required)."""

    config: AppConfig

    @classmethod
    def load(cls) -> IndexSettings:
        load_dotenv(repo_root() / ".env")
        return cls(config=load_app_config())

    @property
    def data_dir(self) -> Path:
        return self.config.data_dir

    @property
    def db_path(self) -> Path:
        return self.config.index_db
