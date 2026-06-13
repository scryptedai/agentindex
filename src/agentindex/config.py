"""Environment-backed configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from agentindex.erc8004 import LAUNCH_DATE


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


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


@dataclass(frozen=True)
class Settings:
    credentials_path: Path
    max_bytes_billed: int
    data_dir: Path
    launch_date: date
    lag_days: int

    @classmethod
    def load(cls) -> Settings:
        load_dotenv(_repo_root() / ".env")

        creds = os.path.expanduser(_require("GOOGLE_APPLICATION_CREDENTIALS"))
        if creds.startswith("AIza"):
            raise SystemExit(
                "GOOGLE_APPLICATION_CREDENTIALS must be a service account JSON path"
            )
        if not Path(creds).is_file():
            raise SystemExit(f"GOOGLE_APPLICATION_CREDENTIALS file not found: {creds}")

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds

        launch_raw = os.environ.get("ERC8004_LAUNCH_DATE", LAUNCH_DATE).strip()
        launch_date = date.fromisoformat(launch_raw)

        data_raw = os.environ.get("DATA_DIR", "data").strip()
        data_dir = Path(data_raw)
        if not data_dir.is_absolute():
            data_dir = _repo_root() / data_dir

        return cls(
            credentials_path=Path(creds),
            max_bytes_billed=_int_env("BQ_MAX_BYTES_BILLED", 3_221_225_472),
            data_dir=data_dir,
            launch_date=launch_date,
            lag_days=_int_env("BQ_LAG_DAYS", 1),
        )

    def sync_through_date(self) -> date:
        """Last calendar day safe to index given public dataset lag."""
        return (datetime.now(timezone.utc).date() - timedelta(days=self.lag_days))


@dataclass(frozen=True)
class IndexSettings:
    """Config for building the local SQLite corpus (no BigQuery required)."""

    data_dir: Path
    db_path: Path
    network: str = "ethereum"
    network_id: int = 1

    @classmethod
    def load(cls) -> IndexSettings:
        load_dotenv(_repo_root() / ".env")

        data_raw = os.environ.get("DATA_DIR", "data").strip()
        data_dir = Path(data_raw)
        if not data_dir.is_absolute():
            data_dir = _repo_root() / data_dir

        db_raw = os.environ.get("INDEX_DB", "").strip()
        if db_raw:
            db_path = Path(db_raw)
            if not db_path.is_absolute():
                db_path = _repo_root() / db_path
        else:
            db_path = data_dir / "agentindex.db"

        network = os.environ.get("INDEX_NETWORK", "ethereum").strip() or "ethereum"
        network_id = _int_env("NETWORK_ID", 1)

        return cls(
            data_dir=data_dir,
            db_path=db_path,
            network=network,
            network_id=network_id,
        )
