"""Data directory layout."""

from __future__ import annotations

from datetime import date
from pathlib import Path


class DataLayout:
    def __init__(self, root: Path, network: str = "ethereum") -> None:
        self.root = root
        self.network = network
        self.network_dir = root / network

    @property
    def meta_path(self) -> Path:
        return self.network_dir / "meta.json"

    def registry_dir(self, registry: str) -> Path:
        return self.network_dir / registry

    def chunk_path(self, registry: str, day: date) -> Path:
        return self.registry_dir(registry) / f"{day.isoformat()}.jsonl"

    def events_path(self, registry: str) -> Path:
        """Single-file backfill output per registry."""
        return self.registry_dir(registry) / "events.jsonl"

    @property
    def ens_dir(self) -> Path:
        return self.network_dir / "ens"

    @property
    def ens_meta_path(self) -> Path:
        return self.ens_dir / "meta.json"

    @property
    def ens_verified_path(self) -> Path:
        return self.ens_dir / "verified.jsonl"

    @property
    def ens_claimed_path(self) -> Path:
        return self.ens_dir / "claimed.jsonl"

    @property
    def ens_cross_registrations_path(self) -> Path:
        return self.ens_dir / "cross_registrations.jsonl"

    def ens_registration_path(self, agent_id: int) -> Path:
        return self.ens_dir / "registrations" / f"{agent_id}.json"

    def ensure(self) -> None:
        self.network_dir.mkdir(parents=True, exist_ok=True)
        for name in ("identity", "reputation"):
            self.registry_dir(name).mkdir(parents=True, exist_ok=True)

    def ensure_ens(self) -> None:
        self.ensure()
        self.ens_dir.mkdir(parents=True, exist_ok=True)
        (self.ens_dir / "registrations").mkdir(parents=True, exist_ok=True)
