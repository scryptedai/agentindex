"""Backfill/sync progress and watermarks on disk."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


from agentindex.storage.backfill_job import BackfillJob


@dataclass
class RegistryState:
    address: str
    last_block_number: int | None = None
    last_log_index: int | None = None
    last_block_timestamp: str | None = None
    chunks_completed: list[str] = field(default_factory=list)
    total_events: int = 0
    total_bytes_billed: int = 0


@dataclass
class Meta:
    network: str
    launch_date: str
    backfill_complete: bool = False
    backfill_completed_at: str | None = None
    registries: dict[str, RegistryState] = field(default_factory=dict)
    backfill_jobs: dict[str, BackfillJob] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path, network: str, launch_date: date) -> Meta:
        if not path.is_file():
            return cls(network=network, launch_date=launch_date.isoformat())
        data = json.loads(path.read_text(encoding="utf-8"))
        registries = {
            name: RegistryState(**state)
            for name, state in data.get("registries", {}).items()
        }
        backfill_jobs = {
            name: BackfillJob(**job)
            for name, job in data.get("backfill_jobs", {}).items()
        }
        return cls(
            network=data.get("network", network),
            launch_date=data.get("launch_date", launch_date.isoformat()),
            backfill_complete=data.get("backfill_complete", False),
            backfill_completed_at=data.get("backfill_completed_at"),
            registries=registries,
            backfill_jobs=backfill_jobs,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def registry(self, name: str, address: str) -> RegistryState:
        if name not in self.registries:
            self.registries[name] = RegistryState(address=address)
        return self.registries[name]

    def chunk_done(self, registry: str, day: date) -> bool:
        state = self.registries.get(registry)
        if not state:
            return False
        return day.isoformat() in state.chunks_completed

    def backfill_job(self, name: str) -> BackfillJob:
        if name not in self.backfill_jobs:
            self.backfill_jobs[name] = BackfillJob(registry=name)
        return self.backfill_jobs[name]

    def mark_registry_fetch_from_last(
        self,
        registry: str,
        address: str,
        row_count: int,
        bytes_billed: int,
        last_row: dict[str, Any] | None,
    ) -> None:
        state = self.registry(registry, address)
        state.total_events = row_count
        state.total_bytes_billed = bytes_billed
        state.chunks_completed = []

        if last_row:
            state.last_block_number = int(last_row["block_number"])
            state.last_log_index = int(last_row["log_index"])
            ts = last_row["block_timestamp"]
            state.last_block_timestamp = (
                ts.isoformat() if isinstance(ts, datetime) else str(ts)
            )

    def mark_registry_fetch(
        self,
        registry: str,
        address: str,
        rows: list[dict[str, Any]],
        bytes_billed: int,
    ) -> None:
        """Record a bulk fetch (backfill) watermark."""
        state = self.registry(registry, address)
        state.total_events = len(rows)
        state.total_bytes_billed = bytes_billed
        state.chunks_completed = []

        if rows:
            last = max(rows, key=lambda r: (r["block_number"], r["log_index"]))
            state.last_block_number = int(last["block_number"])
            state.last_log_index = int(last["log_index"])
            ts = last["block_timestamp"]
            state.last_block_timestamp = (
                ts.isoformat() if isinstance(ts, datetime) else str(ts)
            )

    def mark_chunk(
        self,
        registry: str,
        address: str,
        day: date,
        rows: list[dict[str, Any]],
        bytes_billed: int,
    ) -> None:
        state = self.registry(registry, address)
        day_str = day.isoformat()
        if day_str not in state.chunks_completed:
            state.chunks_completed.append(day_str)
            state.chunks_completed.sort()

        state.total_events += len(rows)
        state.total_bytes_billed += bytes_billed

        if rows:
            last = max(rows, key=lambda r: (r["block_number"], r["log_index"]))
            state.last_block_number = int(last["block_number"])
            state.last_log_index = int(last["log_index"])
            ts = last["block_timestamp"]
            state.last_block_timestamp = ts.isoformat() if isinstance(ts, datetime) else str(ts)

    def mark_backfill_complete(self) -> None:
        self.backfill_complete = True
        self.backfill_completed_at = (
            datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        )
