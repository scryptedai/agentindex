"""ENS ingest progress on disk."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class RegistrationFetchState:
    token_uri: str
    fetched_at: str
    claimed_ens_names: list[str] = field(default_factory=list)
    fetch_error: str | None = None

    @property
    def claimed_ens(self) -> str | None:
        return self.claimed_ens_names[0] if self.claimed_ens_names else None


@dataclass
class EnsMeta:
    bq_last_run_at: str | None = None
    bq_bytes_billed: int = 0
    verified_count: int = 0
    registrations_fetched: int = 0
    registrations_failed: int = 0
    registrations_skipped: int = 0
    registration_uris: dict[str, RegistrationFetchState] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> EnsMeta:
        if not path.is_file():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        registration_uris = {}
        for agent_id, state in data.get("registration_uris", {}).items():
            names = state.get("claimed_ens_names")
            if names is None and state.get("claimed_ens"):
                names = [state["claimed_ens"]]
            registration_uris[agent_id] = RegistrationFetchState(
                token_uri=state["token_uri"],
                fetched_at=state["fetched_at"],
                claimed_ens_names=list(names or []),
                fetch_error=state.get("fetch_error"),
            )
        return cls(
            bq_last_run_at=data.get("bq_last_run_at"),
            bq_bytes_billed=int(data.get("bq_bytes_billed") or 0),
            verified_count=int(data.get("verified_count") or 0),
            registrations_fetched=int(data.get("registrations_fetched") or 0),
            registrations_failed=int(data.get("registrations_failed") or 0),
            registrations_skipped=int(data.get("registrations_skipped") or 0),
            registration_uris=registration_uris,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
