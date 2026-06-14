"""Load config/default.json (or AGENTINDEX_CONFIG override)."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from agentindex.config.models import (
    AppConfig,
    BigQueryNetworkConfig,
    EnsNetworkConfig,
    NetworkConfig,
    RegistrationFetchConfig,
)
from agentindex.erc8004 import Registry


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_config_path() -> Path:
    return repo_root() / "config" / "default.json"


def resolve_config_path() -> Path:
    load_dotenv(repo_root() / ".env")
    raw = os.environ.get("AGENTINDEX_CONFIG", "").strip()
    path = Path(raw) if raw else default_config_path()
    if not path.is_absolute():
        path = repo_root() / path
    if not path.is_file():
        raise SystemExit(f"Config file not found: {path}")
    return path


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_root() / path
    return path


def _parse_registry(raw: dict) -> Registry:
    return Registry(
        name=str(raw["name"]),
        address=str(raw["address"]).lower(),
        topic0=str(raw["topic0"]).lower(),
        event_name=str(raw["event_name"]),
    )


def _parse_ens(raw: dict | None) -> EnsNetworkConfig | None:
    if not raw or not raw.get("enabled", False):
        return None
    return EnsNetworkConfig(
        enabled=True,
        bq_dataset=str(raw["bq_dataset"]),
        resolvers_table=str(raw.get("resolvers_table", "resolvers")),
        resolutions_table=str(raw.get("resolutions_table", "resolutions")),
        identity_registry_erc7930=str(raw["identity_registry_erc7930"]).lower(),
    )


def _parse_network(key: str, raw: dict) -> NetworkConfig:
    bq_raw = raw.get("bigquery") or {}
    logs_table = bq_raw.get("logs_table")
    if raw.get("enabled", True) and not logs_table:
        raise SystemExit(
            f"Network {key!r} is enabled but bigquery.logs_table is not configured"
        )

    fetch_raw = raw.get("registration_fetch") or {}
    return NetworkConfig(
        key=key,
        chain_id=int(raw["chain_id"]),
        enabled=bool(raw.get("enabled", True)),
        launch_date=date.fromisoformat(str(raw["launch_date"])),
        lag_days=int(raw.get("lag_days", 1)),
        bigquery=BigQueryNetworkConfig(logs_table=str(logs_table or "")),
        registries=tuple(_parse_registry(item) for item in raw.get("registries") or []),
        ens=_parse_ens(raw.get("ens")),
        registration_fetch=RegistrationFetchConfig(
            timeout_seconds=int(fetch_raw.get("timeout_seconds", 30)),
            workers=int(fetch_raw.get("workers", 8)),
        ),
    )


def load_app_config(path: Path | None = None) -> AppConfig:
    config_path = path or resolve_config_path()
    data = json.loads(config_path.read_text(encoding="utf-8"))

    networks = {
        key: _parse_network(key, raw)
        for key, raw in (data.get("networks") or {}).items()
    }
    if not networks:
        raise SystemExit("Config must define at least one network")

    default_network = str(data.get("default_network", next(iter(networks))))
    if default_network not in networks:
        raise SystemExit(
            f"default_network {default_network!r} is not defined in networks"
        )

    return AppConfig(
        data_dir=_resolve_path(str(data.get("data_dir", "data"))),
        index_db=_resolve_path(str(data.get("index_db", "data/agentindex.db"))),
        default_network=default_network,
        networks=networks,
    )
