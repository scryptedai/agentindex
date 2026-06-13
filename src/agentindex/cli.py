"""CLI entry points."""

from __future__ import annotations

from agentindex.config import IndexSettings
from agentindex.index.build import build_index
from agentindex.ingest.backfill import backfill_ethereum
from agentindex.ingest.sync import sync_ethereum
from agentindex.storage.paths import DataLayout


def main_backfill() -> None:
    backfill_ethereum()


def main_sync() -> None:
    sync_ethereum()


def main_build() -> None:
    settings = IndexSettings.load()
    layout = DataLayout(settings.data_dir, network=settings.network)
    stats = build_index(
        settings.db_path,
        layout,
        network_id=settings.network_id,
    )
    print(f"Built {settings.db_path}")
    print(f"  agents:              {stats.agents:,}")
    print(f"  reputation feedback: {stats.feedback:,}")
    print(f"  agents w/ feedback:  {stats.agents_with_feedback:,}")
    print(
        f"  source events:       {stats.identity_events:,} identity, "
        f"{stats.reputation_events:,} reputation"
    )
