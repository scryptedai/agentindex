"""CLI entry points."""

from __future__ import annotations

from agentindex.ingest.backfill import backfill_ethereum
from agentindex.ingest.sync import sync_ethereum


def main_backfill() -> None:
    backfill_ethereum()


def main_sync() -> None:
    sync_ethereum()
