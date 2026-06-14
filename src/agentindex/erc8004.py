"""ERC-8004 registry event descriptor."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Registry:
    name: str
    address: str
    topic0: str
    event_name: str
