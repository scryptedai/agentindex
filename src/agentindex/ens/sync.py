"""Daily ENS sync: refresh BigQuery discovery + fetch new/changed registrations."""

from __future__ import annotations

import os

from agentindex.bq.client import BigQueryRunner
from agentindex.config import Settings
from agentindex.ens.discovery import discover_verified_agents
from agentindex.ens.registrations import (
    DEFAULT_TIMEOUT,
    DEFAULT_WORKERS,
    fetch_registrations,
)
from agentindex.index.ens_sources import read_jsonl
from agentindex.storage.ens_meta import EnsMeta
from agentindex.storage.paths import DataLayout


def sync_ens(settings: Settings | None = None) -> None:
    settings = settings or Settings.load()
    layout = DataLayout(settings.data_dir)
    layout.ensure_ens()
    meta = EnsMeta.load(layout.ens_meta_path)

    print("ENS sync (ethereum mainnet)")
    print(f"Data dir: {layout.ens_dir}")
    print()

    print("Step 1/2: refresh BigQuery ENSIP-25 discovery")
    runner = BigQueryRunner(settings.max_bytes_billed)
    verified, billed = discover_verified_agents(runner, layout, meta)
    print(f"  verified links: {verified:,} ({billed:,} bytes billed)")
    print()

    print("Step 2/2: fetch new/changed registration JSON")
    timeout = int(os.environ.get("REGISTRATION_FETCH_TIMEOUT", DEFAULT_TIMEOUT))
    workers = int(os.environ.get("REGISTRATION_FETCH_WORKERS", DEFAULT_WORKERS))
    fetched, failed, skipped = fetch_registrations(
        layout,
        meta,
        force=False,
        timeout=timeout,
        workers=workers,
    )
    claimed = len(read_jsonl(layout.ens_claimed_path))
    print(
        f"  registrations: {fetched:,} fetched, {failed:,} failed, "
        f"{skipped:,} skipped (unchanged)"
    )
    print(f"  claimed ENS names: {claimed:,}")
    print()
    print("Run `poetry run agentindex-build` to merge ENS data into SQLite.")
