"""Typed configuration loaded from JSON."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from agentindex.erc8004 import Registry


@dataclass(frozen=True)
class BigQueryNetworkConfig:
    logs_table: str


@dataclass(frozen=True)
class EnsNetworkConfig:
    enabled: bool
    bq_dataset: str
    resolvers_table: str
    resolutions_table: str
    identity_registry_erc7930: str

    def ensip25_key_prefix(self) -> str:
        return f"agent-registration[{self.identity_registry_erc7930.lower()}]["


@dataclass(frozen=True)
class RegistrationFetchConfig:
    timeout_seconds: int
    workers: int


@dataclass(frozen=True)
class NetworkConfig:
    key: str
    chain_id: int
    enabled: bool
    launch_date: date
    lag_days: int
    bigquery: BigQueryNetworkConfig
    registries: tuple[Registry, ...]
    ens: EnsNetworkConfig | None
    registration_fetch: RegistrationFetchConfig

    def sync_through_date(self) -> date:
        return datetime.now(timezone.utc).date() - timedelta(days=self.lag_days)

    def registry(self, name: str) -> Registry:
        for registry in self.registries:
            if registry.name == name:
                return registry
        raise KeyError(f"Unknown registry {name!r} on network {self.key!r}")

    @property
    def ens_enabled(self) -> bool:
        return self.ens is not None and self.ens.enabled


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    index_db: Path
    default_network: str
    networks: dict[str, NetworkConfig]

    def network(self, key: str | None = None) -> NetworkConfig:
        name = key or self.default_network
        try:
            return self.networks[name]
        except KeyError as exc:
            known = ", ".join(sorted(self.networks))
            raise SystemExit(f"Unknown network {name!r}; configured: {known}") from exc

    def enabled_networks(self) -> tuple[NetworkConfig, ...]:
        return tuple(n for n in self.networks.values() if n.enabled)

    def network_for_chain_id(self, chain_id: int) -> NetworkConfig | None:
        for network in self.networks.values():
            if network.chain_id == chain_id:
                return network
        return None
